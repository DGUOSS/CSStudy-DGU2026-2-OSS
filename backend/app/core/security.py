"""로그인 관련 공통 코드. 로그인한 사용자는 반드시 CurrentUser(get_current_user)로만 얻는다."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Response, status
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.db import SessionDep
from app.models import User

COOKIE_NAME = "access_token"
_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _hasher.verify(password, hashed)


def create_token(user_id: int) -> str:
    exp = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, algorithm="HS256")


def set_login_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_token(user_id),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_hours * 3600,
    )


def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def get_current_user(
    session: SessionDep, access_token: Annotated[str | None, Cookie()] = None
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다")
    if not access_token:
        raise unauthorized
    try:
        payload = jwt.decode(access_token, settings.jwt_secret, algorithms=["HS256"])
        user = session.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자만 할 수 있습니다")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
