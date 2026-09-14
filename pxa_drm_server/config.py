"""DRM 서버 설정.

pxa-common 의 설정 관리(``load_section``)를 그대로 사용한다.
우선순위는 **환경변수(PXA_*) > config.yaml > 기본값** 이며,
config 파일 경로는 환경변수 ``PXA_CONFIG`` 로 지정한다.

오브젝트 스토리지 접근키처럼 민감한 값은 파일에 두지 말고 환경변수로 넣는다::

    PXA_STORAGE__BUCKETS__ABC__ACCESS_KEY=...
    PXA_STORAGE__BUCKETS__ABC__SECRET_KEY=...
"""
from __future__ import annotations

from typing import Optional

from pxa_common import load_section
from pxa_common.fastapi import BaseModel, Field, model_validator


class DrmConfig(BaseModel):
    """domain_core 로딩과 작업 방식."""

    # 개발자가 구현한 모듈. 파일 경로(domain_file)를 주면 그쪽이 우선한다.
    domain_module: str = "domain_core"
    domain_file: Optional[str] = None
    # 임시 작업 디렉토리. 비우면 OS 임시 디렉토리를 쓴다.
    work_dir: Optional[str] = None
    # 첨부파일 업로드 허용 크기(MB). 0 이하면 제한 없음.
    max_upload_size_mb: int = 512
    # 첨부파일 요청의 기본 응답 형식: "file"(결과 파일 다운로드) 또는 "json".
    upload_response: str = "file"


class LocalConfig(BaseModel):
    """filepath(서버 로컬 경로) 처리 방식."""

    # 비우면 모든 경로를 허용한다. 지정하면 해당 디렉토리 하위만 허용한다.
    allowed_roots: list[str] = Field(default_factory=list)
    # True 면 원본 파일을 그대로 도메인에 넘긴다(제자리 처리).
    # False 면 작업본을 만들어 처리하고 성공 시에만 원자적으로 교체한다.
    in_place: bool = False


class BucketConfig(BaseModel):
    """S3 호환 오브젝트 스토리지 버킷 하나의 접근 정보."""

    bucket: str
    endpoint_url: Optional[str] = None
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    # MinIO/Ceph 등 S3 호환 스토리지는 보통 "path" 가 안전하다.
    addressing_style: str = "path"
    signature_version: Optional[str] = None
    verify_ssl: bool = True


class StorageConfig(BaseModel):
    """버킷 별칭 -> 접근 정보. uri 의 'ABC:key' 에서 ABC 가 별칭이다."""

    buckets: dict[str, BucketConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _merge_aliases(cls, data):
        """대소문자만 다른 별칭을 하나로 합친다.

        환경변수 override(PXA_STORAGE__BUCKETS__ABC__ACCESS_KEY)는 pxa-common 에서
        경로가 소문자로 변환되므로, config.yaml 의 'ABC' 와 환경변수의 'abc' 가
        따로 생긴다. 둘을 합쳐야 "키는 환경변수로" 라는 사용법이 성립한다.
        나중에 온 값(환경변수)이 이긴다.
        """
        if not isinstance(data, dict):
            return data
        buckets = data.get("buckets")
        if not isinstance(buckets, dict):
            return data
        merged: dict = {}
        for alias, value in buckets.items():
            key = str(alias).lower()
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return {**data, "buckets": merged}

    def resolve(self, alias: str) -> Optional[BucketConfig]:
        """버킷 별칭을 찾는다(대소문자 무시)."""
        return self.buckets.get(alias.lower())


def get_drm_config() -> DrmConfig:
    return load_section("drm", DrmConfig)


def get_local_config() -> LocalConfig:
    return load_section("local", LocalConfig)


def get_storage_config() -> StorageConfig:
    return load_section("storage", StorageConfig)
