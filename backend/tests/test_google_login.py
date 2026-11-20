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


def test_links_existing_account(login, client, fake_google):
    login("me@dgu.ac.kr", "민제")
    uid = client.get("/api/v1/auth/me").json()["id"]
    client.post("/api/v1/auth/logout")
    fake_google.update(school("ME@dgu.ac.kr", "Google 이름"))
    r = client.post("/api/v1/auth/google", json={"credential": "x"})
    assert r.json()["id"] == uid and r.json()["name"] == "민제"


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
