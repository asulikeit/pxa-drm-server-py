"""테스트 공통 픽스처."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from pxa_common import reload_config
from pxa_common.fastapi import TestClient

ROOT = Path(__file__).resolve().parents[1]


def _deep_merge(base: dict, extra: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """설정을 덮어쓴 TestClient 를 만든다."""
    # 실행 환경의 PXA_* 환경변수가 테스트 설정을 덮지 않도록 지운다.
    for key in [k for k in list(__import__("os").environ) if k.startswith("PXA_")]:
        monkeypatch.delenv(key, raising=False)

    def _make(**overrides):
        config = {
            "app": {"name": "pxa-drm-test", "debug": True},
            "logging": {"dir": str(tmp_path / "logs"), "level": "DEBUG"},
            "drm": {
                "domain_file": str(ROOT / "domain_core.py"),
                "work_dir": str(tmp_path / "work"),
                "max_upload_size_mb": 8,
            },
            "local": {"allowed_roots": [], "in_place": False},
            "storage": {
                "buckets": {
                    "ABC": {
                        "bucket": "abc-bucket",
                        "endpoint_url": "https://s3.test.local",
                        "access_key": "test-key",
                        "secret_key": "test-secret",
                    }
                }
            },
        }
        config = _deep_merge(config, overrides)
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
        reload_config(str(config_path))

        from pxa_drm_server import create_app

        return TestClient(create_app())

    return _make


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def sample_file(tmp_path):
    path = tmp_path / "file.docx"
    path.write_bytes(b"hello pxa drm \x00\x01\x02")
    return path
