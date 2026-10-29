import html
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException

from app.auth.security import digest
from app.store.db import AuthCounter


def enforce_cooldown(request, address: str) -> None:
    """Enforce the same recipient cooldown for known and unknown accounts."""
    now = datetime.now(UTC)
    db = request.app.state.db
    if db.engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    with db.session() as session:
        cooldown = insert(AuthCounter).values(
            key=f"mail:cooldown:{digest(address)}", count=1, expires_at=now + timedelta(seconds=60)
        )
        cooldown = cooldown.on_conflict_do_update(
            index_elements=["key"],
            set_={"expires_at": now + timedelta(seconds=60)},
            where=AuthCounter.expires_at <= now,
        ).returning(AuthCounter.key)
        if session.exec(cooldown).first() is None:
            session.rollback()
            raise HTTPException(
                status_code=429, detail="Please wait before requesting another email."
            )
        session.commit()


def _reserve(request, address: str) -> None:
    """Atomically reserve daily, monthly and hourly-recipient quotas."""
    now = datetime.now(UTC)
    settings = request.app.state.settings
    email_id = digest(address)
    quotas = [
        (f"mail:day:{now:%Y-%m-%d}", settings.auth_email_daily_limit, timedelta(days=2)),
        (f"mail:month:{now:%Y-%m}", settings.auth_email_monthly_limit, timedelta(days=62)),
        (f"mail:hour:{email_id}:{now:%Y-%m-%d-%H}", 3, timedelta(hours=2)),
    ]
    db = request.app.state.db
    if db.engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    with db.session() as session:
        for key, limit, lifetime in quotas:
            stmt = insert(AuthCounter).values(key=key, count=1, expires_at=now + lifetime)
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"], set_={"count": AuthCounter.count + 1}
            ).returning(AuthCounter.count)
            if session.exec(stmt).one()[0] > limit:
                session.rollback()
                raise HTTPException(
                    status_code=429, detail="Please wait before requesting another email."
                )
        session.commit()


async def send_auth_mail(request, address: str, token: str, kind: str) -> None:
    settings = request.app.state.settings
    _reserve(request, address)
    route = "verify-email" if kind == "verify" else "reset-password"
    title = "Verify your email" if kind == "verify" else "Reset your password"
    link = f"{settings.app_base_url.rstrip('/')}/{route}#token={token}"
    plain = (
        f"{title}\n\nOpen this link to continue:\n{link}\n\n"
        "If you did not request this, you can ignore this message.\n"
    )
    body = (
        f'<p>{html.escape(title)}</p><p><a href="{html.escape(link, quote=True)}">'
        "Continue securely</a></p>"
        "<p>If you did not request this, you can ignore this message.</p>"
    )
    if settings.app_env != "production" and not settings.resend_api_key:
        folder = request.app.state.db.runs_dir.parent / "mail"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{secrets.token_hex(16)}.eml"
        with path.open("x", encoding="utf-8") as file:
            file.write(f"To: {address}\nSubject: MedEdge AI: {title}\n\n{plain}")
        return
    if not settings.resend_api_key or not settings.resend_from_email:
        raise HTTPException(status_code=503, detail="Email delivery is temporarily unavailable.")
    try:
        result = await request.app.state.http.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                "Idempotency-Key": digest(token),
            },
            json={
                "from": settings.resend_from_email,
                "to": [address],
                "subject": f"MedEdge AI: {title}",
                "text": plain,
                "html": body,
            },
            timeout=10.0,
        )
        if not result.is_success:
            raise HTTPException(
                status_code=503, detail="Email delivery is temporarily unavailable."
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Email delivery is temporarily unavailable."
        ) from exc
