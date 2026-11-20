"""동국대 계정 로그인. 동국대 메일(dgu.ac.kr)은 Google 워크스페이스라서 Google 로그인으로 학교 계정을 확인한다.

브라우저가 Google에서 받은 ID 토큰을 서버가 Google 공개키로 검증하고, 학교 도메인 계정인지 본다.
"""

import jwt

from app.core.config import settings

GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_jwks = jwt.PyJWKClient(GOOGLE_CERTS, cache_keys=True)


class NotSchoolAccount(Exception):
    """검증은 됐지만 동국대 계정이 아니다."""


def verify_credential(credential: str) -> dict:
    """Google ID 토큰을 검증해 claims를 돌려준다. 위조·만료·다른 앱용이면 jwt.PyJWTError."""
    key = _jwks.get_signing_key_from_jwt(credential).key
    return jwt.decode(
        credential,
        key,
        algorithms=["RS256"],
        audience=settings.google_client_id,
        issuer=GOOGLE_ISSUERS,
    )


def school_identity(claims: dict) -> tuple[str, str]:
    """학교 계정이면 (이메일, 이름). 아니면 NotSchoolAccount."""
    domain = settings.school_email_domain
    email = str(claims.get("email", "")).lower()
    # hd는 워크스페이스 계정에만 붙는다. 개인 Gmail에는 없다
    if (
        claims.get("hd") != domain
        or not email.endswith("@" + domain)
        or claims.get("email_verified") is not True
    ):
        raise NotSchoolAccount
    name = (str(claims.get("name") or "").strip() or email.split("@")[0])[:50]
    return email, name
