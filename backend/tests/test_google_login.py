"""동국대 계정(Google) 로그인. 실제 Google 검증은 가짜로 바꾼다."""

import jwt
import pytest

from app.core.config import settings
from app.features.auth import google


@pytest.fixture
def fake_google(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    claims: dict = {}

    def verify(credential: str) -> dict:
        if credential == "bad":
            raise jwt.InvalidSignatureError("bad")
        return claims

    monkeypatch.setattr(google, "verify_credential", verify)
    return claims


def school(email="new@dgu.ac.kr", name="새 학생", **kw):
    return {"email": email, "name": name, "hd": "dgu.ac.kr", "email_verified": True, **kw}


def test_config_off_by_default(client):
    assert client.get("/api/v1/auth/google/config").json()["client_id"] == ""
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).status_code == 503


def test_first_login_creates_account(client, fake_google):
    fake_google.update(school())
    r = client.post("/api/v1/auth/google", json={"credential": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "new@dgu.ac.kr"
    assert client.get("/api/v1/auth/me").json()["name"] == "새 학생"
    # 비밀번호가 없는 계정이라 비밀번호 로그인은 안 된다
    client.post("/api/v1/auth/logout")
    r = client.post("/api/v1/auth/login", json={"email": "new@dgu.ac.kr", "password": ""})
    assert r.status_code in (401, 422)


def test_links_existing_account(client, session, fake_google):
    from app.models import User

    u = User(email="me@dgu.ac.kr", name="민제", password_hash="x")
    session.add(u)
    session.commit()
    fake_google.update(school("ME@dgu.ac.kr", "Google 이름"))
    r = client.post("/api/v1/auth/google", json={"credential": "x"})
    assert r.json()["id"] == u.id and r.json()["name"] == "민제"


def test_admin_emails(client, fake_google, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", " Boss@dgu.ac.kr , x@dgu.ac.kr")
    fake_google.update(school("boss@dgu.ac.kr"))
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).json()["role"] == "admin"
    fake_google.update(school("student@dgu.ac.kr"))
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).json()["role"] == "user"


def test_email_signup_closed_when_school_login_on(client, fake_google):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "a@dgu.ac.kr", "name": "a", "password": "password123"},
    )
    assert r.status_code == 403


@pytest.mark.parametrize(
    "claims",
    [
        {"email": "a@gmail.com", "name": "a", "email_verified": True},  # 개인 Gmail
        school("a@other.ac.kr", hd="other.ac.kr"),  # 다른 학교
        school(email_verified=False),
    ],
)
def test_rejects_non_school(client, fake_google, claims):
    fake_google.update(claims)
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 401


def test_rejects_invalid_token(client, fake_google):
    assert client.post("/api/v1/auth/google", json={"credential": "bad"}).status_code == 401


def test_verify_credential_checks_real_signature(monkeypatch):
    """실제 RS256 서명 검증 경로(암호화 라이브러리 포함). Google 키 대신 테스트용 키를 쓴다."""
    import time
    from types import SimpleNamespace

    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(
        google._jwks,
        "get_signing_key_from_jwt",
        lambda token: SimpleNamespace(key=key.public_key()),
    )
    now = int(time.time())
    claims = {
        **school(),
        "aud": "test-client",
        "iss": "https://accounts.google.com",
        "iat": now,
        "exp": now + 600,
    }
    assert (
        google.verify_credential(jwt.encode(claims, key, algorithm="RS256"))["email"]
        == "new@dgu.ac.kr"
    )
    with pytest.raises(jwt.PyJWTError):  # 다른 키로 서명(위조)
        google.verify_credential(jwt.encode(claims, other, algorithm="RS256"))
    with pytest.raises(jwt.PyJWTError):  # 다른 앱용 토큰
        google.verify_credential(jwt.encode({**claims, "aud": "x"}, key, algorithm="RS256"))


def test_school_login_without_google_name_uses_email_id(client, fake_google):
    fake_google.update(school("2022113582@dgu.ac.kr", name="  "))
    assert (
        client.post("/api/v1/auth/google", json={"credential": "x"}).json()["name"] == "2022113582"
    )
