"""Patient-controlled chart connections and history."""

import json
import re
import secrets
import shutil
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app import demo
from app.auth.security import client_key, digest, require_role, require_user, throttle
from app.store.db import (
    AuthUser,
    ChartActivity,
    ChartConnection,
    ClinicalSummary,
    ConnectionCode,
    ConsentEvent,
    RunGrant,
    RunRow,
)

router = APIRouter(prefix="/api/chart", tags=["chart"])
CONSENT_VERSION = "chart-access-v2"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CONSENT_SCOPE = "whole_chart,contribute,review,approve,download,meta_image_voice"
CONSENT_TEXT = (
    "I allow this doctor to access my entire patient history, including future records, "
    "and to upload, review, approve and download records until I revoke access. "
    "Original reports and voice recordings are stored in the patient chart until deletion. "
    "Images and voice may be sent to Meta for processing. Downloaded information "
    "cannot be recalled. Doctor accounts are self-declared, not credential-verified."
)


def active_connection(db, patient_id: str, doctor_id: str) -> bool:
    with db.session() as session:
        connection = session.get(ChartConnection, (patient_id, doctor_id))
        return bool(connection and connection.status == "approved")


def source_available(request: Request, run_id: str) -> bool:
    if (request.app.state.db.runs_dir / run_id / "redacted.png").is_file():
        return True
    storage = request.app.state.object_storage
    if not storage:
        return False
    from app.store.object_storage import StorageError

    try:
        return storage.exists(run_id, "redacted")
    except StorageError:
        raise HTTPException(503, "Could not check stored files. Please retry.") from None


def activity(session, patient_id: str, actor_id: str, action: str, run_id: str | None = None):
    session.add(
        ChartActivity(
            id=uuid.uuid4().hex,
            patient_id=patient_id,
            actor_id=actor_id,
            action=action,
            occurred_at=datetime.now(UTC),
            run_id=run_id,
        )
    )


class Redeem(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class Decision(BaseModel):
    approve: bool
    consent_version: str | None = None


class RecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None


class SummaryUpdate(BaseModel):
    summary_en: str = Field(min_length=1, max_length=12000)
    summary_bn: str = Field(min_length=1, max_length=12000)
    transcript: str = Field(min_length=1, max_length=20000)
    acknowledge_unresolved: bool = False
    reviewed_both_languages: bool = False


@router.post("/connection-code")
def create_code(request: Request):
    patient = require_role(request, "patient")
    throttle(request, "connection-code", patient.id, 10, 3600)
    now = datetime.now(UTC)
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        try:
            with request.app.state.db.session() as session:
                session.exec(delete(ConnectionCode).where(ConnectionCode.expires_at <= now))
                session.add(
                    ConnectionCode(
                        id=digest(code),
                        patient_id=patient.id,
                        expires_at=now + timedelta(minutes=20),
                    )
                )
                session.commit()
            return {"code": code, "expires_at": (now + timedelta(minutes=20)).isoformat()}
        except IntegrityError:
            continue
    raise HTTPException(503, "Could not create a connection code. Try again.")


@router.post("/requests")
def request_connection(request: Request, body: Redeem):
    doctor = require_role(request, "doctor")
    throttle(request, "connection-ip", client_key(request), 5, 60)
    throttle(request, "connection-doctor", doctor.id, 20, 3600)
    now = datetime.now(UTC)
    db = request.app.state.db
    with db.session() as session:
        stmt = (
            update(ConnectionCode)
            .where(
                ConnectionCode.id == digest(body.code.strip().upper()),
                ConnectionCode.consumed_at.is_(None),
                ConnectionCode.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(ConnectionCode.patient_id)
        )
        patient_id = session.exec(stmt).scalar_one_or_none()
        if not patient_id:
            session.rollback()
            raise HTTPException(404, "That code has expired or does not exist.")
        if db.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        upsert = insert(ChartConnection).values(
            patient_id=patient_id,
            doctor_id=doctor.id,
            status="pending",
            requested_at=now,
            request_id=uuid.uuid4().hex,
        )
        upsert = upsert.on_conflict_do_update(
            index_elements=["patient_id", "doctor_id"],
            set_={
                "status": "pending",
                "requested_at": now,
                "decided_at": None,
                "consent_version": None,
                "request_id": uuid.uuid4().hex,
            },
            where=ChartConnection.status != "approved",
        ).returning(ChartConnection.patient_id)
        if not session.exec(upsert).scalar_one_or_none():
            session.rollback()
            raise HTTPException(409, "This connection is already active.")
        activity(session, patient_id, doctor.id, "connection_requested")
        session.commit()
    return {"status": "pending"}


@router.get("/connections")
def connections(request: Request):
    user = require_user(request)
    db = request.app.state.db
    with db.session() as session:
        condition = (
            ChartConnection.patient_id == user.id
            if user.role == "patient"
            else ChartConnection.doctor_id == user.id
        )
        rows = session.exec(select(ChartConnection).where(condition)).all()
        result = []
        for row in rows:
            other_id = row.doctor_id if user.role == "patient" else row.patient_id
            other = session.get(AuthUser, other_id)
            # A pending request does not disclose the patient's identity to the doctor.
            visible = user.role == "patient" or row.status == "approved"
            result.append(
                {
                    "patient_id": row.patient_id if visible else None,
                    "doctor_id": row.doctor_id,
                    "request_id": row.request_id,
                    "status": row.status,
                    "name": other.full_name if other and visible else None,
                    "email": other.email if other and visible else None,
                    "requested_at": row.requested_at.isoformat(),
                    "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                }
            )
    return {"connections": result, "consent_version": CONSENT_VERSION, "consent_text": CONSENT_TEXT}


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: str, request: Request):
    doctor = require_role(request, "doctor")
    now = datetime.now(UTC)
    with request.app.state.db.session() as session:
        patient_id = session.exec(
            update(ChartConnection)
            .where(
                ChartConnection.request_id == request_id,
                ChartConnection.doctor_id == doctor.id,
                ChartConnection.status == "pending",
            )
            .values(status="revoked", decided_at=now)
            .returning(ChartConnection.patient_id)
        ).scalar_one_or_none()
        if not patient_id:
            raise HTTPException(404, "Request not found.")
        session.add(
            ConsentEvent(
                id=uuid.uuid4().hex,
                patient_id=patient_id,
                doctor_id=doctor.id,
                actor_id=doctor.id,
                action="cancelled",
                version=CONSENT_VERSION,
                scope=CONSENT_SCOPE,
                consent_text=CONSENT_TEXT,
                occurred_at=now,
            )
        )
        activity(session, patient_id, doctor.id, "connection_cancelled")
        session.commit()
    return {"status": "revoked"}


@router.post("/connections/{doctor_id}/decision")
def decide(request: Request, doctor_id: str, body: Decision):
    patient = require_role(request, "patient")
    if body.approve and body.consent_version != CONSENT_VERSION:
        raise HTTPException(422, "Review the current consent before approving.")
    with request.app.state.db.session() as session:
        status = "approved" if body.approve else "declined"
        now = datetime.now(UTC)
        result = session.exec(
            update(ChartConnection)
            .where(
                ChartConnection.patient_id == patient.id,
                ChartConnection.doctor_id == doctor_id,
                ChartConnection.status == "pending",
            )
            .values(
                status=status,
                consent_version=CONSENT_VERSION if body.approve else None,
                decided_at=now,
            )
            .returning(ChartConnection.doctor_id)
        ).scalar_one_or_none()
        if not result:
            raise HTTPException(404, "Request not found.")
        session.add(
            ConsentEvent(
                id=uuid.uuid4().hex,
                patient_id=patient.id,
                doctor_id=doctor_id,
                actor_id=patient.id,
                action=status,
                version=CONSENT_VERSION,
                scope=CONSENT_SCOPE,
                consent_text=CONSENT_TEXT,
                occurred_at=now,
            )
        )
        activity(session, patient.id, patient.id, "connection_" + status)
        session.commit()
    return {"status": "approved" if body.approve else "declined"}


@router.post("/connections/{other_id}/revoke")
def revoke(request: Request, other_id: str):
    user = require_user(request)
    if demo.is_demo(user.id):
        raise HTTPException(403, "Shared demo accounts cannot change consent.")
    patient_id, doctor_id = (user.id, other_id) if user.role == "patient" else (other_id, user.id)
    with request.app.state.db.session() as session:
        now = datetime.now(UTC)
        result = session.exec(
            update(ChartConnection)
            .where(
                ChartConnection.patient_id == patient_id,
                ChartConnection.doctor_id == doctor_id,
                ChartConnection.status.in_(["approved", "pending"]),
            )
            .values(status="revoked", decided_at=now)
            .returning(ChartConnection.doctor_id)
        ).scalar_one_or_none()
        if not result:
            raise HTTPException(404, "Connection not found.")
        session.add(
            ConsentEvent(
                id=uuid.uuid4().hex,
                patient_id=patient_id,
                doctor_id=doctor_id,
                actor_id=user.id,
                action="revoked",
                version=CONSENT_VERSION,
                scope=CONSENT_SCOPE,
                consent_text=CONSENT_TEXT,
                occurred_at=now,
            )
        )
        activity(session, patient_id, user.id, "connection_revoked")
        session.commit()
    return {"status": "revoked"}


@router.get("/records")
def records(
    request: Request,
    patient_id: str | None = None,
    search: str = "",
    archived: bool = False,
    offset: int = 0,
    limit: int = 20,
    document_type: str | None = None,
    status: str | None = None,
):
    user = require_user(request)
    owner_id = patient_id or user.id
    limit = min(max(limit, 1), 50)
    with request.app.state.db.session() as session:
        if owner_id != user.id:
            if user.role != "doctor":
                raise HTTPException(404, "Chart not found.")
            connection = session.exec(
                select(ChartConnection)
                .where(
                    ChartConnection.patient_id == owner_id,
                    ChartConnection.doctor_id == user.id,
                )
                .with_for_update()
            ).first()
            if not connection or connection.status != "approved":
                raise HTTPException(404, "Chart not found.")
        stmt = select(RunRow).where(RunRow.owner_id == owner_id, RunRow.archived == archived)
        if search.strip():
            stmt = stmt.where(RunRow.title.ilike("%" + search.strip().replace("%", "") + "%"))
        if document_type:
            stmt = stmt.where(RunRow.document_type == document_type)
        if status:
            stmt = stmt.where(RunRow.status == status)
        rows = session.exec(
            stmt.order_by(RunRow.created_at.desc(), RunRow.id.desc())
            .offset(max(offset, 0))
            .limit(limit + 1)
        ).all()
        return {
            "records": [
                {
                    "run_id": r.id,
                    "title": r.title,
                    "status": r.status,
                    "document_type": r.document_type,
                    "created_at": r.created_at.isoformat(),
                    "submitted_by": r.submitted_by,
                    "archived": r.archived,
                    "source_available": source_available(request, r.id),
                }
                for r in rows[:limit]
            ],
            "has_more": len(rows) > limit,
        }


@router.get("/patients/{patient_id}/overview")
def patient_overview(patient_id: str, request: Request, offset: int = 0, limit: int = 20):
    """Return saved chart history, not a model-generated clinical assessment."""
    doctor = require_role(request, "doctor")
    limit = min(max(limit, 1), 50)
    with request.app.state.db.session() as session:
        connection = session.exec(
            select(ChartConnection)
            .where(
                ChartConnection.patient_id == patient_id,
                ChartConnection.doctor_id == doctor.id,
            )
            .with_for_update()
        ).first()
        if not connection or connection.status != "approved":
            raise HTTPException(404, "Chart not found.")
        rows = session.exec(
            select(RunRow)
            .where(RunRow.owner_id == patient_id)
            .order_by(RunRow.created_at.desc(), RunRow.id.desc())
            .offset(max(offset, 0))
            .limit(limit + 1)
        ).all()
        page = rows[:limit]
        ids = [r.id for r in page]
        notes = (
            session.exec(
                select(ClinicalSummary)
                .where(ClinicalSummary.run_id.in_(ids), ClinicalSummary.status == "published")
                .order_by(ClinicalSummary.created_at.desc(), ClinicalSummary.id.desc())
            ).all()
            if ids
            else []
        )
        author_ids = {note.author_id for note in notes}
        authors = (
            {
                a.id: a.full_name
                for a in session.exec(select(AuthUser).where(AuthUser.id.in_(author_ids))).all()
            }
            if author_ids
            else {}
        )
        items = []
        for row in page:
            try:
                extraction = json.loads(row.extraction_json or "{}")
                if not isinstance(extraction, dict):
                    extraction = {}
            except (TypeError, ValueError):
                extraction = {}

            def readings(key, field, data=extraction):
                values = data.get(key, [])
                if not isinstance(values, list):
                    return []
                return [
                    v.get(field)
                    for v in values
                    if isinstance(v, dict)
                    and not v.get("contains_identifier")
                    and isinstance(v.get(field), str)
                    and v.get(field)
                ]

            lab_rows = extraction.get("rows", [])
            lab_rows = (
                [
                    {
                        "name": v.get("raw_name"),
                        "value": v.get("value"),
                        "value_text": v.get("value_text"),
                        "unit": v.get("unit"),
                    }
                    for v in lab_rows
                    if isinstance(v, dict)
                    and not v.get("contains_identifier")
                    and isinstance(v.get("raw_name"), str)
                ]
                if isinstance(lab_rows, list)
                else []
            )
            items.append(
                {
                    "run_id": row.id,
                    "title": row.title,
                    "status": row.status,
                    "document_type": row.document_type,
                    "created_at": row.created_at.isoformat(),
                    "archived": row.archived,
                    "source_available": source_available(request, row.id),
                    "medications": readings("medications", "raw_text"),
                    "tests": readings("advised_tests", "raw_name"),
                    "lab_rows": lab_rows,
                    "notes": [
                        {
                            "id": n.id,
                            "summary_en": n.summary_en,
                            "summary_bn": n.summary_bn,
                            "author_name": authors.get(n.author_id, "Doctor"),
                            "published_at": n.published_at.isoformat() if n.published_at else None,
                            "amends_id": n.amends_id,
                        }
                        for n in notes
                        if n.run_id == row.id
                    ],
                }
            )
        return {"records": items, "has_more": len(rows) > limit}


@router.patch("/records/{run_id}")
def update_record(run_id: str, body: RecordUpdate, request: Request):
    patient = require_role(request, "patient")
    with request.app.state.db.session() as session:
        row = session.get(RunRow, run_id)
        if not row or row.owner_id != patient.id:
            raise HTTPException(404, "Record not found.")
        if body.title is not None:
            row.title = body.title.strip()
            if not row.title:
                raise HTTPException(422, "Enter a title.")
        if body.archived is not None:
            row.archived = body.archived
        session.add(row)
        activity(session, patient.id, patient.id, "record_updated", row.id)
        session.commit()
    return {"ok": True}


@router.get("/records/{run_id}/download")
def download_fhir(run_id: str, request: Request):
    doctor = require_role(request, "doctor")
    with request.app.state.db.session() as session:
        row = session.get(RunRow, run_id)
        if not row or not row.owner_id:
            raise HTTPException(404, "Record not found.")
        if row.owner_id != doctor.id:
            connection = session.exec(
                select(ChartConnection)
                .where(
                    ChartConnection.patient_id == row.owner_id,
                    ChartConnection.doctor_id == doctor.id,
                )
                .with_for_update()
            ).first()
            if not connection or connection.status != "approved":
                raise HTTPException(404, "Record not found.")
            activity(session, row.owner_id, doctor.id, "fhir_downloaded", run_id)
        if row.status not in {"approved", "exported"} or not row.bundle_json:
            raise HTTPException(409, "Approve the FHIR bundle before downloading.")
        content = row.bundle_json
        session.commit()
    return Response(
        content=content,
        media_type="application/fhir+json",
        headers={
            "Content-Disposition": 'attachment; filename="mededge-record.json"',
            "Cache-Control": "no-store",
        },
    )


@router.delete("/records/{run_id}")
def delete_record(run_id: str, request: Request):
    patient = require_role(request, "patient")
    db = request.app.state.db
    with db.session() as session:
        row = session.exec(select(RunRow).where(RunRow.id == run_id).with_for_update()).first()
        if not row or row.owner_id != patient.id:
            raise HTTPException(404, "Record not found.")
        if row.status not in {"reviewing", "approved", "exported", "failed", "interrupted"}:
            raise HTTPException(409, "Wait for processing to finish before deleting this record.")
        if request.app.state.object_storage:
            from app.store.object_storage import StorageError

            try:
                request.app.state.object_storage.delete_record(run_id)
            except StorageError:
                raise HTTPException(503, "Could not delete stored files. Try again.") from None
        # Never follow unexpected paths or symlinks while cleaning temporary files.
        if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
            root = db.runs_dir.resolve()
            folder = root / run_id
            if folder.is_symlink() or not folder.resolve().is_relative_to(root):
                raise HTTPException(500, "Could not safely delete the source files.")
            if folder.exists():
                try:
                    shutil.rmtree(folder)
                except OSError:
                    raise HTTPException(
                        503, "Could not delete the source files. Try again."
                    ) from None
        else:
            raise HTTPException(500, "Could not safely delete the source files.")
        session.exec(delete(ClinicalSummary).where(ClinicalSummary.run_id == run_id))
        session.exec(delete(RunGrant).where(RunGrant.run_id == run_id))
        session.exec(delete(ChartActivity).where(ChartActivity.run_id == run_id))
        session.delete(row)
        activity(session, patient.id, patient.id, "record_deleted")
        session.commit()
    return {"ok": True}


@router.get("/activity")
def list_activity(request: Request, offset: int = 0, limit: int = 20):
    patient = require_role(request, "patient")
    limit = min(max(limit, 1), 50)
    with request.app.state.db.session() as session:
        rows = session.exec(
            select(ChartActivity)
            .where(ChartActivity.patient_id == patient.id)
            .order_by(ChartActivity.occurred_at.desc(), ChartActivity.id.desc())
            .offset(max(offset, 0))
            .limit(limit + 1)
        ).all()
        return {
            "activity": [
                {
                    "id": row.id,
                    "action": row.action,
                    "actor_id": row.actor_id,
                    "run_id": row.run_id,
                    "occurred_at": row.occurred_at.isoformat(),
                }
                for row in rows[:limit]
            ],
            "has_more": len(rows) > limit,
        }


@router.get("/records/{run_id}/summaries")
def summaries(run_id: str, request: Request):
    from app.api.runs import _row_or_404

    user = require_user(request)
    _row_or_404(request, run_id)
    with request.app.state.db.session() as session:
        items = session.exec(
            select(ClinicalSummary)
            .where(ClinicalSummary.run_id == run_id)
            .order_by(ClinicalSummary.created_at)
        ).all()
        author_ids = {item.author_id for item in items}
        authors = (
            {
                author.id: author.full_name
                for author in session.exec(
                    select(AuthUser).where(AuthUser.id.in_(author_ids))
                ).all()
            }
            if author_ids
            else {}
        )
        return {
            "summaries": [
                {
                    "id": s.id,
                    "author_id": s.author_id,
                    "author_name": authors.get(s.author_id, "Doctor"),
                    "amends_id": s.amends_id,
                    "transcript": s.transcript,
                    "summary_en": s.summary_en,
                    "summary_bn": s.summary_bn,
                    "unresolved": s.unresolved,
                    "status": s.status,
                    "created_at": s.created_at.isoformat(),
                    "published_at": s.published_at.isoformat() if s.published_at else None,
                }
                for s in items
                if s.status == "published" or (user.role == "doctor" and s.author_id == user.id)
            ]
        }


@router.post("/records/{run_id}/summaries/{summary_id}")
def save_summary(
    run_id: str, summary_id: str, body: SummaryUpdate, request: Request, publish: bool = False
):
    from app.api.runs import _row_or_404

    doctor = require_role(request, "doctor")
    row = _row_or_404(request, run_id)
    with request.app.state.db.session() as session:
        summary = session.get(ClinicalSummary, summary_id)
        connection = session.exec(
            select(ChartConnection)
            .where(
                ChartConnection.patient_id == row.owner_id, ChartConnection.doctor_id == doctor.id
            )
            .with_for_update()
        ).first()
        if (
            not summary
            or summary.run_id != run_id
            or summary.author_id != doctor.id
            or not connection
            or connection.status != "approved"
        ):
            raise HTTPException(404, "Summary not found.")
        if summary.status != "draft":
            raise HTTPException(409, "Published summaries cannot be edited.")
        if publish and not body.reviewed_both_languages:
            raise HTTPException(422, "Review both versions of the note before publishing.")
        if publish and summary.unresolved not in ("", "[]") and not body.acknowledge_unresolved:
            raise HTTPException(422, "Review and acknowledge unresolved details.")
        summary.summary_en = body.summary_en.strip()
        summary.summary_bn = body.summary_bn.strip()
        summary.transcript = body.transcript.strip()
        if not summary.summary_en or not summary.summary_bn or not summary.transcript:
            raise HTTPException(422, "Both summaries and transcript are required.")
        if publish:
            summary.status = "published"
            summary.published_at = datetime.now(UTC)
            activity(session, row.owner_id, doctor.id, "summary_published", run_id)
        session.add(summary)
        session.commit()
    return {"status": "published" if publish else "draft"}


@router.post("/records/{run_id}/summaries/{summary_id}/amend")
def amend_summary(run_id: str, summary_id: str, request: Request):
    from app.api.runs import _row_or_404

    doctor = require_role(request, "doctor")
    row = _row_or_404(request, run_id)
    with request.app.state.db.session() as session:
        connection = session.exec(
            select(ChartConnection)
            .where(
                ChartConnection.patient_id == row.owner_id, ChartConnection.doctor_id == doctor.id
            )
            .with_for_update()
        ).first()
        original = session.get(ClinicalSummary, summary_id)
        if (
            not connection
            or connection.status != "approved"
            or not original
            or original.run_id != run_id
            or original.status != "published"
        ):
            raise HTTPException(404, "Published summary not found.")
        draft_id = uuid.uuid4().hex
        draft = ClinicalSummary(
            id=draft_id,
            run_id=run_id,
            author_id=doctor.id,
            transcript=original.transcript,
            summary_en=original.summary_en,
            summary_bn=original.summary_bn,
            unresolved="[]",
            status="draft",
            created_at=datetime.now(UTC),
            amends_id=original.id,
        )
        session.add(draft)
        activity(session, row.owner_id, doctor.id, "summary_amendment_started", run_id)
        session.commit()
    return {"id": draft_id, "status": "draft"}
