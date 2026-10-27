import json

from fastapi.testclient import TestClient

from app.config import Settings
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


def test_simulated_run_streams_labeled_events_then_ends():
    with client_for(enable_dev_routes=True) as client:
        run = client.post("/api/dev/simulate", params={"delay_ms": 0}).json()
        with client.stream("GET", run["events_url"]) as response:
            lines = list(response.iter_lines())

    payloads = [json.loads(line[len("data: ") :]) for line in lines if line.startswith("data: ")]
    events = [p for p in payloads if p]
    assert len(events) == 9
    assert [e["seq"] for e in events] == list(range(1, 10))
    assert all(e["data"]["simulated"] for e in events)
    assert "event: end" in lines


def test_unknown_run_is_404():
    with client_for() as client:
        assert client.get("/api/runs/nope/events").status_code == 404


def test_dev_routes_are_off_by_default():
    with client_for() as client:
        assert client.post("/api/dev/simulate").status_code == 404
