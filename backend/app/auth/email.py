# ruff: noqa: E501 -- Inline styles keep the transactional email compatible with mail clients.
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


DISCLAIMER = (
    "MedEdge AI is an administrative data interoperability and optical ingestion pipeline, not a clinical decision or diagnostic tool."
)


def _auth_message(kind: str, link: str) -> tuple[str, str, str]:
    verify = kind == "verify"
    title = "Verify your email" if verify else "Reset your password"
    description = (
        "Confirm your email address to finish setting up your MedEdge account."
        if verify
        else "We received a request to reset the password for your MedEdge account."
    )
    action = "Verify email address" if verify else "Reset password"
    expiry = "24 hours" if verify else "30 minutes"
    safe_link = html.escape(link, quote=True)
    plain = (
        f"MedEdge AI\n\n{title}\n\n{description}\n\n{action}:\n{link}\n\n"
        f"This link expires in {expiry}. Opening the link will ask you to confirm.\n\n"
        "If you did not request this email, you can safely ignore it.\n\n"
        f"{DISCLAIMER}\n"
    )
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#18181b;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{description} This link expires in {expiry}.</div>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f4f4f5;"><tr><td align="center" style="padding:36px 16px 40px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:560px;">
<tr><td style="padding:0 4px 18px;font-size:15px;font-weight:700;letter-spacing:-0.3px;color:#18181b;">MedEdge <span style="color:#71717a;font-weight:400;">AI</span></td></tr>
<tr><td style="background-color:#18181b;border-radius:16px 16px 0 0;padding:32px 36px;">
<div style="color:#a1a1aa;font-size:11px;font-weight:700;letter-spacing:1.6px;text-transform:uppercase;">Account security &nbsp; / &nbsp; MedEdge AI</div>
<div style="padding-top:26px;color:#fafafa;font-size:30px;line-height:1.18;letter-spacing:-1px;font-weight:700;">{title}.</div>
</td></tr>
<tr><td style="background-color:#ffffff;border:1px solid #e4e4e7;border-top:0;border-radius:0 0 16px 16px;padding:34px 36px;">
<p style="margin:0 0 26px;color:#52525b;font-size:16px;line-height:1.6;">{description}</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-radius:8px;background-color:#18181b;"><a href="{safe_link}" style="display:inline-block;padding:15px 23px;color:#ffffff;font-size:14px;font-weight:700;text-decoration:none;">{action} &nbsp; &#8594;</a></td></tr></table>
<p style="margin:24px 0 0;color:#71717a;font-size:13px;line-height:1.6;">This link expires in <strong style="color:#3f3f46;">{expiry}</strong>. You’ll be asked to confirm on the next screen.</p>
<div style="height:1px;background-color:#e4e4e7;margin:28px 0;"></div>
<p style="margin:0 0 8px;color:#3f3f46;font-size:13px;font-weight:700;">Button not working?</p>
<p style="margin:0;color:#71717a;font-size:12px;line-height:1.6;overflow-wrap:anywhere;word-break:break-all;">Copy and paste this link into your browser:<br><a href="{safe_link}" style="color:#52525b;text-decoration:underline;">{safe_link}</a></p>
</td></tr>
<tr><td style="padding:22px 4px 0;color:#71717a;font-size:12px;line-height:1.6;">If you didn’t request this email, you can safely ignore it.<br><span style="color:#a1a1aa;">MedEdge AI &nbsp; / &nbsp; Account security</span><br><span style="color:#a1a1aa;">{DISCLAIMER}</span></td></tr>
</table></td></tr></table></body></html>'''
    return title, plain, body


async def send_auth_mail(request, address: str, token: str, kind: str) -> None:
    settings = request.app.state.settings
    _reserve(request, address)
    route = "verify-email" if kind == "verify" else "reset-password"
    link = f"{settings.app_base_url.rstrip('/')}/{route}#token={token}"
    title, plain, body = _auth_message(kind, link)
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
