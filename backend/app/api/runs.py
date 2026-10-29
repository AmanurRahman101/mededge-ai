import asyncio
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sse_starlette.sse import EventSourceResponse

from app.auth.security import require_role, require_user
from app.events import EventBus
from app.limit import limiter
from app.pipeline.cases import case_image
from app.pipeline.fallback_assembler import assemble
from app.pipeline.orchestrator import RunContext, new_run_id, pseudonym_for, share_code
from app.pipeline.schemas import EncounterFields, Extraction, LabRow, MedicationRow
from app.pipeline.terminology import search_loinc
from app.pipeline.verify import verify
from app.store.db import Database, RunGrant, RunRow

router = APIRouter()
FILES = {"overlay.png", "redacted.png", "table.png"}


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
        with _db(request).session() as session:
            grant = session.get(RunGrant, (run_id, user.id))
        expiry = grant.expires_at if grant is not None else None
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if user.role != "doctor" or expiry is None or expiry <= datetime.now(UTC):
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
) -> dict:
    user = require_user(request)
    image_bytes: bytes | None = None
    mime = "image/jpeg"
    if case_id:
        loaded = case_image(case_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="Unknown sample case")
        image_bytes, mime = loaded
        auto_confirm = True
    elif image is not None:
        image_bytes = await image.read()
        mime = image.content_type or "image/jpeg"
        # The client cannot bypass confirmation for a real upload.
        auto_confirm = False
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Upload a report or choose a sample case")

    audio_bytes = await audio.read() if audio is not None else None
    run_id = new_run_id()
    anon = pseudonym_for(run_id, request.app.state.settings.pseudonym_salt)
    db: Database = request.app.state.db
    db.add(
        RunRow(
            id=run_id,
            status="queued",
            created_at=datetime.now(UTC),
            pseudonym=anon,
            inject_fault=inject_fault,
            owner_id=user.id,
        )
    )
    bus: EventBus = request.app.state.bus
    bus.open(run_id)
    ctx = RunContext(
        run_id, image_bytes, audio_bytes or None, case_id, auto_confirm, inject_fault, mime
    )
    task = asyncio.create_task(request.app.state.orchestrator.execute(ctx))
    request.app.state.tasks.add(task)
    task.add_done_callback(request.app.state.tasks.discard)
    return {"run_id": run_id, "pseudonym": anon, "events_url": f"/api/runs/{run_id}/events"}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict:
    row = _row_or_404(request, run_id)
    return _public(row)


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
    if row.owner_id != require_user(request).id:
        raise HTTPException(status_code=404, detail="Unknown run")
    if row.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="This run is not waiting for confirmation")
    if not request.app.state.orchestrator.confirm(run_id):
        raise HTTPException(status_code=409, detail="This run is not waiting for confirmation")
    return {"ok": True}


@router.post("/api/runs/{run_id}/approve")
async def approve_run(run_id: str, body: ApproveBody, request: Request) -> dict:
    require_role(request, "doctor")
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
    request.app.state.db.update(
        run_id,
        status="approved",
        extraction_json=extraction.model_dump_json(),
        encounter_json=encounter.model_dump_json(),
        bundle_json=json.dumps(bundle),
    )
    return {"ok": True, "bundle": bundle}


@router.post("/api/runs/{run_id}/export")
async def export_run(run_id: str, request: Request) -> dict:
    require_role(request, "doctor")
    row = _row_or_404(request, run_id)
    if row.status != "approved" or not row.bundle_json:
        raise HTTPException(status_code=409, detail="Approve the bundle before export")
    bundle = json.loads(row.bundle_json)
    base = request.app.state.settings.hapi_base_url.rstrip("/")
    response = await request.app.state.http.post(
        base,
        json=bundle,
        headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=response.text[:500])
    request.app.state.db.update(run_id, status="exported")
    return {"ok": True, "server": base, "response": response.json()}


@router.post("/api/runs/{run_id}/dictate")
async def dictate_run(
    run_id: str,
    request: Request,
    audio: UploadFile = File(),
) -> dict:
    require_role(request, "doctor")
    row = _row_or_404(request, run_id)
    if row.status not in {"reviewing", "approved", "exported"}:
        raise HTTPException(status_code=409, detail="The record is not ready for a visit note")
    wav = await audio.read()
    bus: EventBus = request.app.state.bus
    opened = False
    if not bus.accepting(run_id):
        bus.open(run_id)
        opened = True
    try:
        encounter, transcript = await request.app.state.orchestrator._encounter(run_id, wav)
    finally:
        if opened and bus.exists(run_id):
            bus.close(run_id)
    request.app.state.db.update(
        run_id,
        status="reviewing",
        encounter_json=encounter.model_dump_json(),
        transcript=transcript,
        bundle_json=None,
    )
    updated = _row_or_404(request, run_id)
    return _public(updated)


@router.post("/api/runs/{run_id}/share")
async def share_run(run_id: str, request: Request) -> dict:
    user = require_role(request, "patient")
    row = _row_or_404(request, run_id)
    if row.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Unknown run")
    if row.status not in {"reviewing", "approved", "exported"}:
        raise HTTPException(status_code=409, detail="The record is not ready to share")
    now = datetime.now(UTC)
    expires = now + timedelta(hours=24)
    old_expires = row.share_expires
    if old_expires is not None and old_expires.tzinfo is None:
        old_expires = old_expires.replace(tzinfo=UTC)
    active_code = row.share_code if old_expires and old_expires > now else None
    for _ in range(20):
        code = active_code or share_code()
        # An expired code must not become valid again.
        if not active_code and code == row.share_code:
            continue
        try:
            with _db(request).session() as session:
                stored = session.get(RunRow, run_id)
                if stored is None or stored.owner_id != user.id:
                    raise HTTPException(status_code=404, detail="Unknown run")
                stored.share_code = code
                stored.share_expires = expires
                session.add(stored)
                session.commit()
            return {"code": code, "expires": expires.isoformat()}
        except IntegrityError:
            # The database's unique index arbitrates concurrent code creation.
            active_code = None
    raise HTTPException(status_code=503, detail="Could not create a share code. Try again.")


@router.get("/api/runs/{run_id}/events")
async def run_events(
    run_id: str, request: Request, last_event_id: str | None = Header(default=None)
) -> EventSourceResponse:
    _row_or_404(request, run_id)
    bus: EventBus = request.app.state.bus
    if not bus.exists(run_id):
        raise HTTPException(status_code=404, detail="Unknown run")
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream():
        async for event in bus.subscribe(run_id, after_seq=after_seq):
            # Stop delivering data after the session or record grant is revoked/expired.
            try:
                _row_or_404(request, run_id)
            except HTTPException:
                break
            yield {"event": "pipeline", "id": str(event.seq), "data": event.model_dump_json()}
        yield {"event": "end", "data": "{}"}

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
