from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import (
    CurrentUser,
    clear_login_cookie,
    hash_password,
    set_login_cookie,
    verify_password,
)
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, session: SessionDep, response: Response) -> UserOut:
    email = body.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일입니다")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    set_login_cookie(response, user.id)
    return UserOut.model_validate(user, from_attributes=True)


@router.post("/login")
def login(body: LoginIn, session: SessionDep, response: Response) -> UserOut:
    user = session.exec(select(User).where(User.email == body.email.lower())).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 틀렸습니다")
    set_login_cookie(response, user.id)
    return UserOut.model_validate(user, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_login_cookie(response)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)
