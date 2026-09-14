"""도메인 구현 — 개발자가 작성하는 유일한 파일.

아래 세 함수만 구현하면 된다. REST API, 로깅, 에러 처리, 표준 응답 포맷,
오브젝트 스토리지 입출력, 첨부파일 처리는 서버(pxa_drm_server)가 담당한다.

    def encrypt(filepath: str) -> bool     # 암호화 성공 True / 실패 False
    def decrypt(filepath: str) -> bool     # 복호화 성공 True / 실패 False
    def check(filepath: str) -> bool       # 암호화되어 있으면 True

규칙
----
1. filepath 는 **서버가 준비해 둔 로컬 파일 경로**다. 오브젝트 스토리지든
   첨부파일이든 여기까지 오면 똑같은 로컬 파일이므로 경로만 신경 쓰면 된다.
2. encrypt/decrypt 는 **그 경로의 파일을 제자리에서 바꾸면** 된다.
   성공하면 서버가 원래 위치(로컬 경로 / 오브젝트 스토리지 / 응답 파일)로
   되돌려 놓는다.
3. check 는 **파일을 수정하면 안 된다**(읽기 전용).
4. 실패는 False 를 반환하거나 예외를 던지면 된다. 서버가 표준 에러 응답
   (pxa-21001 / pxa-21002 / pxa-21003)으로 변환하고 로그를 남긴다.
5. 오래 걸리는 동기 작업이어도 괜찮다. 서버가 워커 스레드에서 호출한다.
   ``async def`` 로 작성해도 그대로 동작한다.

아래 구현은 동작 확인용 **샘플**이다(단순 XOR + 헤더).
실제 DRM/암호화 모듈 호출로 바꿔서 쓰면 된다.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("pxa")

# 샘플 구현용 상수 — 실제 DRM 모듈로 교체할 부분
_MAGIC = b"PXADRM01"
_KEY = b"pxa-sample-key"


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt(filepath: str) -> bool:
    """파일을 암호화한다. 성공하면 True, 실패하면 False."""
    path = Path(filepath)
    data = path.read_bytes()

    if data.startswith(_MAGIC):
        logger.info("이미 암호화된 파일입니다: %s", path.name)
        return False

    path.write_bytes(_MAGIC + _xor(data, _KEY))
    logger.info("암호화 완료: %s (%d bytes)", path.name, len(data))
    return True


def decrypt(filepath: str) -> bool:
    """파일을 복호화한다. 성공하면 True, 실패하면 False."""
    path = Path(filepath)
    data = path.read_bytes()

    if not data.startswith(_MAGIC):
        logger.info("암호화된 파일이 아닙니다: %s", path.name)
        return False

    body = data[len(_MAGIC):]
    path.write_bytes(_xor(body, _KEY))
    logger.info("복호화 완료: %s (%d bytes)", path.name, len(body))
    return True


def check(filepath: str) -> bool:
    """파일이 암호화되어 있으면 True, 아니면 False. (파일을 수정하지 않는다)"""
    with Path(filepath).open("rb") as f:
        return f.read(len(_MAGIC)) == _MAGIC
