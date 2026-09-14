# pxa-drm-server

파일 **암복호화 API 서버**. `pxa-common==0.1.1` 위에 `fastapi==0.128.0` 으로 만들었다.

개발자는 **`domain_core.py` 에 세 함수만 구현**하면 된다.
REST API, 로깅, 에러 처리, 표준 응답 포맷, 오브젝트 스토리지 입출력,
첨부파일 처리는 서버가 전부 담당한다.

```python
# domain_core.py — 개발자가 작성하는 유일한 파일
def encrypt(filepath: str) -> bool:   # 암호화 성공 True / 실패 False
def decrypt(filepath: str) -> bool:   # 복호화 성공 True / 실패 False
def check(filepath: str) -> bool:     # 암호화되어 있으면 True (파일 수정 금지)
```

---

## 1. 빠르게 실행하기

```bash
pip install -r requirements.txt          # 또는: pip install -e ".[dev]"

# domain_core.py 의 세 함수를 실제 DRM 모듈 호출로 바꾼다 (기본은 동작 확인용 샘플)

PXA_CONFIG=config/config.yaml python -m pxa_drm_server
# 또는
PXA_CONFIG=config/config.yaml pxa-drm-server
# 또는
PXA_CONFIG=config/config.yaml uvicorn pxa_drm_server.main:app --host 0.0.0.0 --port 8000
```

- Swagger UI: `http://localhost:8000/docs`
- 상태 확인: `GET /api/v1/health`

---

## 2. 기본 제공 API

| 대상 | 호출 |
|---|---|
| 서버 로컬 경로 | `GET \| POST /api/v1/encrypt?filepath=/download/file.docx` |
| 서버 로컬 경로 | `GET \| POST /api/v1/decrypt?filepath=/download/file.docx` |
| 오브젝트 스토리지 | `GET \| POST /api/v1/encrypt?uri=ABC:download/file.docx` |
| 오브젝트 스토리지 | `GET \| POST /api/v1/decrypt?uri=ABC:download/file.docx` |
| 첨부파일 | `POST /api/v1/encrypt` (multipart, `file=@file.docx`) |
| 첨부파일 | `POST /api/v1/decrypt` (multipart, `file=@file.docx`) |
| 암호화 여부 확인 | `GET \| POST /api/v1/check` (위 세 가지 대상 모두 지원) |

`filepath`, `uri`, `file` 중 **정확히 하나**를 지정한다.
하나도 없으면 `pxa-20002`, 둘 이상이면 `pxa-20001` 로 응답한다.

```bash
# 로컬 경로
curl "http://localhost:8000/api/v1/encrypt?filepath=/download/file.docx"

# 오브젝트 스토리지 (ABC 는 config 에 등록한 버킷 별칭)
curl "http://localhost:8000/api/v1/decrypt?uri=ABC:download/file.docx"

# 첨부파일 -> 처리된 파일을 그대로 내려받는다
curl -F "file=@file.docx" "http://localhost:8000/api/v1/encrypt" -o encrypted.docx

# 첨부파일 -> 파일 대신 JSON 결과만 받고 싶을 때
curl -F "file=@file.docx" "http://localhost:8000/api/v1/encrypt?response=json"
```

### 응답 포맷

pxa-common 규약을 따른다. **HTTP 상태는 항상 200**이고 정상/비정상은 `code` 로 구분한다.
(첨부파일 요청이 성공했을 때만 예외적으로 결과 파일이 바로 내려간다.)

```json
{
  "success": true,
  "code": "pxa-10000",
  "message": "'file.docx' 파일을 암호화했습니다.",
  "result": {
    "operation": "encrypt",
    "source": {"type": "local", "location": "/download/file.docx", "filename": "file.docx"},
    "size": 29,
    "elapsed_ms": 1.8
  }
}
```

`check` 는 `result.encrypted` 에 true/false 가 담긴다.

### 에러 코드

| 코드 | 의미 |
|---|---|
| `pxa-20001` | 요청 검증 실패 (대상 중복 지정, `response` 값 오류 등) |
| `pxa-20002` | `filepath / uri / file` 중 아무것도 없음 |
| `pxa-21001` | `encrypt()` 가 False 반환 |
| `pxa-21002` | `decrypt()` 가 False 반환 |
| `pxa-21003` | 도메인 함수에서 예외 발생 |
| `pxa-21004` | 도메인 함수 미구현 |
| `pxa-21005` | 도메인 함수가 True/False 가 아닌 값을 반환 |
| `pxa-22001` | 대상 파일/오브젝트 없음 |
| `pxa-22002` | 허용되지 않은 경로 (`local.allowed_roots`) |
| `pxa-22003` | `uri` 형식 오류 |
| `pxa-22004` | 설정에 없는 버킷 별칭 |
| `pxa-22005` | 오브젝트 스토리지 입출력 오류 |
| `pxa-22006` | 첨부파일 처리 오류 |
| `pxa-22007` | 첨부파일 크기 초과 |

---

## 3. 개발자가 작성하는 코드

`domain_core.py` 하나가 전부다.

```python
def encrypt(filepath: str) -> bool:
    ok = my_drm.protect(filepath)     # 실제 DRM 모듈 호출
    return bool(ok)
```

지켜야 할 것

1. `filepath` 는 **서버가 준비해 둔 로컬 파일 경로**다. 오브젝트 스토리지든 첨부파일이든
   여기까지 오면 똑같은 로컬 파일이므로 경로만 신경 쓰면 된다.
2. `encrypt` / `decrypt` 는 **그 경로의 파일을 제자리에서 바꾸면** 된다.
   성공하면 서버가 원래 위치(로컬 경로 / 오브젝트 스토리지 / 응답 파일)로 되돌려 놓는다.
3. `check` 는 **파일을 수정하면 안 된다**(읽기 전용).
4. 실패는 `False` 를 반환하거나 예외를 던지면 된다. 서버가 표준 에러 응답으로 바꾸고 로그를 남긴다.
5. 오래 걸리는 동기 함수여도 된다. 서버가 워커 스레드에서 호출한다. `async def` 도 그대로 동작한다.

`check()` 는 선택 사항이다. 없으면 서버는 기동되지만 `/api/v1/check` 는 `pxa-21004` 로 응답한다.

---

## 4. 설정

우선순위는 **환경변수(`PXA_*`) > `config.yaml` > 기본값** 이고, 파일 경로는 `PXA_CONFIG` 로 지정한다
(pxa-common 설정 기능).

```yaml
app:     { name: "pxa-drm-server", debug: false }
server:  { host: "0.0.0.0", port: 8000 }
logging: { dir: "./logs", level: "INFO", filename: "drm-server.log", backup_count: 14 }

drm:
  domain_module: "domain_core"     # import 할 모듈명
  # domain_file: "./domain_core.py"  # 파일 경로로 직접 지정(우선 적용)
  work_dir: null                   # 임시 작업 디렉토리(null 이면 OS 임시 디렉토리)
  max_upload_size_mb: 512          # 0 이하면 제한 없음
  upload_response: "file"          # 첨부파일 기본 응답: file | json

local:
  allowed_roots: []                # 비우면 모든 경로 허용. 예: ["/download", "/data"]
  in_place: false                  # false 권장 (아래 "안전 처리" 참고)

storage:
  buckets:
    ABC:                           # uri 의 "ABC:download/file.docx" 에서 ABC
      bucket: "abc-bucket"
      endpoint_url: "https://s3.example.com"
      region: "us-east-1"
      addressing_style: "path"     # MinIO/Ceph 등 S3 호환 스토리지는 path 권장
      verify_ssl: true
      access_key: ""               # 환경변수 주입 권장
      secret_key: ""
```

### 접근키는 환경변수로

```bash
export PXA_STORAGE__BUCKETS__ABC__ACCESS_KEY=...
export PXA_STORAGE__BUCKETS__ABC__SECRET_KEY=...
export PXA_SERVER__PORT=9000
```

버킷 별칭은 **대소문자를 구분하지 않는다**. pxa-common 이 환경변수 경로를 소문자로 바꾸기 때문에,
`config.yaml` 의 `ABC` 와 환경변수의 `abc` 를 서버가 하나로 합쳐 준다.
`uri` 에는 `ABC:` 든 `abc:` 든 쓸 수 있고, `s3://ABC/download/file.docx` 형식도 받는다.

---

## 5. 동작 방식

```
요청 -> 대상 해석(filepath/uri/file) -> 로컬 작업 파일 준비
     -> domain_core.encrypt|decrypt|check(filepath)
     -> 성공 시에만 원래 위치로 반영 -> 표준 응답 -> 임시 파일 정리
```

**안전 처리**

- `local.in_place: false`(기본값)이면 작업본을 만들어 처리하고, 성공했을 때만 원본을
  원자적으로(`os.replace`) 교체한다. 도메인이 실패하거나 예외를 던져도 **원본은 그대로** 남는다.
- 오브젝트 스토리지는 성공했을 때만 같은 키로 다시 올린다(`ContentType` 유지).
- `check` 는 읽기 전용이라 큰 파일이어도 복사하지 않고 원본을 그대로 읽는다.
- 임시 작업 디렉토리는 요청이 끝나면(파일 응답이면 전송 완료 후) 지운다.

**보안**

- `local.allowed_roots` 를 지정하면 그 디렉토리 하위 경로만 처리한다(경로 정규화 후 검사).
  비워 두면 서버가 접근 가능한 모든 경로를 허용하므로, 외부에 노출되는 환경에서는 지정을 권장한다.
- 접근키는 config 파일 대신 환경변수로 주입한다.

**로깅** — `pxa-common` 의 `setup_logging()` + `RequestLoggingMiddleware`.
request-id 와 처리시간이 함께 남고, 설정한 디렉토리에 자정마다 회전 저장된다.

```
2026-09-14 21:41:03,815 | INFO | pxa | encrypt 요청: source=local location=/download/file.docx
2026-09-14 21:41:03,816 | INFO | pxa | encrypt 완료: location=/download/file.docx result=True (1.8ms)
2026-09-14 21:41:03,816 | INFO | pxa | [4126cfffb094] GET /api/v1/encrypt -> 200 (3.1ms)
```

---

## 6. 구조

```
domain_core.py              # ★ 개발자가 작성하는 유일한 파일
config/config.yaml          # 설정 (접근키는 환경변수 권장)
pxa_drm_server/
  app.py                    # FastAPI 앱 조립 (로깅/예외/미들웨어/라우터)
  main.py                   # 실행 진입점
  api/v1/routes.py          # encrypt / decrypt / check / health
  service.py                # 공통 처리 흐름
  domain.py                 # domain_core 로딩 및 호출
  sources/                  # 대상별 입출력 (local / objectstorage / upload)
  config.py  codes.py  errors.py  runtime.py  workspace.py
  messages/drm.yaml         # 메시지 카탈로그
tests/
```

## 7. 테스트

```bash
pip install -e ".[dev]"
pytest
```
