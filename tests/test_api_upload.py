"""첨부파일(multipart) API 테스트."""
from __future__ import annotations

ORIGINAL = b"attached document body \x00\xff"
MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_upload_encrypt_returns_result_file(client):
    res = client.post(
        "/api/v1/encrypt", files={"file": ("file.docx", ORIGINAL, MIME)}
    )
    assert res.status_code == 200
    assert res.content.startswith(b"PXADRM01")
    assert "file.docx" in res.headers["content-disposition"]


def test_upload_roundtrip_returns_original_bytes(client):
    encrypted = client.post(
        "/api/v1/encrypt", files={"file": ("file.docx", ORIGINAL, MIME)}
    ).content
    decrypted = client.post(
        "/api/v1/decrypt", files={"file": ("file.docx", encrypted, MIME)}
    ).content
    assert decrypted == ORIGINAL


def test_upload_json_response_mode(client):
    body = client.post(
        "/api/v1/encrypt",
        params={"response": "json"},
        files={"file": ("file.docx", ORIGINAL, MIME)},
    ).json()
    assert body["success"] is True
    assert body["result"]["source"]["type"] == "upload"
    assert body["result"]["source"]["filename"] == "file.docx"
    assert body["result"]["size"] == len(ORIGINAL) + len(b"PXADRM01")


def test_upload_check_always_returns_json(client):
    body = client.post(
        "/api/v1/check", files={"file": ("file.docx", ORIGINAL, MIME)}
    ).json()
    assert body["success"] is True
    assert body["result"]["encrypted"] is False


def test_upload_domain_failure_is_standard_error(client):
    encrypted = client.post(
        "/api/v1/encrypt", files={"file": ("file.docx", ORIGINAL, MIME)}
    ).content
    body = client.post(
        "/api/v1/encrypt", files={"file": ("file.docx", encrypted, MIME)}
    ).json()
    assert body["success"] is False
    assert body["code"] == "pxa-21001"


def test_upload_too_large(make_client):
    client = make_client(drm={"max_upload_size_mb": 1})
    body = client.post(
        "/api/v1/encrypt", files={"file": ("big.bin", b"x" * (2 * 1024 * 1024))}
    ).json()
    assert body["code"] == "pxa-22007"


def test_upload_empty_file(client):
    body = client.post("/api/v1/encrypt", files={"file": ("empty.docx", b"")}).json()
    assert body["code"] == "pxa-22006"


def test_invalid_response_mode(client):
    body = client.post(
        "/api/v1/encrypt",
        params={"response": "xml"},
        files={"file": ("file.docx", ORIGINAL, MIME)},
    ).json()
    assert body["code"] == "pxa-20001"
