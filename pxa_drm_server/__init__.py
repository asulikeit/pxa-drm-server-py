"""pxa-drm-server — 파일 암복호화 API 서버.

개발자는 ``domain_core.py`` 에 세 함수만 구현하면 된다::

    def encrypt(filepath: str) -> bool: ...
    def decrypt(filepath: str) -> bool: ...
    def check(filepath: str) -> bool: ...

REST API / 로깅 / 에러처리 / 표준 응답 / 오브젝트 스토리지 입출력은
이 패키지가 pxa-common 위에서 처리한다.

    pxa-drm-server init      # 시작 템플릿 생성
    pxa-drm-server           # 서버 실행
"""
from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("pxa-drm-server")
except PackageNotFoundError:      # 설치 없이 소스에서 바로 쓰는 경우
    __version__ = "0.0.0.dev0"

# app 이 __version__ 을 쓰므로 버전을 정한 뒤에 import 한다.
from .app import create_app  # noqa: E402
from .codes import DrmCode  # noqa: E402

__all__ = ["create_app", "DrmCode", "__version__"]
