"""암복호화 처리 흐름.

라우터는 "무엇을(source) 어떤 작업(operation)" 인지만 넘기고,
여기서 아래 순서를 공통으로 처리한다.

    대상 해석 -> 로컬 파일로 준비 -> domain_core 호출 -> 결과 반영 -> 응답/정리

개발자가 작성하는 domain_core 는 로컬 파일 경로 하나만 신경 쓰면 된다.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from pxa_common import ApiResponse, RequiredFieldError, ValidationError, msg
from pxa_common.fastapi import FileResponse, UploadFile
from starlette.background import BackgroundTask

from .errors import DecryptFailedError, EncryptFailedError
from .runtime import DrmRuntime
from .sources import (
    FileSource,
    LocalFileSource,
    ObjectStorageSource,
    UploadFileSource,
)
from .workspace import Workspace

logger = logging.getLogger("pxa")

RESPONSE_FILE = "file"
RESPONSE_JSON = "json"


@dataclass(frozen=True)
class Operation:
    """API 하나가 수행하는 도메인 작업."""

    name: str            # domain_core 에서 호출할 함수 이름
    writes: bool         # 결과를 원래 위치에 되돌려야 하는가
    failure: Optional[type] = None   # False 반환 시 올릴 예외


OPERATIONS: dict[str, Operation] = {
    "encrypt": Operation("encrypt", writes=True, failure=EncryptFailedError),
    "decrypt": Operation("decrypt", writes=True, failure=DecryptFailedError),
    "check": Operation("check", writes=False),
}


def build_source(
    runtime: DrmRuntime,
    filepath: Optional[str] = None,
    uri: Optional[str] = None,
    file: Optional[UploadFile] = None,
) -> FileSource:
    """filepath / uri / 첨부파일 중 주어진 하나를 처리 대상으로 만든다."""
    given = [
        name
        for name, value in (("filepath", filepath), ("uri", uri), ("file", file))
        if value
    ]
    if not given:
        raise RequiredFieldError("filepath | uri | file", result=None)
    if len(given) > 1:
        raise ValidationError(
            msg("drm.target_conflict") + f" (지정됨: {', '.join(given)})"
        )

    if filepath:
        return LocalFileSource(filepath, runtime.local)
    if uri:
        return ObjectStorageSource(uri, runtime.storage)
    return UploadFileSource(file, runtime.max_upload_bytes)


def _resolve_response_mode(runtime: DrmRuntime, requested: Optional[str]) -> str:
    mode = (requested or runtime.drm.upload_response or RESPONSE_FILE).lower()
    if mode not in (RESPONSE_FILE, RESPONSE_JSON):
        raise ValidationError(
            f"response 는 '{RESPONSE_FILE}' 또는 '{RESPONSE_JSON}' 이어야 합니다: {mode}"
        )
    return mode


def _success_message(op_name: str, source: FileSource, ok: bool) -> str:
    if op_name == "check":
        key = "drm.check_encrypted" if ok else "drm.check_plain"
    else:
        key = f"drm.{op_name}_ok"
    return msg(key, filename=source.filename)


async def run_operation(
    runtime: DrmRuntime,
    op_name: str,
    source: FileSource,
    response_mode: Optional[str] = None,
) -> Union[ApiResponse, FileResponse]:
    """대상 준비 → 도메인 호출 → 결과 반영까지의 공통 처리."""
    operation = OPERATIONS[op_name]
    mode = _resolve_response_mode(runtime, response_mode)
    started = time.perf_counter()

    workspace = Workspace(runtime.drm.work_dir)
    keep_workspace = False
    logger.info(
        "%s 요청: source=%s location=%s", op_name, source.kind, source.location
    )
    try:
        work_path = await source.materialize(workspace, for_write=operation.writes)
        ok = await runtime.domain.call(operation.name, work_path)

        if not ok and operation.failure is not None:
            logger.warning(
                "%s 실패(domain False): location=%s", op_name, source.location
            )
            raise operation.failure(
                message=None, result=source.describe()
            )

        if operation.writes:
            await source.commit(work_path)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        result = {
            "operation": op_name,
            "source": source.describe(),
            "size": _size_of(work_path),
            "elapsed_ms": elapsed_ms,
        }
        if op_name == "check":
            result["encrypted"] = ok

        logger.info(
            "%s 완료: location=%s result=%s (%.1fms)",
            op_name, source.location, ok, elapsed_ms,
        )

        # 첨부파일 요청이고 결과 파일을 돌려줘야 하면 파일로 응답한다.
        if (
            isinstance(source, UploadFileSource)
            and operation.writes
            and mode == RESPONSE_FILE
        ):
            keep_workspace = True
            return FileResponse(
                path=work_path,
                filename=source.filename,
                media_type=source.content_type,
                background=BackgroundTask(workspace.cleanup),
            )

        return ApiResponse.ok(
            result=result, message=_success_message(op_name, source, ok)
        )
    finally:
        if not keep_workspace:
            workspace.cleanup()


def _size_of(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size
    except OSError:
        return None
