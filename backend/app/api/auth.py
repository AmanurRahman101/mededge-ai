import asyncio
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, HTTPException, Request, Response
from pwdlib import PasswordHash
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.auth.email import enforce_cooldown, send_auth_mail
from app.auth.security import (
    client_key,
    cookie_name,
    digest,
    require_user,
    session_for,
    throttle,
    user_payload,
    utc,
    verify_request,
)
from app.store.db import AuthSession, AuthToken, AuthUser

router = APIRouter(prefix="/api/auth", tags=["authentication"])
password_hash = PasswordHash.recommended()
hash_gate = asyncio.Semaphore(2)
DUMMY_HASH = password_hash.hash("a sample password that is not used")


def canonical_email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError("Enter a valid email address.") from exc


class EmailBody(BaseModel):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return canonical_email(value)


class Registration(EmailBody):
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["patient", "doctor"]

    @field_validator("full_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter your name.")
        return value


class Login(EmailBody):
    password: str = Field(max_length=128)
    remember: bool = False


class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class VerifyBody(TokenBody):
    password: str = Field(max_length=128)


class ResetBody(TokenBody):
    password: str = Field(min_length=12, max_length=128)


class ChangeBody(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


async def hash_password(value: str) -> str:
    async with hash_gate:
        return await asyncio.to_thread(password_hash.hash, value)


async def verify_password(value: str, hashed: str) -> bool:
    async with hash_gate:
        return await asyncio.to_thread(password_hash.verify, value, hashed)


def get_by_email(request: Request, email: str) -> AuthUser | None:
    with request.app.state.db.session() as session:
        return session.exec(select(AuthUser).where(AuthUser.email == email)).first()


async def issue_mail(request: Request, user: AuthUser, kind: str) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + (
        timedelta(hours=24) if kind == "verify" else timedelta(minutes=30)
    )
    with request.app.state.db.session() as session:
        session.add(AuthToken(id=digest(token), user_id=user.id, kind=kind, expires_at=expires))
        session.commit()
    await send_auth_mail(request, user.email, token, kind)


@router.post("/register", status_code=202)
async def register(body: Registration, request: Request) -> dict:
    verify_request(request)
    throttle(request, "register-ip", client_key(request), 5, 3600)
    throttle(request, "register-email", body.email, 3, 3600)
    enforce_cooldown(request, body.email)
    hashed = await hash_password(body.password)
    user = AuthUser(
        id=uuid.uuid4().hex,
        email=body.email,
        full_name=body.full_name,
        password_hash=hashed,
        role=body.role,
        verified=False,
        created_at=datetime.now(UTC),
    )
    with request.app.state.db.session() as session:
        session.add(user)
        try:
            session.commit()
            session.refresh(user)
        except IntegrityError:
            session.rollback()
            return {
                "message": "If this address can be registered, "
                "check your email for a verification link."
            }
    await issue_mail(request, user, "verify")
    return {
        "message": "If this address can be registered, check your email for a verification link."
    }


@router.post("/login")
async def login(body: Login, request: Request, response: Response) -> dict:
    verify_request(request)
    throttle(request, "login-ip", client_key(request), 10, 60)
    throttle(request, "login-email", body.email, 10, 900)
    user = get_by_email(request, body.email)
    valid = await verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.verified:
        raise HTTPException(status_code=403, detail="Please verify your email before signing in.")
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    max_age = int(
        timedelta(days=30 if body.remember else 0, hours=0 if body.remember else 12).total_seconds()
    )
    with request.app.state.db.session() as session:
        session.add(
            AuthSession(
                id=digest(token),
                user_id=user.id,
                csrf_token=csrf,
                expires_at=datetime.now(UTC) + timedelta(seconds=max_age),
            )
        )
        session.commit()
    response.set_cookie(
        cookie_name(request.app.state.settings),
        token,
        max_age=max_age if body.remember else None,
        httponly=True,
        secure=request.app.state.settings.app_env == "production",
        samesite="lax",
        path="/",
    )
    return {"user": user_payload(user), "csrf_token": csrf}


@router.get("/me")
async def me(request: Request) -> dict:
    found = session_for(request)
    if not found:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return {"user": user_payload(found[1]), "csrf_token": found[0].csrf_token}


def consume_token(session, token: str, kind: str) -> str:
    now = datetime.now(UTC)
    stmt = (
        update(AuthToken)
        .where(
            AuthToken.id == digest(token),
            AuthToken.kind == kind,
            AuthToken.consumed_at.is_(None),
            AuthToken.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(AuthToken.user_id)
    )
    user_id = session.exec(stmt).scalar_one_or_none()
    if not user_id:
        raise HTTPException(
            status_code=400, detail="This link has expired or has already been used."
        )
    return user_id


@router.post("/verify")
async def verify_email(body: VerifyBody, request: Request) -> dict:
    verify_request(request)
    throttle(request, "verify-ip", client_key(request), 20, 60)
    with request.app.state.db.session() as session:
        entry = session.get(AuthToken, digest(body.token))
        user = (
            session.get(AuthUser, entry.user_id)
            if entry
            and entry.kind == "verify"
            and not entry.consumed_at
            and utc(entry.expires_at) > datetime.now(UTC)
            else None
        )
    valid = await verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(
            status_code=400, detail="Invalid password or expired verification link."
        )
    with request.app.state.db.session() as session:
        user_id = consume_token(session, body.token, "verify")
        result = session.exec(
            update(AuthUser)
            .where(AuthUser.id == user_id, AuthUser.password_hash == user.password_hash)
            .values(verified=True)
            .returning(AuthUser.id)
        ).scalar_one_or_none()
        if not result:
            raise HTTPException(
                status_code=400, detail="This link has expired or has already been used."
            )
        session.commit()
    return {"message": "Your email is verified. You can now sign in."}


@router.post("/resend-verification", status_code=202)
async def resend(body: EmailBody, request: Request) -> dict:
    verify_request(request)
    throttle(request, "resend-ip", client_key(request), 10, 3600)
    throttle(request, "resend-recipient", body.email, 3, 3600)
    enforce_cooldown(request, body.email)
    user = get_by_email(request, body.email)
    if user and not user.verified:
        await issue_mail(request, user, "verify")
    return {"message": "If this account needs verification, an email will be sent."}


@router.post("/forgot-password", status_code=202)
async def forgot(body: EmailBody, request: Request) -> dict:
    verify_request(request)
    throttle(request, "forgot-ip", client_key(request), 10, 3600)
    throttle(request, "forgot-recipient", body.email, 3, 3600)
    enforce_cooldown(request, body.email)
    user = get_by_email(request, body.email)
    if user:
        await issue_mail(request, user, "reset")
    return {"message": "If an account exists, a password reset email will be sent."}


@router.post("/reset-password")
async def reset(body: ResetBody, request: Request) -> dict:
    verify_request(request)
    throttle(request, "reset-ip", client_key(request), 10, 60)
    hashed = await hash_password(body.password)
    with request.app.state.db.session() as session:
        user_id = consume_token(session, body.token, "reset")
        user = session.get(AuthUser, user_id)
        if not user:
            raise HTTPException(
                status_code=400, detail="This link has expired or has already been used."
            )
        user.password_hash = hashed
        session.add(user)
        session.exec(delete(AuthSession).where(AuthSession.user_id == user_id))
        session.exec(
            update(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.kind == "reset",
                AuthToken.consumed_at.is_(None),
            )
            .values(consumed_at=datetime.now(UTC))
        )
        session.commit()
    return {"message": "Your password has been changed. Please sign in."}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    verify_request(request)
    found = session_for(request)
    if found:
        with request.app.state.db.session() as session:
            row = session.get(AuthSession, found[0].id)
            if row:
                session.delete(row)
                session.commit()
    response.delete_cookie(
        cookie_name(request.app.state.settings),
        path="/",
        secure=request.app.state.settings.app_env == "production",
        httponly=True,
        samesite="lax",
    )
    return {"message": "Signed out."}


@router.post("/logout-all")
async def logout_all(request: Request, response: Response) -> dict:
    verify_request(request)
    user = require_user(request)
    with request.app.state.db.session() as session:
        session.exec(delete(AuthSession).where(AuthSession.user_id == user.id))
        session.commit()
    response.delete_cookie(
        cookie_name(request.app.state.settings),
        path="/",
        secure=request.app.state.settings.app_env == "production",
        httponly=True,
        samesite="lax",
    )
    return {"message": "Signed out on all devices."}


@router.post("/change-password")
async def change_password(body: ChangeBody, request: Request, response: Response) -> dict:
    verify_request(request)
    user = require_user(request)
    throttle(request, "change-password", user.id, 10, 900)
    if not await verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    hashed = await hash_password(body.new_password)
    with request.app.state.db.session() as session:
        current = session.get(AuthUser, user.id)
        current.password_hash = hashed
        session.add(current)
        session.exec(delete(AuthSession).where(AuthSession.user_id == user.id))
        session.commit()
    response.delete_cookie(
        cookie_name(request.app.state.settings),
        path="/",
        secure=request.app.state.settings.app_env == "production",
        httponly=True,
        samesite="lax",
    )
    return {"message": "Your password has been changed. Please sign in again."}
