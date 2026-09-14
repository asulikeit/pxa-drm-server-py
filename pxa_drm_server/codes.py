"""DRM 서버 애플리케이션 코드.

pxa-common 의 ``AppCode`` 규약(코드 / 기본 메시지 / HTTP 상태)을 그대로 따른다.
공통 코드(pxa-10000, pxa-2000x)는 ``AppCode`` 를 쓰고, DRM 도메인에서만
의미가 있는 코드를 여기에 추가한다.

  - pxa-21xxx : 도메인(암복호화) 처리 관련
  - pxa-22xxx : 파일/스토리지 입출력 관련

새 코드가 필요하면 이 Enum 에만 한 줄 추가한다.
"""
from __future__ import annotations

from enum import Enum


class DrmCode(str, Enum):
    """DRM 서버 전용 애플리케이션 코드."""

    # ---- 도메인(개발자 구현) 처리 ----
    ENCRYPT_FAILED = ("pxa-21001", "파일 암호화에 실패했습니다.", 200)
    DECRYPT_FAILED = ("pxa-21002", "파일 복호화에 실패했습니다.", 200)
    DOMAIN_ERROR = ("pxa-21003", "도메인 처리 중 오류가 발생했습니다.", 200)
    DOMAIN_NOT_IMPLEMENTED = ("pxa-21004", "도메인 기능이 구현되지 않았습니다.", 200)
    DOMAIN_CONTRACT_ERROR = ("pxa-21005", "도메인 함수의 반환값이 올바르지 않습니다.", 200)

    # ---- 파일 / 스토리지 ----
    FILE_NOT_FOUND = ("pxa-22001", "대상 파일을 찾을 수 없습니다.", 200)
    PATH_NOT_ALLOWED = ("pxa-22002", "허용되지 않은 경로입니다.", 200)
    INVALID_URI = ("pxa-22003", "uri 형식이 올바르지 않습니다.", 200)
    BUCKET_NOT_CONFIGURED = ("pxa-22004", "설정되지 않은 버킷입니다.", 200)
    STORAGE_ERROR = ("pxa-22005", "오브젝트 스토리지 처리 중 오류가 발생했습니다.", 200)
    UPLOAD_ERROR = ("pxa-22006", "첨부파일 처리 중 오류가 발생했습니다.", 200)
    FILE_TOO_LARGE = ("pxa-22007", "파일 크기가 허용 범위를 초과했습니다.", 200)

    def __new__(cls, code: str, message: str, http_status: int):
        obj = str.__new__(cls, code)
        obj._value_ = code
        obj.code = code
        obj.message = message
        obj.http_status = http_status
        return obj

    @property
    def is_success(self) -> bool:
        return self.code.startswith("pxa-1")
