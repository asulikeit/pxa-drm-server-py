"""FastAPI 앱 팩토리.

pxa-common 이 제공하는 기반(설정 / 로깅 / 표준응답 / 예외처리 / 메시지)을
한자리에서 조립한다. 개발자는 ``domain_core.py`` 만 작성하면 되고
이 파일을 수정할 일은 없다.

    from pxa_drm_server import create_app
    app = create_app()
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from pxa_common import (
    RequestLoggingMiddleware,
    get_app_config,
    get_messages_config,
    load_message_files,
    register_exception_handlers,
    register_messages,
    setup_logging,
)
from pxa_common.fastapi import FastAPI

from .api.v1 import router as v1_router
from .runtime import build_runtime

__all__ = ["create_app"]

_MESSAGE_FILE = Path(__file__).parent / "messages" / "drm.yaml"

logger = logging.getLogger("pxa")


def _load_messages() -> None:
    """서버 기본 메시지 -> 애플리케이션 메시지(config) 순으로 등록한다."""
    if _MESSAGE_FILE.is_file():
        data = yaml.safe_load(_MESSAGE_FILE.read_text(encoding="utf-8")) or {}
        register_messages(data)
    files = get_messages_config().files
    if files:
        load_message_files(files)


def create_app() -> FastAPI:
    """DRM 서버 앱을 만든다."""
    setup_logging()
    _load_messages()

    app_cfg = get_app_config()
    runtime = build_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "%s 기동 완료 (debug=%s, buckets=%s)",
            app_cfg.name, app_cfg.debug, sorted(runtime.storage.buckets) or "없음",
        )
        yield
        logger.info("%s 종료", app_cfg.name)

    app = FastAPI(
        title=app_cfg.name,
        description="파일 암복호화 API 서버 (pxa-common 기반)",
        version="0.1.0",
        debug=app_cfg.debug,
        lifespan=lifespan,
    )

    # 요청 로깅(request-id + 처리시간) / 표준 예외 처리
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    app.state.drm_runtime = runtime
    app.include_router(v1_router)
    return app
