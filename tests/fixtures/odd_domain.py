"""계약을 지키지 않는 도메인 모듈(오류 응답 테스트용)."""


def encrypt(filepath: str):
    raise RuntimeError("암호화 모듈 연결 실패")


def decrypt(filepath: str):
    return "yes"        # bool 이 아님 -> pxa-21005


# check() 는 일부러 구현하지 않는다 -> pxa-21004
