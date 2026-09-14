"""처리 대상(파일) 추상화.

로컬 경로 / 오브젝트 스토리지 / 첨부파일 어느 쪽이든 서버는 동일하게 다룬다.

    1) materialize(workspace, for_write) : 로컬 파일로 만들어 준다 -> domain_core 에 넘길 경로
    2) commit(path)                      : 성공 시 결과를 원래 위치로 되돌린다
"""
from __future__ import annotations

import abc
from pathlib import Path

from ..workspace import Workspace


class FileSource(abc.ABC):
    """처리 대상 하나."""

    #: "local" | "objectstorage" | "upload"
    kind: str = "unknown"

    @property
    @abc.abstractmethod
    def location(self) -> str:
        """로그/응답에 남길 원본 위치 표기."""

    @property
    @abc.abstractmethod
    def filename(self) -> str:
        """원본 파일명."""

    @abc.abstractmethod
    async def materialize(self, workspace: Workspace, for_write: bool = True) -> Path:
        """도메인에 넘길 로컬 파일 경로를 준비한다.

        for_write=False 는 결과를 되돌리지 않는 읽기 전용 작업(check)이다.
        """

    async def commit(self, path: Path) -> None:
        """도메인 처리 결과를 원래 위치에 반영한다(기본: 아무것도 안 함)."""

    def describe(self) -> dict:
        return {"type": self.kind, "location": self.location, "filename": self.filename}
