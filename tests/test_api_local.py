"""filepath(서버 로컬 경로) API 테스트."""
from __future__ import annotations

from pathlib import Path

ODD_DOMAIN = Path(__file__).parent / "fixtures" / "odd_domain.py"

ORIGINAL = b"hello pxa drm \x00\x01\x02"


def test_health(client):
    body = client.get("/api/v1/health").json()
    assert body["success"] is True
    assert body["code"] == "pxa-10000"
    assert body["result"]["domain"] == {"encrypt": True, "decrypt": True, "check": True}
    assert body["result"]["buckets"] == ["abc"]   # 별칭은 소문자로 정규화된다


def test_encrypt_then_decrypt_roundtrip(client, sample_file):
    res = client.get("/api/v1/encrypt", params={"filepath": str(sample_file)}).json()
    assert res["success"] is True
    assert res["code"] == "pxa-10000"
    assert res["result"]["operation"] == "encrypt"
    assert res["result"]["source"]["type"] == "local"
    assert sample_file.read_bytes() != ORIGINAL

    checked = client.get("/api/v1/check", params={"filepath": str(sample_file)}).json()
    assert checked["success"] is True
    assert checked["result"]["encrypted"] is True

    res = client.get("/api/v1/decrypt", params={"filepath": str(sample_file)}).json()
    assert res["success"] is True
    assert sample_file.read_bytes() == ORIGINAL

    checked = client.get("/api/v1/check", params={"filepath": str(sample_file)}).json()
    assert checked["result"]["encrypted"] is False


def test_post_with_filepath_also_works(client, sample_file):
    res = client.post("/api/v1/encrypt", params={"filepath": str(sample_file)}).json()
    assert res["success"] is True
    assert sample_file.read_bytes().startswith(b"PXADRM01")


def test_encrypt_twice_returns_domain_failure(client, sample_file):
    client.get("/api/v1/encrypt", params={"filepath": str(sample_file)})
    encrypted = sample_file.read_bytes()

    res = client.get("/api/v1/encrypt", params={"filepath": str(sample_file)})
    body = res.json()
    assert res.status_code == 200          # HTTP 는 항상 200
    assert body["success"] is False
    assert body["code"] == "pxa-21001"
    assert sample_file.read_bytes() == encrypted   # 원본 보존


def test_decrypt_plain_file_returns_domain_failure(client, sample_file):
    body = client.get("/api/v1/decrypt", params={"filepath": str(sample_file)}).json()
    assert body["code"] == "pxa-21002"
    assert sample_file.read_bytes() == ORIGINAL


def test_target_required(client):
    body = client.get("/api/v1/encrypt").json()
    assert body["success"] is False
    assert body["code"] == "pxa-20002"


def test_target_conflict(client, sample_file):
    body = client.get(
        "/api/v1/encrypt",
        params={"filepath": str(sample_file), "uri": "ABC:a/b.docx"},
    ).json()
    assert body["code"] == "pxa-20001"


def test_file_not_found(client, tmp_path):
    body = client.get(
        "/api/v1/encrypt", params={"filepath": str(tmp_path / "없는파일.docx")}
    ).json()
    assert body["code"] == "pxa-22001"


def test_allowed_roots_blocks_outside_path(make_client, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "file.docx"
    inside.write_bytes(ORIGINAL)
    outside = tmp_path / "outside.docx"
    outside.write_bytes(ORIGINAL)

    client = make_client(local={"allowed_roots": [str(allowed)]})

    assert client.get("/api/v1/encrypt", params={"filepath": str(inside)}).json()["success"]
    blocked = client.get("/api/v1/encrypt", params={"filepath": str(outside)}).json()
    assert blocked["code"] == "pxa-22002"
    assert outside.read_bytes() == ORIGINAL


def test_odd_domain_module_is_reported_as_standard_errors(make_client, tmp_path):
    target = tmp_path / "file.docx"
    target.write_bytes(ORIGINAL)
    client = make_client(drm={"domain_file": str(ODD_DOMAIN)})

    body = client.get("/api/v1/encrypt", params={"filepath": str(target)}).json()
    assert body["code"] == "pxa-21003"
    assert target.read_bytes() == ORIGINAL          # 실패 시 원본 그대로

    body = client.get("/api/v1/decrypt", params={"filepath": str(target)}).json()
    assert body["code"] == "pxa-21005"              # bool 이 아닌 반환값

    body = client.get("/api/v1/check", params={"filepath": str(target)}).json()
    assert body["code"] == "pxa-21004"              # check() 미구현
