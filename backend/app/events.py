import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Stage(StrEnum):
    SYSTEM = "system"
    SEGMENT = "segment"
    REDACT = "redact"
    EXTRACT = "extract"
    TRANSCRIBE = "transcribe"
    STRUCTURE = "structure"
    AGENT = "agent"
    VERIFY = "verify"
    EXPORT = "export"


class EventKind(StrEnum):
    STARTED = "started"
    PROGRESS = "progress"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRY = "retry"
    WARNING = "warning"
    ERROR = "error"
    COMPLETED = "completed"


class PipelineEvent(BaseModel):
    run_id: str
    seq: int
    ts: datetime
    stage: Stage
    kind: EventKind
    message: str
    model: str | None = None
    latency_ms: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)


_CLOSED = object()


class _Channel:
    def __init__(self) -> None:
        self.history: list[PipelineEvent] = []
        self.subscribers: set[asyncio.Queue[Any]] = set()
        self.closed = False


class EventBus:
    """Per-run event log with live fan-out. Late subscribers replay history first."""

    def __init__(self, max_runs: int = 200) -> None:
        self._channels: OrderedDict[str, _Channel] = OrderedDict()
        self._max_runs = max_runs

    def open(self, run_id: str) -> None:
        self._channels[run_id] = _Channel()
        while len(self._channels) > self._max_runs:
            oldest_id, oldest = next(iter(self._channels.items()))
            if not oldest.closed:
                break
            del self._channels[oldest_id]

    def exists(self, run_id: str) -> bool:
        return run_id in self._channels

    def history(self, run_id: str) -> list[PipelineEvent]:
        return list(self._channels[run_id].history)

    def publish(
        self,
        run_id: str,
        stage: Stage,
        kind: EventKind,
        message: str,
        *,
        model: str | None = None,
        latency_ms: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> PipelineEvent:
        channel = self._channels[run_id]
        if channel.closed:
            raise RuntimeError(f"Run {run_id} is already closed")
        event = PipelineEvent(
            run_id=run_id,
            seq=len(channel.history) + 1,
            ts=datetime.now(UTC),
            stage=stage,
            kind=kind,
            message=message,
            model=model,
            latency_ms=latency_ms,
            data=data or {},
        )
        channel.history.append(event)
        for queue in channel.subscribers:
            queue.put_nowait(event)
        return event

    def close(self, run_id: str) -> None:
        channel = self._channels[run_id]
        channel.closed = True
        for queue in channel.subscribers:
            queue.put_nowait(_CLOSED)

    async def subscribe(self, run_id: str, after_seq: int = 0) -> AsyncIterator[PipelineEvent]:
        channel = self._channels[run_id]
        queue: asyncio.Queue[Any] = asyncio.Queue()
        backlog = list(channel.history)
        already_closed = channel.closed
        channel.subscribers.add(queue)
        try:
            for event in backlog:
                if event.seq > after_seq:
                    yield event
            if already_closed:
                return
            while True:
                item = await queue.get()
                if item is _CLOSED:
                    return
                if item.seq > after_seq:
                    yield item
        finally:
            channel.subscribers.discard(queue)
