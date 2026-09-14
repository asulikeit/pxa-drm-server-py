"""ASGI 진입점.

    uvicorn pxa_drm_server.asgi:app --host 0.0.0.0 --port 8000

이 모듈을 import 하는 순간 설정을 읽고 domain_core 를 로드한다.
(CLI 가 이 모듈을 건드리지 않아야 ``pxa-drm-server init`` 이 domain_core 없이도 동작한다.)
"""
from __future__ import annotations

from .app import create_app

app = create_app()
