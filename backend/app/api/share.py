from fastapi import APIRouter, HTTPException, Request

from app.api.runs import _public

router = APIRouter()


@router.get("/api/share/{code}")
async def open_share(code: str, request: Request) -> dict:
    row = request.app.state.db.by_share(code.upper())
    if row is None:
        raise HTTPException(status_code=404, detail="That code has expired or does not exist")
    return _public(row)
