"""DRM 서버 전용 예외.

모두 pxa-common 의 ``AppError`` 를 상속하므로
``register_exception_handlers(app)`` 한 줄로 표준 응답(HTTP 200 + 코드)으로
자동 변환된다. 개발자는 예외를 잡을 필요가 없다.
"""
from __future__ import annotations

from typing import Any, Optional

from pxa_common import AppError

from .codes import DrmCode


class DrmError(AppError):
    """DRM 서버 예외 베이스."""

    code_enum: DrmCode = DrmCode.DOMAIN_ERROR

    def __init__(self, message: Optional[str] = None, result: Any = None):
        super().__init__(self.code_enum, message, result)


class EncryptFailedError(DrmError):
    """domain_core.encrypt() 가 False 를 반환 (pxa-21001)."""

    code_enum = DrmCode.ENCRYPT_FAILED


class DecryptFailedError(DrmError):
    """domain_core.decrypt() 가 False 를 반환 (pxa-21002)."""

    code_enum = DrmCode.DECRYPT_FAILED


class DomainError(DrmError):
    """domain_core 함수가 예외를 던짐 (pxa-21003)."""

    code_enum = DrmCode.DOMAIN_ERROR


class DomainNotImplementedError(DrmError):
    """domain_core 에 해당 함수가 없음 (pxa-21004)."""

    code_enum = DrmCode.DOMAIN_NOT_IMPLEMENTED


class DomainContractError(DrmError):
    """domain_core 함수가 True/False 가 아닌 값을 반환 (pxa-21005)."""

    code_enum = DrmCode.DOMAIN_CONTRACT_ERROR


class TargetNotFoundError(DrmError):
    """대상 파일/오브젝트 없음 (pxa-22001)."""

    code_enum = DrmCode.FILE_NOT_FOUND


class PathNotAllowedError(DrmError):
    """allowed_roots 밖의 경로 (pxa-22002)."""

    code_enum = DrmCode.PATH_NOT_ALLOWED


class InvalidUriError(DrmError):
    """uri 형식 오류 (pxa-22003)."""

    code_enum = DrmCode.INVALID_URI


class BucketNotConfiguredError(DrmError):
    """config 에 없는 버킷 별칭 (pxa-22004)."""

    code_enum = DrmCode.BUCKET_NOT_CONFIGURED


class StorageError(DrmError):
    """오브젝트 스토리지 입출력 오류 (pxa-22005)."""

    code_enum = DrmCode.STORAGE_ERROR


class UploadError(DrmError):
    """첨부파일 처리 오류 (pxa-22006)."""

    code_enum = DrmCode.UPLOAD_ERROR


class FileTooLargeError(DrmError):
    """허용 크기 초과 (pxa-22007)."""

    code_enum = DrmCode.FILE_TOO_LARGE
