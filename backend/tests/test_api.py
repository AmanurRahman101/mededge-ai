import pytest
from fastapi.testclient import TestClient

from app.api.dev import _play
from app.config import Settings
from app.events import EventBus
from app.main import create_app

SECRET = "secret-key-123"


def client_for(**overrides) -> TestClient:
    settings = Settings(_env_file=None, model_api_key=SECRET, **overrides)
    return TestClient(create_app(settings))


def test_health_reports_roles_without_leaking_the_key():
    with client_for() as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert SECRET not in response.text
    data = response.json()
    assert data["meta_key_present"] is True
    assert data["roles"]["extractor"] == [{"target": "meta:muse-spark-1.3", "configured": True}]
    assert data["sam"] == {"provider": "meta", "model": "sam-3.1"}


def test_live_provider_probe_requires_a_session():
    with client_for() as client:
        response = client.get("/api/health", params={"probe_providers": "true"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_simulated_run_streams_labeled_events_then_ends():
    bus = EventBus()
    bus.open("demo")
    await _play(bus, "demo", 0)
    events = [event.model_dump() async for event in bus.subscribe("demo")]
    assert len(events) == 9
    assert [e["seq"] for e in events] == list(range(1, 10))
    assert all(e["data"]["simulated"] for e in events)


def test_unknown_run_requires_authentication():
    with client_for() as client:
        assert client.get("/api/runs/nope/events").status_code == 401


def test_dev_routes_are_off_by_default():
    with client_for() as client:
        assert client.post("/api/dev/simulate").status_code == 404
