"""서버 실행 진입점.

    python -m pxa_drm_server            # 또는 pxa-drm-server
    uvicorn pxa_drm_server.main:app     # ASGI 서버로 직접 기동

호스트/포트는 config 의 ``server`` 섹션 또는 환경변수로 지정한다::

    PXA_SERVER__PORT=9000
"""
from __future__ import annotations

from pxa_common import load_section
from pxa_common.fastapi import BaseModel

from .app import create_app


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False


app = create_app()


def run() -> None:
    import uvicorn

    cfg = load_section("server", ServerConfig)
    uvicorn.run(
        "pxa_drm_server.main:app",
        host=cfg.host,
        port=cfg.port,
        workers=cfg.workers if not cfg.reload else 1,
        reload=cfg.reload,
        log_config=None,          # 로깅은 pxa-common setup_logging() 이 담당한다
    )


if __name__ == "__main__":
    run()
