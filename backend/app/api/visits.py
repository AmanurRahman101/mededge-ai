"""Explicit encounters, isolated doctor workspaces and patient-owned visit contents."""

import asyncio
import re
import shutil
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.chart import active_connection, activity
from app.auth.security import require_role, require_user, throttle
from app.store.db import AuthUser, ChartConnection, ClinicalSummary, RunRow, Visit, VisitReference
from app.store.object_storage import StorageError
from app.visit_access import visit_access

router = APIRouter(prefix="/api/visits", tags=["visits"])


class StartVisit(BaseModel):
    patient_id: str
    title: str = Field(default="Consultation", min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=128)


class FinishVisit(BaseModel):
    expected_revision: int = Field(ge=1)


class LinkReport(BaseModel):
    run_id: str


class NoteInput(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)


def describe(session, visit, names=None):
    doctor = session.get(AuthUser, visit.doctor_id) if names is None else None
    patient = session.get(AuthUser, visit.patient_id) if names is None else None
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "doctor_id": visit.doctor_id,
        "patient_name": names.get(visit.patient_id, "Patient")
        if names is not None
        else patient.full_name
        if patient
        else "Patient",
        "doctor_name": names.get(visit.doctor_id, "Doctor")
        if names is not None
        else doctor.full_name
        if doctor
        else "Doctor",
        "title": visit.title,
        "status": visit.status,
        "revision": visit.revision,
        "created_at": visit.created_at.isoformat(),
        "completed_at": visit.completed_at.isoformat() if visit.completed_at else None,
    }


@router.get("")
def list_visits(request: Request, patient_id: str | None = None, offset: int = 0, limit: int = 20):
    user = require_user(request)
    limit = min(40, max(1, limit))
    with request.app.state.db.session() as session:
        query = select(Visit)
        if user.role == "patient":
            if patient_id and patient_id != user.id:
                raise HTTPException(404, "Chart not found.")
            query = query.where(Visit.patient_id == user.id)
        elif patient_id:
            if not active_connection(request.app.state.db, patient_id, user.id):
                raise HTTPException(404, "Chart not found.")
            query = query.where(
                Visit.patient_id == patient_id,
                or_(
                    Visit.doctor_id == user.id,
                    Visit.status == "completed",
                ),
            )
        else:
            connected = select(ChartConnection.patient_id).where(
                ChartConnection.doctor_id == user.id,
                ChartConnection.status == "approved",
            )
            query = query.where(Visit.doctor_id == user.id, Visit.patient_id.in_(connected))
        rows = session.exec(
            query.order_by(Visit.created_at.desc(), Visit.id.desc())
            .offset(max(0, offset))
            .limit(limit + 1)
        ).all()
        ids = {
            identifier
            for visit in rows[:limit]
            for identifier in (visit.patient_id, visit.doctor_id)
        }
        names = (
            {
                person.id: person.full_name
                for person in session.exec(select(AuthUser).where(AuthUser.id.in_(ids))).all()
            }
            if ids
            else {}
        )
        return {
            "visits": [describe(session, v, names) for v in rows[:limit]],
            "has_more": len(rows) > limit,
        }


@router.post("")
def start_visit(body: StartVisit, request: Request):
    doctor = require_role(request, "doctor")
    throttle(request, "start-visit", doctor.id, 30, 3600)
    db = request.app.state.db
    with db.session() as session:
        from app.api.prescriptions import consent

        consent(session, body.patient_id, doctor.id)
        previous = session.exec(
            select(Visit).where(
                Visit.doctor_id == doctor.id,
                Visit.submission_key == body.idempotency_key,
            )
        ).first()
        if previous:
            if previous.patient_id != body.patient_id:
                raise HTTPException(409, "This visit request was already used.")
            return describe(session, previous)
        current = session.exec(
            select(Visit).where(
                Visit.patient_id == body.patient_id,
                Visit.doctor_id == doctor.id,
                Visit.status == "open",
            )
        ).first()
        if current:
            return describe(session, current)
        visit = Visit(
            id=uuid.uuid4().hex,
            patient_id=body.patient_id,
            doctor_id=doctor.id,
            title=body.title.strip() or "Consultation",
            created_at=datetime.now(UTC),
            submission_key=body.idempotency_key,
        )
        session.add(visit)
        activity(session, body.patient_id, doctor.id, "visit_started")
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            current = session.exec(
                select(Visit).where(
                    Visit.patient_id == body.patient_id,
                    Visit.doctor_id == doctor.id,
                    Visit.status == "open",
                )
            ).first()
            if current:
                return describe(session, current)
            raise HTTPException(409, "Please reload the visits and try again.") from None
        return describe(session, visit)


def visit_records(session, visit_id):
    references = select(VisitReference.run_id).where(VisitReference.visit_id == visit_id)
    return session.exec(
        select(RunRow)
        .where(
            or_(
                RunRow.visit_id == visit_id,
                RunRow.id.in_(references),
            )
        )
        .order_by(RunRow.created_at, RunRow.id)
    ).all()


def blockers(session, visit):
    owned = session.exec(select(RunRow).where(RunRow.visit_id == visit.id)).all()
    ids = [r.id for r in owned]
    drafts = (
        session.exec(
            select(ClinicalSummary.id).where(
                ClinicalSummary.run_id.in_(ids),
                ClinicalSummary.status == "draft",
            )
        ).all()
        if ids
        else []
    )
    published = (
        session.exec(
            select(ClinicalSummary.id).where(
                ClinicalSummary.run_id.in_(ids),
                ClinicalSummary.status == "published",
            )
        ).first()
        if ids
        else None
    )
    result = []
    if any(r.status in {"queued", "processing", "awaiting_confirmation"} for r in owned):
        result.append("Finish report processing and privacy review.")
    if drafts:
        result.append("Publish or finish the visit’s draft notes and prescriptions.")
    if not published:
        result.append("Publish a note or prescription before completing the visit.")
    return result


@router.get("/{visit_id}")
def get_visit(visit_id: str, request: Request):
    user = require_user(request)
    with request.app.state.db.session() as session:
        visit = visit_access(session, visit_id, user)
        records = visit_records(session, visit.id)
        published = (
            set(
                session.exec(
                    select(ClinicalSummary.run_id).where(
                        ClinicalSummary.run_id.in_([r.id for r in records]),
                        ClinicalSummary.status == "published",
                    )
                ).all()
            )
            if records
            else set()
        )
        return {
            **describe(session, visit),
            "can_edit": user.id == visit.doctor_id and visit.status == "open",
            "completion_checks": blockers(session, visit) if user.id == visit.doctor_id else [],
            "records": [
                {
                    "run_id": r.id,
                    "title": r.title,
                    "input_mode": r.input_mode,
                    "status": r.status,
                    "document_type": r.document_type,
                    "has_published_note": r.id in published,
                    "reference": r.visit_id != visit.id,
                }
                for r in records
            ],
        }


@router.post("/{visit_id}/complete")
def complete_visit(visit_id: str, body: FinishVisit, request: Request):
    doctor = require_role(request, "doctor")
    with request.app.state.db.session() as session:
        visit = visit_access(session, visit_id, doctor, write=True, lock=True)
        if visit.revision != body.expected_revision:
            raise HTTPException(409, "The visit changed. Reload it before completing.")
        if visit.status == "completed":
            return describe(session, visit)
        remaining = blockers(session, visit)
        if remaining:
            raise HTTPException(409, " ".join(remaining))
        visit.status = "completed"
        visit.completed_at = datetime.now(UTC)
        visit.revision += 1
        session.add(visit)
        activity(session, visit.patient_id, doctor.id, "visit_completed")
        session.commit()
        return describe(session, visit)


@router.post("/{visit_id}/reports")
def reference_report(visit_id: str, body: LinkReport, request: Request):
    from app.api.runs import _row_or_404

    doctor = require_role(request, "doctor")
    row = _row_or_404(request, body.run_id)
    with request.app.state.db.session() as session:
        visit = visit_access(session, visit_id, doctor, write=True, open_only=True, lock=True)
        if row.owner_id != visit.patient_id:
            raise HTTPException(404, "Report not found.")
        if row.visit_id == visit.id or session.get(VisitReference, (visit.id, row.id)):
            return {"ok": True}
        session.add(
            VisitReference(
                visit_id=visit.id, run_id=row.id, added_by=doctor.id, added_at=datetime.now(UTC)
            )
        )
        visit.revision += 1
        session.add(visit)
        activity(session, visit.patient_id, doctor.id, "visit_report_linked", row.id)
        session.commit()
        return {"ok": True}


@router.post("/{visit_id}/notes")
def create_note(visit_id: str, body: NoteInput, request: Request):
    doctor = require_role(request, "doctor")
    with request.app.state.db.session() as session:
        visit = visit_access(session, visit_id, doctor, write=True, open_only=True, lock=True)
        key = "visit-note:" + body.idempotency_key
        previous = session.exec(
            select(RunRow).where(
                RunRow.submitted_by == doctor.id,
                RunRow.submission_key == key,
            )
        ).first()
        if previous:
            if previous.visit_id != visit.id:
                raise HTTPException(409, "This note request was already used.")
            return {"run_id": previous.id}
        run_id = uuid.uuid4().hex[:12]
        row = RunRow(
            id=run_id,
            owner_id=visit.patient_id,
            visit_id=visit.id,
            submitted_by=doctor.id,
            submission_key=key,
            status="reviewing",
            input_mode="visit_note",
            title="Visit note",
            document_type="other",
            created_at=datetime.now(UTC),
            pseudonym="Visit note",
        )
        session.add(row)
        session.flush()
        session.add(
            ClinicalSummary(
                id=uuid.uuid4().hex,
                run_id=run_id,
                author_id=doctor.id,
                transcript="Manually authored visit note.",
                summary_en="",
                summary_bn="",
                created_at=datetime.now(UTC),
            )
        )
        activity(session, visit.patient_id, doctor.id, "visit_note_created", run_id)
        session.commit()
        return {"run_id": run_id}


@router.delete("/{visit_id}")
def discard_empty_visit(visit_id: str, request: Request):
    doctor = require_role(request, "doctor")
    with request.app.state.db.session() as session:
        visit = visit_access(session, visit_id, doctor, write=True, open_only=True, lock=True)
        if visit_records(session, visit_id):
            raise HTTPException(409, "Only an empty visit can be discarded.")
        activity(session, visit.patient_id, doctor.id, "empty_visit_discarded")
        session.delete(visit)
        session.commit()
        return {"ok": True}


@router.delete("/{visit_id}/drafts/{run_id}")
async def discard_draft(visit_id: str, run_id: str, request: Request):
    doctor = require_role(request, "doctor")
    with request.app.state.db.session() as session:
        visit = visit_access(session, visit_id, doctor, write=True, open_only=True, lock=True)
        row = session.get(RunRow, run_id)
        if not row or row.visit_id != visit.id or row.submitted_by != doctor.id:
            raise HTTPException(404, "Draft not found.")
        if row.status in {"queued", "processing", "awaiting_confirmation"}:
            raise HTTPException(409, "Wait for processing before discarding this draft.")
        if session.exec(
            select(ClinicalSummary.id).where(
                ClinicalSummary.run_id == run_id,
                ClinicalSummary.status == "published",
            )
        ).first():
            raise HTTPException(409, "Published records stay in the patient's history.")
        storage = request.app.state.object_storage
        root = request.app.state.db.runs_dir.resolve()
        folder = root / run_id
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id)
            or folder.is_symlink()
            or not folder.resolve().is_relative_to(root)
        ):
            raise HTTPException(500, "Could not safely delete source files.")
        if storage:
            try:
                await asyncio.to_thread(storage.delete_record, run_id)
            except StorageError:
                raise HTTPException(503, "Could not delete stored files. Please retry.") from None
        if folder.exists():
            try:
                await asyncio.to_thread(shutil.rmtree, folder)
            except OSError:
                raise HTTPException(503, "Could not delete source files. Please retry.") from None
        session.exec(delete(VisitReference).where(VisitReference.run_id == run_id))
        session.exec(delete(ClinicalSummary).where(ClinicalSummary.run_id == run_id))
        session.delete(row)
        activity(session, visit.patient_id, doctor.id, "visit_draft_discarded")
        session.commit()
        return {"ok": True}
