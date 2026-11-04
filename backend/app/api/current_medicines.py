"""Explicit patient-reported medicine use. Never infer active use from OCR."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.auth.security import require_role, require_user, throttle
from app.store.db import AuthUser, CurrentMedicine

router = APIRouter()


class MedicineInput(BaseModel):
    id: str = Field(pattern=r"^[a-f0-9-]{32,36}$")
    name: str = Field(min_length=1, max_length=160)
    instructions: str = Field(default="", max_length=500)

    @field_validator("name", "instructions")
    @classmethod
    def trim(cls, value, info):
        value = value.strip()
        if info.field_name == "name" and not value:
            raise ValueError("Enter the medicine name.")
        return value


class MedicineEdit(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    instructions: str = Field(default="", max_length=500)
    expected_confirmed_at: datetime


def medicine_json(row):
    return {
        "id": row.id,
        "name": row.name,
        "instructions": row.instructions,
        "confirmed_at": row.confirmed_at.isoformat(),
        "reported_by": "patient",
    }


@router.get("/patients/{patient_id}/medicines")
def list_medicines(patient_id: str, request: Request):
    from app.api.chart import active_connection

    user = require_user(request)
    if not (user.role == "patient" and user.id == patient_id) and not (
        user.role == "doctor" and active_connection(request.app.state.db, patient_id, user.id)
    ):
        raise HTTPException(404, "Chart not found.")
    with request.app.state.db.session() as session:
        rows = session.exec(
            select(CurrentMedicine)
            .where(CurrentMedicine.patient_id == patient_id)
            .order_by(CurrentMedicine.confirmed_at.desc(), CurrentMedicine.id)
        ).all()
        return JSONResponse(
            {"medicines": [medicine_json(row) for row in rows]},
            headers={"Cache-Control": "no-store"},
        )


@router.post("/patients/{patient_id}/medicines")
def add_medicine(patient_id: str, body: MedicineInput, request: Request):
    patient = require_role(request, "patient")
    if patient.id != patient_id:
        raise HTTPException(404, "Chart not found.")
    throttle(request, "current-medicine", patient.id, 30, 60)
    with request.app.state.db.session() as session:
        # Serialize additions for this patient in PostgreSQL, including the list limit.
        session.exec(select(AuthUser).where(AuthUser.id == patient.id).with_for_update()).one()
        existing = session.get(CurrentMedicine, body.id)
        if existing:
            if existing.patient_id != patient.id:
                raise HTTPException(409, "Please try adding the medicine again.")
            if existing.name != body.name or existing.instructions != body.instructions:
                raise HTTPException(409, "This request was already saved with different details.")
            return medicine_json(existing)
        rows = session.exec(
            select(CurrentMedicine.id).where(CurrentMedicine.patient_id == patient.id).limit(100)
        ).all()
        if len(rows) >= 100:
            raise HTTPException(
                422, "Your list is full. Remove medicines you no longer take first."
            )
        row = CurrentMedicine(
            **body.model_dump(), patient_id=patient.id, confirmed_at=datetime.now(UTC)
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            saved = session.get(CurrentMedicine, body.id)
            if (
                saved
                and saved.patient_id == patient.id
                and saved.name == body.name
                and saved.instructions == body.instructions
            ):
                return medicine_json(saved)
            raise HTTPException(409, "This request was already saved. Refresh your list.") from None
        session.refresh(row)
        return medicine_json(row)


@router.delete("/patients/{patient_id}/medicines/{medicine_id}")
def remove_medicine(patient_id: str, medicine_id: str, request: Request):
    patient = require_role(request, "patient")
    if patient.id != patient_id:
        raise HTTPException(404, "Chart not found.")
    throttle(request, "current-medicine", patient.id, 30, 60)
    with request.app.state.db.session() as session:
        row = session.get(CurrentMedicine, medicine_id)
        if not row or row.patient_id != patient.id:
            raise HTTPException(404, "Medicine not found.")
        session.delete(row)
        session.commit()
    return {"status": "removed"}


@router.patch("/patients/{patient_id}/medicines/{medicine_id}")
def edit_medicine(patient_id: str, medicine_id: str, body: MedicineEdit, request: Request):
    patient = require_role(request, "patient")
    if patient.id != patient_id:
        raise HTTPException(404, "Chart not found.")
    throttle(request, "current-medicine", patient.id, 30, 60)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter the medicine name.")
    with request.app.state.db.session() as session:
        row = session.get(CurrentMedicine, medicine_id)
        if row is None or row.patient_id != patient.id:
            raise HTTPException(404, "Medicine not found.")
        changed = session.exec(
            update(CurrentMedicine)
            .where(
                CurrentMedicine.id == medicine_id,
                CurrentMedicine.patient_id == patient.id,
                CurrentMedicine.confirmed_at == body.expected_confirmed_at,
            )
            .values(
                name=name, instructions=body.instructions.strip(), confirmed_at=datetime.now(UTC)
            )
            .returning(CurrentMedicine.id)
        ).scalar_one_or_none()
        if changed is None:
            raise HTTPException(
                409, "This medicine changed elsewhere. Reload the list before editing."
            )
        session.commit()
        session.refresh(row)
        return medicine_json(row)
