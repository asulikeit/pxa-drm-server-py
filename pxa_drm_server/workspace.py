"""요청 단위 임시 작업 디렉토리.

원본을 직접 건드리지 않고 작업본을 만들어 처리하기 위한 공간이다.
요청이 끝나면(파일 응답이면 전송이 끝난 뒤) 통째로 지운다.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("pxa")


class Workspace:
    """요청 하나가 쓰는 임시 디렉토리."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            Path(base_dir).mkdir(parents=True, exist_ok=True)
        self.dir = Path(tempfile.mkdtemp(prefix="pxa-drm-", dir=base_dir or None))

    def path_for(self, filename: str) -> Path:
        """작업 디렉토리 안의 안전한 경로를 만든다(경로 요소는 파일명만 사용)."""
        safe = Path(filename).name or "file"
        return self.dir / safe

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc_info) -> None:
        self.cleanup()
