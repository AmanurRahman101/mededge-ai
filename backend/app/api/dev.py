import asyncio
import uuid

from fastapi import APIRouter, Request

from app.events import EventBus, EventKind, Stage

router = APIRouter(prefix="/api/dev")

# Scripted trace for building the frontend without spending credits.
# Every event carries data.simulated=True so the UI can label it.
_SCRIPT: list[tuple[Stage, EventKind, str, str | None]] = [
    (Stage.SEGMENT, EventKind.STARTED, "Segmenting page regions", "sam-3.1"),
    (Stage.SEGMENT, EventKind.COMPLETED, "Found page, results table, 1 barcode", "sam-3.1"),
    (Stage.REDACT, EventKind.COMPLETED, "Blurred header band and barcode locally", None),
    (Stage.EXTRACT, EventKind.STARTED, "Reading redacted table", "muse-spark-1.3"),
    (Stage.EXTRACT, EventKind.COMPLETED, "Extracted 7 rows", "muse-spark-1.3"),
    (Stage.AGENT, EventKind.TOOL_CALL, "search_loinc('S. Creatinine')", "muse-spark-1.3"),
    (Stage.AGENT, EventKind.TOOL_RESULT, "Resolved to LOINC 2160-0", None),
    (Stage.VERIFY, EventKind.RETRY, "Attempt 1: Observation.status missing", None),
    (Stage.VERIFY, EventKind.COMPLETED, "Attempt 2: bundle valid, 0 errors", None),
]


async def _play(bus: EventBus, run_id: str, delay_s: float) -> None:
    try:
        for stage, kind, message, model in _SCRIPT:
            await asyncio.sleep(delay_s)
            bus.publish(run_id, stage, kind, message, model=model, data={"simulated": True})
    finally:
        bus.close(run_id)


@router.post("/simulate")
async def simulate(request: Request, delay_ms: int = 400) -> dict:
    bus: EventBus = request.app.state.bus
    run_id = f"sim-{uuid.uuid4().hex[:10]}"
    bus.open(run_id)
    task = asyncio.create_task(_play(bus, run_id, max(delay_ms, 0) / 1000))
    tasks: set[asyncio.Task] = request.app.state.tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return {"run_id": run_id, "events_url": f"/api/runs/{run_id}/events"}
