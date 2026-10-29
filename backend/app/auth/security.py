import hashlib
import hmac
import ipaddress
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import delete

from app.store.db import AuthCounter, AuthSession, AuthUser


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cookie_name(settings) -> str:
    return "__Host-mededge_session" if settings.app_env == "production" else "mededge_session"


def session_for(request):
    token = request.cookies.get(cookie_name(request.app.state.settings))
    if not token:
        return None
    with request.app.state.db.session() as session:
        row = session.get(AuthSession, digest(token))
        if not row or utc(row.expires_at) <= datetime.now(UTC):
            return None
        user = session.get(AuthUser, row.user_id)
        if not user or not user.verified:
            return None
        return row, user


def require_user(request):
    found = session_for(request)
    if not found:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return found[1]


def require_role(request, role: str):
    user = require_user(request)
    if user.role != role:
        raise HTTPException(status_code=403, detail="You do not have access to this action.")
    return user


def check_origin(request) -> None:
    settings = request.app.state.settings
    allowed = {settings.app_base_url.rstrip("/")}
    if settings.app_env != "production":
        allowed.update(s.rstrip("/") for s in settings.cors_origin_list)
    origin = request.headers.get("origin", "").rstrip("/")
    if not origin or origin not in allowed:
        raise HTTPException(status_code=403, detail="Invalid request origin.")


def verify_request(request: Request) -> None:
    """Protect state-changing browser requests, including an anonymous login."""
    check_origin(request)
    found = session_for(request)
    if found:
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not hmac.compare_digest(supplied, found[0].csrf_token):
            raise HTTPException(
                status_code=403, detail="Invalid security token. Refresh and retry."
            )


def throttle(request, scope: str, subject: str, limit: int, seconds: int) -> None:
    """Atomic fixed-window database counter, shared by all application instances."""
    from datetime import timedelta

    now = datetime.now(UTC)
    bucket = int(now.timestamp()) // seconds
    key = f"{scope}:{digest(subject)}:{bucket}"
    db = request.app.state.db
    with db.session() as session:
        dialect = db.engine.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        stmt = insert(AuthCounter).values(
            key=key, count=1, expires_at=now + timedelta(seconds=seconds * 2)
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"], set_={"count": AuthCounter.count + 1}
        )
        stmt = stmt.returning(AuthCounter.count)
        count = session.exec(stmt).one()[0]
        # Opportunistic, bounded cleanup; no periodic process or database keepalive.
        if int(now.timestamp()) % 97 == 0:
            session.exec(delete(AuthCounter).where(AuthCounter.expires_at < now))
        session.commit()
    if count > limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")


def client_key(request) -> str:
    # Render's public edge overwrites CF-Connecting-IP. Do not trust this
    # header for local or generic deployments where callers can forge it.
    settings = request.app.state.settings
    if settings.app_env == "production" and settings.trust_render_proxy:
        forwarded = request.headers.get("cf-connecting-ip", "")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


def user_payload(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "verified": user.verified,
    }
