"""서버 로컬 경로(filepath) 대상.

기본값(in_place=False)은 작업본을 만들어 처리하고, 성공했을 때만
원본과 원자적으로 교체한다. 처리 중 실패해도 원본은 그대로 남는다.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from ..config import LocalConfig
from ..errors import PathNotAllowedError, StorageError, TargetNotFoundError
from ..workspace import Workspace
from .base import FileSource

logger = logging.getLogger("pxa")


class LocalFileSource(FileSource):
    kind = "local"

    def __init__(self, filepath: str, cfg: LocalConfig):
        self.cfg = cfg
        raw = (filepath or "").strip()
        if not raw:
            raise PathNotAllowedError("filepath 가 비어 있습니다.")
        self.path = Path(raw).expanduser()
        try:
            self.path = self.path.resolve()
        except OSError as exc:
            raise PathNotAllowedError(f"경로를 확인할 수 없습니다: {raw}") from exc
        self._check_allowed()

    def _check_allowed(self) -> None:
        """allowed_roots 가 설정되어 있으면 그 하위 경로만 허용한다."""
        roots = [r for r in self.cfg.allowed_roots if r]
        if not roots:
            return
        for root in roots:
            base = Path(root).expanduser().resolve()
            if self.path == base or base in self.path.parents:
                return
        raise PathNotAllowedError(
            f"허용되지 않은 경로입니다: {self.path} "
            f"(허용 루트: {', '.join(roots)})"
        )

    @property
    def location(self) -> str:
        return str(self.path)

    @property
    def filename(self) -> str:
        return self.path.name

    async def materialize(self, workspace: Workspace, for_write: bool = True) -> Path:
        if not self.path.is_file():
            raise TargetNotFoundError(f"파일을 찾을 수 없습니다: {self.path}")
        # 읽기 전용 작업(check)은 복사 없이 원본을 그대로 본다.
        if self.cfg.in_place or not for_write:
            return self.path
        work = workspace.path_for(self.path.name)
        shutil.copy2(self.path, work)
        return work

    async def commit(self, path: Path) -> None:
        if self.cfg.in_place or path == self.path:
            return
        # 같은 디렉토리에 임시 파일로 쓴 뒤 rename 해서 원자적으로 교체한다.
        target_dir = self.path.parent
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".pxa", dir=target_dir)
        tmp_path = Path(tmp_name)
        try:
            os.close(fd)
            shutil.copyfile(path, tmp_path)
            shutil.copystat(self.path, tmp_path)
            os.replace(tmp_path, self.path)
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise StorageError(f"결과 파일을 저장하지 못했습니다: {self.path} ({exc})") from exc
        logger.debug("로컬 파일 갱신: %s", self.path)
