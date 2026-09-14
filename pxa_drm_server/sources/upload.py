"""첨부파일(multipart payload) 대상.

받은 파일을 작업 디렉토리에 저장해 도메인에 넘기고,
처리 결과 파일을 그대로 응답으로 돌려준다(또는 JSON 요약).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pxa_common.fastapi import UploadFile

from ..errors import FileTooLargeError, UploadError
from ..workspace import Workspace
from .base import FileSource

logger = logging.getLogger("pxa")

_CHUNK = 1024 * 1024


class UploadFileSource(FileSource):
    kind = "upload"

    def __init__(self, upload: UploadFile, max_bytes: int = 0):
        name = (upload.filename or "").strip()
        if not name:
            raise UploadError("첨부파일의 파일명이 없습니다.")
        self.upload = upload
        self.max_bytes = max_bytes
        self._filename = Path(name).name
        self.result_path: Optional[Path] = None

    @property
    def location(self) -> str:
        return self._filename

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def content_type(self) -> str:
        return self.upload.content_type or "application/octet-stream"

    async def materialize(self, workspace: Workspace, for_write: bool = True) -> Path:
        target = workspace.path_for(self._filename)
        written = 0
        try:
            await self.upload.seek(0)
            with target.open("wb") as out:
                while True:
                    chunk = await self.upload.read(_CHUNK)
                    if not chunk:
                        break
                    written += len(chunk)
                    if self.max_bytes and written > self.max_bytes:
                        raise FileTooLargeError(
                            f"첨부파일이 허용 크기({self.max_bytes // (1024 * 1024)}MB)를 "
                            f"초과했습니다."
                        )
                    out.write(chunk)
        except FileTooLargeError:
            target.unlink(missing_ok=True)
            raise
        except OSError as exc:
            raise UploadError(f"첨부파일을 저장하지 못했습니다: {exc}") from exc
        finally:
            await self.upload.close()

        if written == 0:
            raise UploadError("첨부파일이 비어 있습니다.")
        self.result_path = target
        return target

    async def commit(self, path: Path) -> None:
        # 결과 파일 자체가 응답이므로 되돌릴 곳이 없다.
        self.result_path = path
