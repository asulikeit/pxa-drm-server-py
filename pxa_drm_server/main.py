"""CLI 진입점.

    pxa-drm-server init      # domain_core.py / config/config.yaml 을 현재 위치에 만든다
    pxa-drm-server           # 서버 실행 (= pxa-drm-server run)
    python -m pxa_drm_server

호스트/포트는 config 의 ``server`` 섹션 또는 환경변수로 지정한다::

    PXA_SERVER__PORT=9000
"""
from __future__ import annotations

import argparse
import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Optional, Sequence

from pxa_common import load_section
from pxa_common.fastapi import BaseModel

#: init 이 만들어 주는 파일 — (템플릿 이름, 생성 경로)
_TEMPLATES = (
    ("domain_core.py", Path("domain_core.py")),
    ("config.yaml", Path("config") / "config.yaml"),
)


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False


def run() -> None:
    """설정을 읽어 uvicorn 으로 서버를 띄운다."""
    import uvicorn

    cfg = load_section("server", ServerConfig)
    uvicorn.run(
        "pxa_drm_server.asgi:app",
        host=cfg.host,
        port=cfg.port,
        workers=cfg.workers if not cfg.reload else 1,
        reload=cfg.reload,
        log_config=None,          # 로깅은 pxa-common setup_logging() 이 담당한다
    )


def init(target_dir: Path, force: bool = False) -> int:
    """시작 템플릿(domain_core.py, config/config.yaml)을 복사한다."""
    source_dir = resources.files("pxa_drm_server") / "templates"
    created, skipped = [], []

    for name, relative in _TEMPLATES:
        destination = target_dir / relative
        if destination.exists() and not force:
            skipped.append(destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with resources.as_file(source_dir / name) as template:
            shutil.copyfile(template, destination)
        created.append(destination)

    for path in created:
        print(f"생성: {path}")
    for path in skipped:
        print(f"건너뜀(이미 있음): {path}")

    if skipped and not created:
        print("\n덮어쓰려면 --force 를 붙이세요.")
        return 1

    print(
        "\n다음 순서로 진행하세요.\n"
        "  1) domain_core.py 의 encrypt/decrypt/check 를 실제 DRM 모듈 호출로 바꾼다\n"
        "  2) config/config.yaml 에서 로깅/버킷 설정을 맞춘다\n"
        "  3) PXA_CONFIG=config/config.yaml pxa-drm-server"
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """콘솔 스크립트 진입점."""
    parser = argparse.ArgumentParser(
        prog="pxa-drm-server",
        description="파일 암복호화 API 서버 (pxa-common 기반)",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="서버를 실행한다 (기본값)")
    init_parser = subparsers.add_parser(
        "init", help="domain_core.py 와 config/config.yaml 을 만든다"
    )
    init_parser.add_argument(
        "--dir", default=".", help="템플릿을 만들 디렉토리 (기본: 현재 위치)"
    )
    init_parser.add_argument(
        "--force", action="store_true", help="이미 있는 파일을 덮어쓴다"
    )

    args = parser.parse_args(argv)
    if args.command == "init":
        return init(Path(args.dir), force=args.force)

    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
