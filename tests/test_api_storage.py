"""uri(오브젝트 스토리지) API 테스트.

실제 S3 대신 로컬 디렉토리를 쓰는 가짜 클라이언트를 주입한다.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pxa_drm_server.sources import objectstorage
from pxa_drm_server.sources.objectstorage import parse_uri

ORIGINAL = b"object storage body \x10\x20"


class _FakeClientError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    """디렉토리를 버킷처럼 쓰는 최소 구현."""

    def __init__(self, root: Path):
        self.root = root

    def _object_path(self, bucket: str, key: str) -> Path:
        return self.root / bucket / key

    def head_object(self, Bucket: str, Key: str):
        path = self._object_path(Bucket, Key)
        if not path.is_file():
            raise _FakeClientError("404")
        return {"ContentType": "application/octet-stream", "ContentLength": path.stat().st_size}

    def download_file(self, bucket: str, key: str, target: str):
        path = self._object_path(bucket, key)
        if not path.is_file():
            raise _FakeClientError("NoSuchKey")
        shutil.copyfile(path, target)

    def upload_file(self, source: str, bucket: str, key: str, ExtraArgs=None):
        path = self._object_path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)


@pytest.fixture
def fake_bucket(tmp_path, monkeypatch):
    root = tmp_path / "s3"
    obj = root / "abc-bucket" / "download" / "file.docx"
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.write_bytes(ORIGINAL)
    monkeypatch.setattr(objectstorage, "_build_client", lambda alias, cfg: FakeS3(root))
    return obj


def test_encrypt_and_decrypt_object(client, fake_bucket):
    body = client.get(
        "/api/v1/encrypt", params={"uri": "ABC:download/file.docx"}
    ).json()
    assert body["success"] is True
    assert body["result"]["source"] == {
        "type": "objectstorage",
        "location": "ABC:download/file.docx",
        "filename": "file.docx",
        "bucket": "ABC",
        "key": "download/file.docx",
    }
    assert fake_bucket.read_bytes().startswith(b"PXADRM01")

    checked = client.get("/api/v1/check", params={"uri": "ABC:download/file.docx"}).json()
    assert checked["result"]["encrypted"] is True

    body = client.get("/api/v1/decrypt", params={"uri": "ABC:download/file.docx"}).json()
    assert body["success"] is True
    assert fake_bucket.read_bytes() == ORIGINAL


def test_leading_slash_and_s3_scheme(client, fake_bucket):
    assert client.get(
        "/api/v1/check", params={"uri": "ABC:/download/file.docx"}
    ).json()["success"] is True
    assert client.get(
        "/api/v1/check", params={"uri": "s3://ABC/download/file.docx"}
    ).json()["success"] is True


def test_object_not_found(client, fake_bucket):
    body = client.get("/api/v1/encrypt", params={"uri": "ABC:download/none.docx"}).json()
    assert body["code"] == "pxa-22001"


def test_unknown_bucket_alias(client, fake_bucket):
    body = client.get("/api/v1/encrypt", params={"uri": "ZZZ:download/file.docx"}).json()
    assert body["code"] == "pxa-22004"


def test_invalid_uri(client, fake_bucket):
    body = client.get("/api/v1/encrypt", params={"uri": "download/file.docx"}).json()
    assert body["code"] == "pxa-22003"


def test_failed_domain_does_not_upload(client, fake_bucket):
    body = client.get("/api/v1/decrypt", params={"uri": "ABC:download/file.docx"}).json()
    assert body["code"] == "pxa-21002"
    assert fake_bucket.read_bytes() == ORIGINAL


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("ABC:download/file.docx", ("ABC", "download/file.docx")),
        ("ABC:/download/file.docx", ("ABC", "download/file.docx")),
        ("s3://ABC/download/file.docx", ("ABC", "download/file.docx")),
        ("ABC:file.docx", ("ABC", "file.docx")),
    ],
)
def test_parse_uri(uri, expected):
    assert parse_uri(uri) == expected


@pytest.mark.parametrize("uri", ["", "ABC:", ":key", "download/file.docx", "ABC"])
def test_parse_uri_rejects_bad_input(uri):
    from pxa_drm_server.errors import InvalidUriError

    with pytest.raises(InvalidUriError):
        parse_uri(uri)


def test_bucket_alias_merges_case_variants():
    """환경변수 override(소문자)와 config.yaml(대문자) 별칭이 하나로 합쳐진다."""
    from pxa_drm_server.config import StorageConfig

    storage = StorageConfig(
        buckets={
            "ABC": {"bucket": "abc-bucket", "endpoint_url": "https://s3.test"},
            "abc": {"access_key": "from-env", "secret_key": "secret-from-env"},
        }
    )
    assert sorted(storage.buckets) == ["abc"]
    bucket = storage.resolve("ABC")
    assert bucket.bucket == "abc-bucket"
    assert bucket.endpoint_url == "https://s3.test"
    assert bucket.access_key == "from-env"      # 환경변수가 이긴다
    assert storage.resolve("AbC") is bucket
    assert storage.resolve("nope") is None
