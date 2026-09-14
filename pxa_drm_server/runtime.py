"""서버 런타임 구성요소(설정 + 도메인 모듈).

앱 기동 시 한 번 만들어 ``app.state.drm_runtime`` 에 담아 두고,
라우터는 의존성 주입으로 꺼내 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass

from pxa_common.fastapi import Request

from .config import (
    DrmConfig,
    LocalConfig,
    StorageConfig,
    get_drm_config,
    get_local_config,
    get_storage_config,
)
from .domain import DomainAdapter, load_domain_module


@dataclass
class DrmRuntime:
    drm: DrmConfig
    local: LocalConfig
    storage: StorageConfig
    domain: DomainAdapter

    @property
    def max_upload_bytes(self) -> int:
        size = self.drm.max_upload_size_mb
        return size * 1024 * 1024 if size and size > 0 else 0


def build_runtime() -> DrmRuntime:
    """설정을 읽고 domain_core 를 로드한다. 실패하면 기동을 중단한다."""
    drm = get_drm_config()
    return DrmRuntime(
        drm=drm,
        local=get_local_config(),
        storage=get_storage_config(),
        domain=DomainAdapter(load_domain_module(drm)),
    )


def get_runtime(request: Request) -> DrmRuntime:
    """라우터용 의존성."""
    return request.app.state.drm_runtime
