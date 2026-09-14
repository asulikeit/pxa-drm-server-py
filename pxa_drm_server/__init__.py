"""pxa-drm-server — 파일 암복호화 API 서버.

개발자는 ``domain_core.py`` 에 세 함수만 구현하면 된다::

    def encrypt(filepath: str) -> bool: ...
    def decrypt(filepath: str) -> bool: ...
    def check(filepath: str) -> bool: ...

REST API / 로깅 / 에러처리 / 표준 응답 / 오브젝트 스토리지 입출력은
이 패키지가 pxa-common 위에서 처리한다.
"""
from .app import create_app
from .codes import DrmCode

__version__ = "0.1.0"

__all__ = ["create_app", "DrmCode", "__version__"]
