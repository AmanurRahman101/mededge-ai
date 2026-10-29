from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.runs import _public
from app.auth.security import client_key, require_role, throttle
from app.limit import limiter
from app.store.db import RunGrant

router = APIRouter()


class RedeemBody(BaseModel):
    code: str = Field(min_length=1, max_length=32)


@router.post("/api/share/redeem")
@limiter.limit("5/minute")
async def redeem_share(request: Request, body: RedeemBody) -> dict:
    user = require_role(request, "doctor")
    throttle(request, "share-ip", client_key(request), 5, 60)
    throttle(request, "share-user", user.id, 20, 3600)
    code = body.code.strip().upper()
    row = request.app.state.db.by_share(code)
    if row is None or row.owner_id is None or row.share_expires is None:
        raise HTTPException(status_code=404, detail="That code has expired or does not exist")
    expires = row.share_expires
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        raise HTTPException(status_code=404, detail="That code has expired or does not exist")
    with request.app.state.db.session() as session:
        grant = session.get(RunGrant, (row.id, user.id))
        if grant is None:
            grant = RunGrant(run_id=row.id, user_id=user.id, expires_at=expires)
        else:
            grant.expires_at = expires
        session.add(grant)
        session.commit()
    return _public(row)
