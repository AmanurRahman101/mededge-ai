from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.auth.security import require_user, throttle
from app.pipeline.medicine_reference import ReferenceUnavailable

router = APIRouter(prefix="/api/medicines", tags=["medicine reference"])


class MedicineSearch(BaseModel):
    query: str = Field(min_length=3, max_length=80)
    page: int = Field(default=1, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize(cls, value):
        value = " ".join(value.split())
        if len(value) < 3 or any(ord(c) < 32 for c in value):
            raise ValueError("Enter at least three characters of the medicine name.")
        return value


@router.post("/search")
async def search_medicines(body: MedicineSearch, request: Request):
    user = require_user(request)
    throttle(request, "medicine-reference", user.id, 40, 60)
    try:
        return await request.app.state.medicine_reference.search(body.query, body.page)
    except ReferenceUnavailable as exc:
        raise HTTPException(503, str(exc), headers={"Retry-After": "10"}) from None
