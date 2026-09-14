"""S3 호환 오브젝트 스토리지(uri) 대상.

uri 형식은 ``별칭:오브젝트키`` 다 (예: ``ABC:download/file.docx``).
``s3://ABC/download/file.docx`` 형식도 받아들인다.
별칭별 접근 정보(access key / secret key / endpoint)는 config 의
``storage.buckets`` 섹션에서 읽는다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

from starlette.concurrency import run_in_threadpool

from ..config import BucketConfig, StorageConfig
from ..errors import (
    BucketNotConfiguredError,
    InvalidUriError,
    StorageError,
    TargetNotFoundError,
)
from ..workspace import Workspace
from .base import FileSource

logger = logging.getLogger("pxa")

_clients: dict[str, object] = {}

# 오브젝트가 없을 때 S3 호환 스토리지가 쓰는 에러 코드들
_NOT_FOUND_CODES = {"404", "NoSuchKey", "NoSuchBucket", "NotFound"}


def parse_uri(uri: str) -> Tuple[str, str]:
    """``ABC:download/file.docx`` -> ``("ABC", "download/file.docx")``."""
    raw = (uri or "").strip()
    if not raw:
        raise InvalidUriError("uri 가 비어 있습니다.")

    if raw.startswith("s3://"):
        rest = raw[len("s3://"):]
        alias, _, key = rest.partition("/")
    else:
        alias, sep, key = raw.partition(":")
        if not sep:
            raise InvalidUriError(
                f"uri 는 '버킷별칭:오브젝트키' 형식이어야 합니다: {raw}"
            )

    alias = alias.strip()
    key = key.strip().lstrip("/")
    if not alias or "/" in alias or not key:
        raise InvalidUriError(
            f"uri 는 '버킷별칭:오브젝트키' 형식이어야 합니다: {raw}"
        )
    return alias, key


def _build_client(alias: str, cfg: BucketConfig):
    """별칭별 boto3 S3 클라이언트를 만든다(프로세스 내 캐시)."""
    if alias in _clients:
        return _clients[alias]
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError as exc:  # pragma: no cover - 설치 환경 문제
        raise StorageError(
            "오브젝트 스토리지를 사용하려면 boto3 가 필요합니다: pip install boto3"
        ) from exc

    boto_cfg = BotoConfig(
        s3={"addressing_style": cfg.addressing_style},
        signature_version=cfg.signature_version or "s3v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )
    client = boto3.client(
        "s3",
        endpoint_url=cfg.endpoint_url or None,
        aws_access_key_id=cfg.access_key or None,
        aws_secret_access_key=cfg.secret_key or None,
        region_name=cfg.region or None,
        verify=cfg.verify_ssl,
        config=boto_cfg,
    )
    _clients[alias] = client
    return client


def reset_clients() -> None:
    """설정을 다시 읽었을 때 클라이언트 캐시를 비운다(테스트/재기동)."""
    _clients.clear()


def _error_code(exc: Exception) -> str:
    return str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))


class ObjectStorageSource(FileSource):
    kind = "objectstorage"

    def __init__(self, uri: str, storage: StorageConfig):
        self.alias, self.key = parse_uri(uri)
        bucket = storage.resolve(self.alias)
        if bucket is None:
            known = ", ".join(sorted(storage.buckets)) or "(설정 없음)"
            raise BucketNotConfiguredError(
                f"설정에 없는 버킷 별칭입니다: {self.alias} (설정된 별칭: {known})"
            )
        self.bucket = bucket
        self._content_type: Optional[str] = None

    @property
    def location(self) -> str:
        return f"{self.alias}:{self.key}"

    @property
    def filename(self) -> str:
        return Path(self.key).name

    def _client(self):
        return _build_client(self.alias, self.bucket)

    def _download(self, target: Path) -> None:
        client = self._client()
        try:
            head = client.head_object(Bucket=self.bucket.bucket, Key=self.key)
            self._content_type = head.get("ContentType")
            client.download_file(self.bucket.bucket, self.key, str(target))
        except Exception as exc:
            if _error_code(exc) in _NOT_FOUND_CODES:
                raise TargetNotFoundError(
                    f"오브젝트를 찾을 수 없습니다: {self.location}"
                ) from exc
            raise StorageError(
                f"오브젝트를 내려받지 못했습니다: {self.location} ({exc})"
            ) from exc

    def _upload(self, source: Path) -> None:
        client = self._client()
        extra = {"ContentType": self._content_type} if self._content_type else {}
        try:
            client.upload_file(
                str(source), self.bucket.bucket, self.key, ExtraArgs=extra or None
            )
        except Exception as exc:
            raise StorageError(
                f"오브젝트를 올리지 못했습니다: {self.location} ({exc})"
            ) from exc

    async def materialize(self, workspace: Workspace, for_write: bool = True) -> Path:
        target = workspace.path_for(self.filename)
        await run_in_threadpool(self._download, target)
        logger.debug("오브젝트 내려받기 완료: %s", self.location)
        return target

    async def commit(self, path: Path) -> None:
        await run_in_threadpool(self._upload, path)
        logger.debug("오브젝트 올리기 완료: %s", self.location)

    def describe(self) -> dict:
        info = super().describe()
        info.update({"bucket": self.alias, "key": self.key})
        return info
