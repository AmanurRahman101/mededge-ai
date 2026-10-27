from fastapi import APIRouter, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.events import EventBus

router = APIRouter()


@router.get("/api/runs/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None),
) -> EventSourceResponse:
    bus: EventBus = request.app.state.bus
    if not bus.exists(run_id):
        raise HTTPException(status_code=404, detail="Unknown run")
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream():
        async for event in bus.subscribe(run_id, after_seq=after_seq):
            yield {"event": "pipeline", "id": str(event.seq), "data": event.model_dump_json()}
        yield {"event": "end", "data": "{}"}

    return EventSourceResponse(stream(), ping=15)
