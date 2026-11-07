def test_signup_login_me_logout(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "Me@DGU.ac.kr", "name": "민제", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "me@dgu.ac.kr"
    assert client.get("/api/v1/auth/me").json()["name"] == "민제"

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401

    r = client.post("/api/v1/auth/login", json={"email": "me@dgu.ac.kr", "password": "password123"})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_duplicate_email_and_wrong_password(client, login):
    login("x@dgu.ac.kr")
    r = client.post(
        "/api/v1/auth/signup", json={"email": "x@dgu.ac.kr", "name": "n", "password": "password123"}
    )
    assert r.status_code == 409
    r = client.post("/api/v1/auth/login", json={"email": "x@dgu.ac.kr", "password": "wrongpass1"})
    assert r.status_code == 401


def test_short_password_rejected(client):
    r = client.post(
        "/api/v1/auth/signup", json={"email": "s@dgu.ac.kr", "name": "n", "password": "short"}
    )
    assert r.status_code == 422


def test_bad_token_rejected(client):
    client.cookies.set("access_token", "garbage")
    assert client.get("/api/v1/auth/me").status_code == 401
