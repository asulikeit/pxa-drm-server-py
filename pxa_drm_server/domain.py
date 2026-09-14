"""domain_core 로더 / 호출 어댑터.

서버는 기동 시 개발자가 작성한 ``domain_core`` 모듈을 읽어 들이고,
요청이 오면 ``encrypt(filepath)`` / ``decrypt(filepath)`` / ``check(filepath)``
를 호출한다. 개발자는 이 파일을 볼 필요가 없다.

- 동기 함수는 워커 스레드에서 실행해 이벤트 루프를 막지 않는다.
- ``async def`` 로 구현해도 그대로 동작한다.
- 반환값은 반드시 ``True`` / ``False`` 여야 한다.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from starlette.concurrency import run_in_threadpool

from .config import DrmConfig, get_drm_config
from .errors import DomainContractError, DomainError, DomainNotImplementedError

logger = logging.getLogger("pxa")

# 개발자가 구현해야 하는 함수. encrypt/decrypt 는 필수, check 는 선택이다.
REQUIRED_FUNCTIONS = ("encrypt", "decrypt")
OPTIONAL_FUNCTIONS = ("check",)


def _load_module_from_file(path: Path):
    """파일 경로에서 모듈을 직접 읽어 들인다(config: drm.domain_file)."""
    spec = importlib.util.spec_from_file_location("domain_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"도메인 파일을 읽을 수 없습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["domain_core"] = module
    spec.loader.exec_module(module)
    return module


def load_domain_module(cfg: Optional[DrmConfig] = None):
    """설정에 따라 domain_core 모듈을 로드하고 계약을 검증한다."""
    cfg = cfg or get_drm_config()

    if cfg.domain_file:
        path = Path(cfg.domain_file).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"drm.domain_file 경로에 파일이 없습니다: {path}")
        module = _load_module_from_file(path)
        origin = str(path)
    else:
        # 프로젝트 루트(실행 디렉토리)의 domain_core.py 도 찾을 수 있게 한다.
        cwd = str(Path.cwd())
        if cwd not in sys.path:
            sys.path.insert(0, cwd)
        try:
            module = importlib.import_module(cfg.domain_module)
        except ImportError as exc:
            raise RuntimeError(
                f"도메인 모듈 '{cfg.domain_module}' 을(를) 찾을 수 없습니다. "
                f"domain_core.py 를 만들거나 config 의 drm.domain_module / "
                f"drm.domain_file 을 확인하세요."
            ) from exc
        origin = getattr(module, "__file__", cfg.domain_module)

    missing = [n for n in REQUIRED_FUNCTIONS if not callable(getattr(module, n, None))]
    if missing:
        raise RuntimeError(
            f"도메인 모듈({origin})에 다음 함수가 없습니다: {', '.join(missing)}. "
            f"각 함수는 filepath 하나를 받아 True/False 를 반환해야 합니다."
        )
    for name in OPTIONAL_FUNCTIONS:
        if not callable(getattr(module, name, None)):
            logger.warning(
                "도메인 모듈에 %s() 가 없습니다. /api/v1/%s 호출 시 pxa-21004 로 응답합니다.",
                name, name,
            )

    logger.info("도메인 모듈 로드: %s", origin)
    return module


class DomainAdapter:
    """도메인 함수 호출을 감싸 예외/반환값을 표준 오류로 바꾼다."""

    def __init__(self, module: Any):
        self.module = module

    def has(self, name: str) -> bool:
        return callable(getattr(self.module, name, None))

    def _resolve(self, name: str) -> Callable[..., Any]:
        func = getattr(self.module, name, None)
        if not callable(func):
            raise DomainNotImplementedError(
                f"domain_core.{name}() 가 구현되어 있지 않습니다."
            )
        return func

    async def call(self, name: str, filepath: Path) -> bool:
        """domain_core.<name>(filepath) 를 호출하고 bool 을 돌려준다."""
        func = self._resolve(name)
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(str(filepath))
            else:
                result = await run_in_threadpool(func, str(filepath))
        except Exception as exc:  # 개발자 코드의 모든 예외를 표준 응답으로
            logger.exception("domain_core.%s() 실행 중 예외", name)
            raise DomainError(
                f"domain_core.{name}() 실행 중 오류가 발생했습니다: {exc}"
            ) from exc

        if not isinstance(result, bool):
            raise DomainContractError(
                f"domain_core.{name}() 는 True/False 를 반환해야 합니다 "
                f"(반환값 타입: {type(result).__name__})."
            )
        return result
