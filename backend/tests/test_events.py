import asyncio

import pytest

from app.events import EventBus, EventKind, Stage


async def collect(bus: EventBus, run_id: str, after_seq: int = 0) -> list[str]:
    return [event.message async for event in bus.subscribe(run_id, after_seq=after_seq)]


async def test_late_subscriber_replays_history_then_follows_live():
    bus = EventBus()
    bus.open("r1")
    bus.publish("r1", Stage.SEGMENT, EventKind.STARTED, "first")

    task = asyncio.create_task(collect(bus, "r1"))
    await asyncio.sleep(0)
    bus.publish("r1", Stage.SEGMENT, EventKind.COMPLETED, "second")
    bus.close("r1")

    assert await asyncio.wait_for(task, timeout=1) == ["first", "second"]


async def test_resume_skips_events_already_seen():
    bus = EventBus()
    bus.open("r2")
    for message in ("a", "b", "c"):
        bus.publish("r2", Stage.AGENT, EventKind.PROGRESS, message)
    bus.close("r2")

    assert await collect(bus, "r2", after_seq=2) == ["c"]


def test_sequence_numbers_increase_and_closed_runs_reject_events():
    bus = EventBus()
    bus.open("r3")
    first = bus.publish("r3", Stage.VERIFY, EventKind.STARTED, "x")
    second = bus.publish("r3", Stage.VERIFY, EventKind.COMPLETED, "y")
    assert (first.seq, second.seq) == (1, 2)

    bus.close("r3")
    with pytest.raises(RuntimeError):
        bus.publish("r3", Stage.VERIFY, EventKind.ERROR, "late")


def test_oldest_closed_runs_are_evicted():
    bus = EventBus(max_runs=2)
    for run_id in ("a", "b"):
        bus.open(run_id)
        bus.close(run_id)
    bus.open("c")
    assert not bus.exists("a")
    assert bus.exists("b") and bus.exists("c")
