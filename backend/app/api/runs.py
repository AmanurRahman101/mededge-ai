import asyncio
import hashlib
import io
import json
import wave
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from app.api.chart import active_connection
from app.auth.security import require_role, require_user
from app.events import EventBus
from app.limit import limiter
from app.pipeline.cases import case_image
from app.pipeline.fallback_assembler import assemble
from app.pipeline.orchestrator import RunContext, new_run_id, pseudonym_for
from app.pipeline.schemas import EncounterFields, Extraction, LabRow, MedicationRow
from app.pipeline.terminology import search_loinc
from app.pipeline.verify import verify
from app.store.db import ChartConnection, Database, RunRow

router = APIRouter()
FILES = {"overlay.png", "redacted.png", "table.png"}
MAX_IMAGE_BYTES = 12_000_000
MAX_AUDIO_BYTES = 9_000_000


class ApproveBody(BaseModel):
    rows: list[LabRow] | None = None
    medications: list[MedicationRow] | None = None
    note: str | None = None


def _db(request: Request) -> Database:
    return request.app.state.db


def _row_or_404(request: Request, run_id: str) -> RunRow:
    user = require_user(request)
    row = _db(request).get(run_id)
    if row is None or row.owner_id is None:
        raise HTTPException(status_code=404, detail="Unknown run")
    if row.owner_id != user.id:
        if user.role != "doctor" or not active_connection(_db(request), row.owner_id, user.id):
            raise HTTPException(status_code=404, detail="Unknown run")
    return row


@router.post("/api/runs")
@limiter.limit("30/minute")
async def create_run(
    request: Request,
    image: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
    case_id: str | None = Form(default=None),
    auto_confirm: bool = Form(default=False),
    inject_fault: bool = Form(default=False),
    patient_id: str | None = Form(default=None),
    idempotency_key: str | None = Form(default=None),
    source_run_id: str | None = Form(default=None),
) -> dict:
    user = require_user(request)
    if user.role == "doctor" and not case_id:
        if not patient_id or not active_connection(_db(request), patient_id, user.id):
            raise HTTPException(404, "Patient chart not found.")
        if audio is None or (image is None and not source_run_id) or not idempotency_key:
            raise HTTPException(422, "A report, voice recording, and submission key are required.")
        if len(idempotency_key) > 128:
            raise HTTPException(422, "Invalid submission key.")
    elif user.role != "doctor" and audio is not None:
        raise HTTPException(422, "Patient uploads accept images only.")
    image_bytes: bytes | None = None
    mime = "image/jpeg"
    if case_id:
        loaded = case_image(case_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="Unknown sample case")
        image_bytes, mime = loaded
        auto_confirm = True
    elif image is not None:
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "The image exceeds the 12 MB limit.")
        mime = image.content_type or "image/jpeg"
        # The client cannot bypass confirmation for a real upload.
        auto_confirm = False
    elif source_run_id and user.role == "doctor" and not case_id:
        source = _row_or_404(request, source_run_id)
        if source.owner_id != patient_id:
            raise HTTPException(404, "Source record not found.")
        path = _db(request).runs_dir / source_run_id / "redacted.png"
        if not path.is_file():
            raise HTTPException(409, "Source image unavailable. Upload a report image.")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise HTTPException(413, "The source image exceeds the 12 MB limit.")
        image_bytes = path.read_bytes()
        mime = "image/png"
        auto_confirm = False
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Upload a report or choose a sample case")

    audio_bytes = await audio.read(MAX_AUDIO_BYTES + 1) if audio is not None else None
    if user.role == "doctor" and not case_id:
        if not audio_bytes or len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(422, "Recording must be at most 9 MB.")
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                if (
                    wav.getnchannels(),
                    wav.getsampwidth(),
                    wav.getframerate(),
                    wav.getcomptype(),
                ) not in {(1, 2, 16000, "NONE"), (1, 2, 24000, "NONE")}:
                    raise HTTPException(422, "Recording must be mono 16-bit PCM at 16 or 24 kHz.")
                if wav.getnframes() / wav.getframerate() > 180:
                    raise HTTPException(422, "Recording must be at most three minutes.")
                frames = wav.readframes(wav.getnframes())
                if not frames or len(frames) != wav.getnframes() * 2:
                    raise HTTPException(422, "Recording is empty or incomplete.")
        except (wave.Error, EOFError, ZeroDivisionError):
            raise HTTPException(422, "Upload a valid WAV recording.") from None
    db: Database = request.app.state.db
    submission_digest = None
    if user.role == "doctor" and not case_id:
        submission_digest = hashlib.sha256(
            patient_id.encode()
            + b"\0"
            + hashlib.sha256(image_bytes).digest()
            + hashlib.sha256(audio_bytes).digest()
        ).hexdigest()
        with db.session() as session:
            previous = session.exec(
                select(RunRow).where(
                    RunRow.submitted_by == user.id, RunRow.submission_key == idempotency_key
                )
            ).first()
            if previous:
                if previous.submission_digest != submission_digest:
                    raise HTTPException(
                        409, "Submission key was already used for different content."
                    )
                return {
                    "run_id": previous.id,
                    "pseudonym": previous.pseudonym,
                    "events_url": f"/api/runs/{previous.id}/events",
                }
    if len(request.app.state.tasks) >= 4:
        raise HTTPException(429, "The service is busy. Please retry shortly.")
    run_id = new_run_id()
    anon = pseudonym_for(run_id, request.app.state.settings.pseudonym_salt)
    try:
        with db.session() as session:
            if submission_digest:
                connection = session.exec(
                    select(ChartConnection)
                    .where(
                        ChartConnection.patient_id == patient_id,
                        ChartConnection.doctor_id == user.id,
                    )
                    .with_for_update()
                ).first()
                if not connection or connection.status != "approved":
                    raise HTTPException(404, "Patient chart not found.")
            session.add(
                RunRow(
                    id=run_id,
                    status="queued",
                    created_at=datetime.now(UTC),
                    pseudonym=anon,
                    inject_fault=inject_fault,
                    owner_id=patient_id if user.role == "doctor" and not case_id else user.id,
                    submitted_by=user.id,
                    submission_key=idempotency_key if submission_digest else None,
                    submission_digest=submission_digest,
                )
            )
            session.commit()
    except IntegrityError:
        with db.session() as session:
            previous = session.exec(
                select(RunRow).where(
                    RunRow.submitted_by == user.id, RunRow.submission_key == idempotency_key
                )
            ).first()
            if previous and previous.submission_digest == submission_digest:
                return {
                    "run_id": previous.id,
                    "pseudonym": previous.pseudonym,
                    "events_url": f"/api/runs/{previous.id}/events",
                }
        raise HTTPException(409, "Submission key was already used for different content.") from None
    bus: EventBus = request.app.state.bus
    bus.open(run_id)
    ctx = RunContext(
        run_id, image_bytes, audio_bytes or None, case_id, auto_confirm, inject_fault, mime
    )
    task = asyncio.create_task(request.app.state.orchestrator.execute(ctx))
    request.app.state.tasks.add(task)
    task.add_done_callback(request.app.state.tasks.discard)
    request.app.state.orchestrator.register_task(
        run_id, patient_id if submission_digest else user.id, user.id, task
    )
    return {"run_id": run_id, "pseudonym": anon, "events_url": f"/api/runs/{run_id}/events"}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict:
    row = _row_or_404(request, run_id)
    result = _public(row)
    result["source_available"] = (_db(request).runs_dir / run_id / "redacted.png").is_file()
    return result


@router.get("/api/runs/{run_id}/files/{name}")
async def run_file(run_id: str, name: str, request: Request) -> Response:
    if name not in FILES:
        raise HTTPException(status_code=404, detail="Unknown file")
    _row_or_404(request, run_id)
    path = request.app.state.db.runs_dir / run_id / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not ready")
    return Response(
        content=path.read_bytes(), media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@router.post("/api/runs/{run_id}/confirm")
async def confirm_run(run_id: str, request: Request) -> dict:
    row = _row_or_404(request, run_id)
    user = require_user(request)
    if row.owner_id != user.id and row.submitted_by != user.id:
        raise HTTPException(status_code=404, detail="Unknown run")
    if row.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="This run is not waiting for confirmation")
    if not request.app.state.orchestrator.confirm(run_id):
        raise HTTPException(status_code=409, detail="This run is not waiting for confirmation")
    return {"ok": True}


@router.post("/api/runs/{run_id}/approve")
async def approve_run(run_id: str, body: ApproveBody, request: Request) -> dict:
    doctor = require_role(request, "doctor")
    row = _row_or_404(request, run_id)
    if not row.extraction_json or not row.encounter_json:
        raise HTTPException(status_code=409, detail="Nothing to approve yet")
    extraction = Extraction.model_validate_json(row.extraction_json)
    encounter = EncounterFields.model_validate_json(row.encounter_json)
    if body.rows is not None:
        extraction.rows = body.rows
    if body.medications is not None:
        extraction.medications = body.medications
    if body.note is not None:
        encounter.note = body.note
    loinc = {}
    allowed: set[str] = set()
    for item in extraction.rows:
        try:
            hits = await search_loinc(request.app.state.http, item.raw_name, max_list=1)
        except Exception:
            hits = []
        if hits:
            loinc[item.raw_name.lower()] = hits[0]
            allowed.add(hits[0].code)
    bundle = assemble(extraction, encounter, row.pseudonym, loinc)
    report = verify(bundle, extraction, allowed, set())
    if not report.ok:
        raise HTTPException(status_code=422, detail=report.as_text())
    with _db(request).session() as session:
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
                raise HTTPException(404, "Unknown run")
        stored = session.exec(select(RunRow).where(RunRow.id == run_id).with_for_update()).first()
        if not stored or stored.owner_id != row.owner_id:
            raise HTTPException(404, "Unknown run")
        stored.status = "approved"
        stored.extraction_json = extraction.model_dump_json()
        stored.encounter_json = encounter.model_dump_json()
        stored.bundle_json = json.dumps(bundle)
        session.add(stored)
        session.commit()
    return {"ok": True, "bundle": bundle}


@router.post("/api/runs/{run_id}/export")
async def export_run(run_id: str, request: Request) -> dict:
    require_role(request, "doctor")
    _row_or_404(request, run_id)
    raise HTTPException(status_code=403, detail="External FHIR export is disabled.")


@router.post("/api/runs/{run_id}/dictate")
async def dictate_run(
    run_id: str,
    request: Request,
    audio: UploadFile = File(),
) -> dict:
    require_role(request, "doctor")
    raise HTTPException(410, "Use a combined report and voice submission.")


@router.post("/api/runs/{run_id}/share")
async def share_run(run_id: str, request: Request) -> dict:
    raise HTTPException(status_code=410, detail="Use patient-approved chart connections instead.")


@router.get("/api/runs/{run_id}/events")
async def run_events(
    run_id: str, request: Request, last_event_id: str | None = Header(default=None)
) -> EventSourceResponse:
    _row_or_404(request, run_id)
    bus: EventBus = request.app.state.bus
    if not bus.exists(run_id):

        async def closed_stream():
            yield {"event": "end", "data": "{}"}

        return EventSourceResponse(closed_stream())
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream():
        iterator = bus.subscribe(run_id, after_seq=after_seq).__aiter__()
        pending = asyncio.create_task(iterator.__anext__())
        try:
            while True:
                done, _ = await asyncio.wait({pending}, timeout=3)
                try:
                    _row_or_404(request, run_id)
                except HTTPException:
                    return
                if not done:
                    yield {"comment": "connected"}
                    continue
                try:
                    event = pending.result()
                except StopAsyncIteration:
                    yield {"event": "end", "data": "{}"}
                    return
                yield {"event": "pipeline", "id": str(event.seq), "data": event.model_dump_json()}
                pending = asyncio.create_task(iterator.__anext__())
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await iterator.aclose()

    return EventSourceResponse(stream(), ping=15)


def _public(row: RunRow) -> dict:
    return {
        "run_id": row.id,
        "status": row.status,
        "pseudonym": row.pseudonym,
        "document_type": row.document_type,
        "extraction": json.loads(row.extraction_json) if row.extraction_json else None,
        "encounter": json.loads(row.encounter_json) if row.encounter_json else None,
        "bundle": json.loads(row.bundle_json) if row.bundle_json else None,
        "transcript": row.transcript,
        "extractor_model": row.extractor_model,
        "used_fallback": row.used_fallback,
        "replay": row.replay,
        "inject_fault": row.inject_fault,
        # Share codes are returned only by the owner's explicit share action.
        "share_code": None,
        "overlay_url": f"/api/runs/{row.id}/files/overlay.png",
        "redacted_url": f"/api/runs/{row.id}/files/redacted.png",
    }
