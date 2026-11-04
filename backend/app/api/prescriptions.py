"""Doctor-authored prescriptions: voice or manual entry, always reviewed before publication."""

import asyncio
import hashlib
import io
import json
import uuid
import wave
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.chart import active_connection, activity
from app.auth.security import require_role, throttle
from app.events import EventKind, Stage
from app.models.providers import TextPart
from app.pipeline.orchestrator import EXTRACT_USD, VOICE_USD, new_run_id, pseudonym_for
from app.pipeline.prescription_schema import INSTRUCTIONS, PrescriptionDraft
from app.pipeline.transcribe import transcribe_wav
from app.store.db import ChartConnection, ClinicalSummary, RunRow
from app.store.object_storage import StorageError

router = APIRouter(prefix="/api/chart", tags=["prescriptions"])


def validate_audio(data):
    if not data or len(data) > 9_000_000:
        raise HTTPException(422, "Recording must be nonempty and at most 9 MB.")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if (
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getframerate(),
                wav.getcomptype(),
            ) not in {(1, 2, 16000, "NONE"), (1, 2, 24000, "NONE")}:
                raise HTTPException(422, "Recording must be mono 16-bit PCM at 16 or 24 kHz.")
            count = wav.getnframes()
            if (
                count <= 0
                or count / wav.getframerate() > 180
                or len(wav.readframes(count)) != count * 2
            ):
                raise HTTPException(422, "Recording must be complete and at most three minutes.")
    except (wave.Error, EOFError, ZeroDivisionError):
        raise HTTPException(422, "Upload a valid WAV recording.") from None


def consent(session, patient_id, doctor_id):
    row = session.exec(
        select(ChartConnection)
        .where(ChartConnection.patient_id == patient_id, ChartConnection.doctor_id == doctor_id)
        .with_for_update()
    ).first()
    if not row or row.status != "approved":
        raise HTTPException(404, "Patient chart not found.")


def start_task(app, row):
    app.state.bus.open(row.id)
    task = asyncio.create_task(process(app, row.id))
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)
    app.state.orchestrator.register_task(row.id, row.owner_id, row.submitted_by, task)


async def process(app, run_id):
    db, bus = app.state.db, app.state.bus

    def check():
        app.state.orchestrator._check_consent(SimpleNamespace(run_id=run_id))

    try:
        check()
        row = db.get(run_id)
        with db.session() as session:
            completed = session.exec(
                select(ClinicalSummary.id).where(ClinicalSummary.run_id == run_id)
            ).first()
        if completed:
            db.update(run_id, status="reviewing")
            bus.publish(
                run_id, Stage.EXTRACT, EventKind.COMPLETED, "Saved prescription ready for review"
            )
            return
        db.update(run_id, status="processing")
        transcript = row.transcript
        if not transcript:
            if db.spent_today() >= app.state.settings.daily_budget_usd:
                raise ValueError("Processing budget reached. Please try later.")
            bus.publish(
                run_id, Stage.TRANSCRIBE, EventKind.STARTED, "Transcribing the prescription"
            )
            if app.state.object_storage:
                audio, _ = await asyncio.to_thread(app.state.object_storage.get, run_id, "audio")
            else:
                audio = (db.runs_dir / run_id / "audio.wav").read_bytes()
            voice = await transcribe_wav(app.state.http, app.state.settings, audio)
            del audio
            db.add_spend(VOICE_USD)
            transcript = str(voice.get("transcript") or "").strip()
            if not transcript:
                raise ValueError("No speech detected. Record the prescription again.")
            if len(transcript) > 20000:
                raise ValueError("The transcript is too long. Use a shorter recording.")
            check()
            db.update(run_id, transcript=transcript)
        check()
        if db.spent_today() >= app.state.settings.daily_budget_usd:
            raise ValueError("Processing budget reached. Please try later.")
        bus.publish(
            run_id, Stage.EXTRACT, EventKind.STARTED, "Preparing the prescription for review"
        )
        result = await app.state.router.structured(
            "extractor",
            instructions=INSTRUCTIONS,
            parts=[TextPart(transcript)],
            schema=PrescriptionDraft,
        )
        db.add_spend(EXTRACT_USD)
        check()
        medicines = [
            m.model_copy(update={"id": uuid.uuid4().hex, "confirmed": False}).model_dump()
            for m in result.value.medicines
        ]
        with db.session() as session:
            consent(session, row.owner_id, row.submitted_by)
            current = session.get(RunRow, run_id)
            if current is None:
                return
            existing = session.exec(
                select(ClinicalSummary).where(ClinicalSummary.run_id == run_id)
            ).first()
            if existing is None:
                session.add(
                    ClinicalSummary(
                        id=uuid.uuid4().hex,
                        run_id=run_id,
                        author_id=row.submitted_by,
                        transcript=transcript,
                        summary_en=result.value.summary_en,
                        summary_bn=result.value.summary_bn,
                        unresolved=json.dumps(result.value.unresolved),
                        prescription_json=json.dumps(medicines, ensure_ascii=False),
                        created_at=datetime.now(UTC),
                    )
                )
            current.status = "reviewing"
            session.add(current)
            session.commit()
        bus.publish(
            run_id, Stage.EXTRACT, EventKind.COMPLETED, "Prescription ready for doctor review"
        )
    except asyncio.CancelledError:
        db.update(run_id, status="interrupted")
        raise
    except Exception as exc:
        db.update(run_id, status="failed")
        safe_messages = (
            "No speech detected. Record the prescription again.",
            "Processing budget reached. Please try later.",
            "The transcript is too long. Use a shorter recording.",
        )
        message = (
            str(exc)
            if type(exc) is ValueError and str(exc) in safe_messages
            else (
                "Prescription processing failed. Retry explicitly or start a manual prescription."
            )
        )
        bus.publish(run_id, Stage.SYSTEM, EventKind.ERROR, message)
    finally:
        app.state.orchestrator._save_trace(run_id)
        bus.close(run_id)


@router.post("/patients/{patient_id}/prescriptions")
async def create_prescription(
    patient_id: str,
    request: Request,
    mode: str = Form(),
    idempotency_key: str = Form(),
    audio: UploadFile | None = File(default=None),
):
    doctor = require_role(request, "doctor")
    db = request.app.state.db
    if not active_connection(db, patient_id, doctor.id):
        raise HTTPException(404, "Patient chart not found.")
    if mode not in {"voice", "manual"} or not 1 <= len(idempotency_key) <= 128:
        raise HTTPException(422, "Choose voice or manual entry and supply a submission key.")
    data = await audio.read(9_000_001) if audio else b""
    if mode == "voice":
        validate_audio(data)
    elif data:
        raise HTTPException(422, "Manual prescriptions do not accept a recording.")
    fingerprint = hashlib.sha256(patient_id.encode() + mode.encode() + data).hexdigest()
    with db.session() as session:
        previous = session.exec(
            select(RunRow).where(
                RunRow.submitted_by == doctor.id, RunRow.submission_key == idempotency_key
            )
        ).first()
        if previous:
            if previous.submission_digest != fingerprint:
                raise HTTPException(409, "Submission key was already used for different content.")
            return {"run_id": previous.id}
    throttle(request, f"new-prescription-{mode}", doctor.id, 12 if mode == "voice" else 60, 3600)
    if mode == "voice" and len(request.app.state.tasks) >= 4:
        raise HTTPException(
            429, "Processing is busy. Please retry shortly.", headers={"Retry-After": "10"}
        )
    run_id = new_run_id()
    row = RunRow(
        id=run_id,
        owner_id=patient_id,
        submitted_by=doctor.id,
        submission_key=idempotency_key,
        submission_digest=fingerprint,
        status="queued" if mode == "voice" else "reviewing",
        document_type="prescription",
        input_mode=f"{mode}_prescription",
        title="Prescription",
        pseudonym=pseudonym_for(run_id, request.app.state.settings.pseudonym_salt),
        created_at=datetime.now(UTC),
    )
    storage = request.app.state.object_storage
    if data:
        if storage is None and request.app.state.settings.app_env == "production":
            raise HTTPException(503, "Permanent recording storage is not configured.")
        if storage:
            try:
                await asyncio.to_thread(storage.put, run_id, "audio", data, "audio/wav")
            except StorageError:
                raise HTTPException(503, "Could not store the recording. Please retry.") from None
        else:
            folder = db.runs_dir / run_id
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "audio.wav").write_bytes(data)
    try:
        with db.session() as session:
            consent(session, patient_id, doctor.id)
            session.add(row)
            session.flush()
            if mode == "manual":
                session.add(
                    ClinicalSummary(
                        id=uuid.uuid4().hex,
                        run_id=run_id,
                        author_id=doctor.id,
                        transcript="Manually authored prescription.",
                        summary_en="Prescription.",
                        summary_bn="ব্যবস্থাপত্র।",
                        prescription_json="[]",
                        created_at=datetime.now(UTC),
                    )
                )
            activity(session, patient_id, doctor.id, "prescription_created", run_id)
            session.commit()
            session.refresh(row)
    except (IntegrityError, HTTPException) as exc:
        if data and storage:
            await asyncio.to_thread(storage.delete_record, run_id)
        if isinstance(exc, HTTPException):
            raise
        with db.session() as session:
            previous = session.exec(
                select(RunRow).where(
                    RunRow.submitted_by == doctor.id, RunRow.submission_key == idempotency_key
                )
            ).first()
            if previous and previous.submission_digest == fingerprint:
                return {"run_id": previous.id}
        raise HTTPException(409, "Submission key was already used for different content.") from None
    if mode == "voice":
        start_task(request.app, row)
    return {"run_id": run_id}


@router.post("/records/{run_id}/prescription/retry")
async def retry_prescription(run_id: str, request: Request):
    from app.api.runs import _row_or_404

    doctor = require_role(request, "doctor")
    row = _row_or_404(request, run_id)
    if row.submitted_by != doctor.id or row.input_mode != "voice_prescription":
        raise HTTPException(404, "Prescription not found.")
    if row.status not in {"failed", "interrupted"}:
        raise HTTPException(409, "This prescription is already processing or ready for review.")
    throttle(request, "retry-prescription", doctor.id, 3, 600)
    if len(request.app.state.tasks) >= 4:
        raise HTTPException(429, "Processing is busy. Please retry shortly.")
    with request.app.state.db.session() as session:
        from sqlalchemy import update

        consent(session, row.owner_id, doctor.id)
        changed = session.exec(
            update(RunRow)
            .where(RunRow.id == run_id, RunRow.status.in_(["failed", "interrupted"]))
            .values(status="queued")
            .returning(RunRow.id)
        ).scalar_one_or_none()
        if not changed:
            raise HTTPException(409, "Processing has already resumed.")
        session.commit()
    start_task(request.app, row)
    return {"run_id": run_id}
