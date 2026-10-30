from datetime import UTC, datetime, timedelta

from app.auth.security import digest
from app.store.db import ChartConnection, ClinicalSummary, ConnectionCode
from tests.test_access import access_client, sign_in  # noqa: F401


def test_connection_requires_patient_approval_and_revocation_blocks_access(request):
    client = request.getfixturevalue("access_client")
    sign_in(client, "patient1")
    code = client.post("/api/chart/connection-code").json()["code"]
    sign_in(client, "doctor")
    assert client.post("/api/chart/requests", json={"code": code}).json()["status"] == "pending"
    assert client.get("/api/runs/record").status_code == 404
    sign_in(client, "patient1")
    assert (
        client.post("/api/chart/connections/doctor/decision", json={"approve": True}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/chart/connections/doctor/decision",
            json={"approve": True, "consent_version": "chart-access-v1"},
        ).status_code
        == 200
    )
    sign_in(client, "doctor")
    assert client.get("/api/runs/record").status_code == 200
    sign_in(client, "patient1")
    assert client.post("/api/chart/connections/doctor/revoke").status_code == 200
    sign_in(client, "doctor")
    assert client.get("/api/runs/record").status_code == 404


def test_codes_are_single_use_expire_and_retry_collision(request, monkeypatch):
    client = request.getfixturevalue("access_client")
    sign_in(client, "patient1")
    codes = iter("AAAAAABBBBBBCCCCCC")
    monkeypatch.setattr("app.api.chart.secrets.choice", lambda _: next(codes))
    with client.app.state.db.session() as session:
        session.add(
            ConnectionCode(
                id=digest("AAAAAA"),
                patient_id="patient1",
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        session.commit()
    response = client.post("/api/chart/connection-code")
    assert response.status_code == 200
    assert response.json()["code"] == "BBBBBB"
    sign_in(client, "doctor")
    assert client.post("/api/chart/requests", json={"code": "BBBBBB"}).status_code == 200
    assert client.post("/api/chart/requests", json={"code": "BBBBBB"}).status_code == 404
    with client.app.state.db.session() as session:
        session.add(
            ConnectionCode(
                id=digest("CCCCCC"),
                patient_id="patient1",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        session.commit()
    assert client.post("/api/chart/requests", json={"code": "CCCCCC"}).status_code == 404


def test_history_visibility_and_record_delete(request):
    client = request.getfixturevalue("access_client")
    sign_in(client, "patient2")
    assert client.get("/api/chart/records").json()["records"] == []
    assert client.delete("/api/chart/records/record").status_code == 404
    sign_in(client, "patient1")
    assert len(client.get("/api/chart/records").json()["records"]) == 1
    assert (
        client.patch("/api/chart/records/record", json={"title": "Blood work"}).status_code == 200
    )
    assert len(client.get("/api/chart/records", params={"search": "blood"}).json()["records"]) == 1
    assert client.patch("/api/chart/records/record", json={"archived": True}).status_code == 200
    assert client.get("/api/chart/records").json()["records"] == []
    assert len(client.get("/api/chart/records", params={"archived": True}).json()["records"]) == 1
    client.app.state.db.update("record", status="queued")
    assert client.delete("/api/chart/records/record").status_code == 409
    client.app.state.db.update("record", status="reviewing")
    assert client.delete("/api/chart/records/record").status_code == 200
    assert not (client.app.state.db.runs_dir / "record").exists()
    assert client.get("/api/runs/record").status_code == 404


def test_summary_draft_hidden_until_doctor_verifies_and_revocation_blocks_publish(request):
    client = request.getfixturevalue("access_client")
    now = datetime.now(UTC)
    with client.app.state.db.session() as session:
        session.add(
            ChartConnection(
                patient_id="patient1", doctor_id="doctor", status="approved", requested_at=now
            )
        )
        session.add(
            ClinicalSummary(
                id="summary",
                run_id="record",
                author_id="doctor",
                status="draft",
                summary_en="English",
                summary_bn="বাংলা",
                transcript="original",
                unresolved='["uncertain"]',
                created_at=now,
            )
        )
        session.commit()
    sign_in(client, "patient1")
    assert client.get("/api/chart/records/record/summaries").json()["summaries"] == []
    sign_in(client, "doctor")
    url = "/api/chart/records/record/summaries/summary?publish=true"
    data = {"summary_en": "English", "summary_bn": "বাংলা", "transcript": "corrected"}
    assert client.post(url, json=data).status_code == 422
    data.update(reviewed_both_languages=True, acknowledge_unresolved=True)
    assert client.post(url, json=data).status_code == 200
    assert client.post(url, json=data).status_code == 409
    sign_in(client, "patient1")
    assert len(client.get("/api/chart/records/record/summaries").json()["summaries"]) == 1
    assert client.post("/api/chart/connections/doctor/revoke").status_code == 200
    sign_in(client, "doctor")
    assert client.get("/api/chart/records/record/summaries").status_code == 404
