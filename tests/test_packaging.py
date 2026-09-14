"""배포(PyPI) 구성 검증."""
from __future__ import annotations

import subprocess
import sys
import tomllib
from importlib import resources
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PAIRS = (
    ("domain_core.py", ROOT / "domain_core.py"),
    ("config.yaml", ROOT / "config" / "config.yaml"),
)


@pytest.mark.parametrize("template_name, repo_file", TEMPLATE_PAIRS)
def test_templates_match_repo_files(template_name, repo_file):
    """패키지에 담기는 템플릿과 저장소 루트 파일이 어긋나지 않아야 한다."""
    packaged = (resources.files("pxa_drm_server") / "templates" / template_name).read_text(
        encoding="utf-8"
    )
    assert packaged == repo_file.read_text(encoding="utf-8"), (
        f"{repo_file} 를 고쳤다면 pxa_drm_server/templates/{template_name} 도 맞춰야 합니다."
    )


def test_version_matches_pyproject():
    import pxa_drm_server

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pxa_drm_server.__version__ == pyproject["project"]["version"]


def test_init_creates_starter_files(tmp_path):
    from pxa_drm_server.main import init

    assert init(tmp_path) == 0
    assert (tmp_path / "domain_core.py").is_file()
    assert (tmp_path / "config" / "config.yaml").is_file()

    # 기존 파일은 덮어쓰지 않는다.
    (tmp_path / "domain_core.py").write_text("# 사용자가 고친 코드\n", encoding="utf-8")
    assert init(tmp_path) == 1
    assert (tmp_path / "domain_core.py").read_text(encoding="utf-8") == "# 사용자가 고친 코드\n"

    # --force 면 덮어쓴다.
    assert init(tmp_path, force=True) == 0
    assert "def encrypt" in (tmp_path / "domain_core.py").read_text(encoding="utf-8")


def test_cli_help_works_without_domain_core(tmp_path):
    """domain_core.py 가 없는 디렉토리에서도 CLI 가 동작해야 한다."""
    result = subprocess.run(
        [sys.executable, "-m", "pxa_drm_server", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "init" in result.stdout
