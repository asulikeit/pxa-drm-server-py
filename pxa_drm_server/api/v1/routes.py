"""기본 제공 REST API (v1).

세 가지 작업(encrypt / decrypt / check)에 대해 각각 세 가지 대상 지정 방식을
지원한다. 라우터는 대상 해석과 실행을 service 에 위임하고 응답만 돌려준다.

    GET|POST /api/v1/encrypt?filepath=/download/file.docx
    GET|POST /api/v1/encrypt?uri=ABC:download/file.docx
    POST     /api/v1/encrypt   (multipart: file=@file.docx)
"""
from __future__ import annotations

from typing import Optional

from pxa_common import ApiResponse
from pxa_common.fastapi import APIRouter, Depends, File, Query, UploadFile

from ...runtime import DrmRuntime, get_runtime
from ...service import OPERATIONS, build_source, run_operation

router = APIRouter(prefix="/api/v1", tags=["drm"])

_SUMMARY = {
    "encrypt": "파일 암호화",
    "decrypt": "파일 복호화",
    "check": "파일 암호화 여부 확인",
}

_FILEPATH_DESC = "서버가 접근 가능한 파일 경로 (예: /download/file.docx)"
_URI_DESC = "오브젝트 스토리지 경로, '버킷별칭:오브젝트키' 형식 (예: ABC:download/file.docx)"
_RESPONSE_DESC = "첨부파일 요청의 응답 형식. file=결과 파일 다운로드, json=표준 JSON 응답"


def _register(operation: str) -> None:
    """작업 하나에 대한 GET/POST 엔드포인트를 등록한다."""
    summary = _SUMMARY[operation]

    @router.get(
        f"/{operation}",
        summary=f"{summary} (filepath / uri)",
        operation_id=f"{operation}_by_query",
        response_model=ApiResponse,
    )
    async def _by_query(
        filepath: Optional[str] = Query(None, description=_FILEPATH_DESC),
        uri: Optional[str] = Query(None, description=_URI_DESC),
        runtime: DrmRuntime = Depends(get_runtime),
    ):
        source = build_source(runtime, filepath=filepath, uri=uri)
        return await run_operation(runtime, operation, source)

    @router.post(
        f"/{operation}",
        summary=f"{summary} (filepath / uri / 첨부파일)",
        operation_id=f"{operation}_by_payload",
    )
    async def _by_payload(
        filepath: Optional[str] = Query(None, description=_FILEPATH_DESC),
        uri: Optional[str] = Query(None, description=_URI_DESC),
        response: Optional[str] = Query(None, description=_RESPONSE_DESC),
        file: Optional[UploadFile] = File(None, description="처리할 첨부파일"),
        runtime: DrmRuntime = Depends(get_runtime),
    ):
        source = build_source(runtime, filepath=filepath, uri=uri, file=file)
        return await run_operation(runtime, operation, source, response_mode=response)


for _operation_name in OPERATIONS:
    _register(_operation_name)


@router.get("/health", summary="상태 확인", response_model=ApiResponse)
async def health(runtime: DrmRuntime = Depends(get_runtime)):
    """서버와 도메인 모듈이 준비되었는지 확인한다."""
    return ApiResponse.ok(
        result={
            "status": "ok",
            "domain": {
                name: runtime.domain.has(name) for name in OPERATIONS
            },
            "buckets": sorted(runtime.storage.buckets),
        },
        message="서버가 정상 동작 중입니다.",
    )
