from datetime import UTC, datetime, timedelta

from app.auth.security import digest
from app.store.db import ChartConnection, ClinicalSummary, ConnectionCode, RunRow
from tests.test_access import access_client, sign_in  # noqa: F401


def test_doctor_overview_requires_consent_and_excludes_drafts(request):
    client = request.getfixturevalue("access_client")
    now = datetime.now(UTC)
    with client.app.state.db.session() as session:
        session.add(
            ChartConnection(
                patient_id="patient1", doctor_id="doctor", status="pending", requested_at=now
            )
        )
        session.add(
            RunRow(
                id="archived",
                status="reviewing",
                created_at=now + timedelta(seconds=1),
                pseudonym="PT-A",
                owner_id="patient1",
                archived=True,
            )
        )
        for name, status in [("published", "published"), ("draft", "draft")]:
            session.add(
                ClinicalSummary(
                    id=name,
                    run_id="record",
                    author_id="doctor",
                    status=status,
                    transcript="private draft transcript",
                    summary_en=name,
                    summary_bn="বাংলা",
                    created_at=now,
                    published_at=now if status == "published" else None,
                )
            )
        session.commit()
    client.app.state.db.update(
        "record",
        extraction_json='{"medications":[{"raw_text":"Example 10 mg"}],'
        '"advised_tests":[{"raw_name":"CRP"}]}',
    )
    sign_in(client, "doctor")
    assert client.get("/api/chart/patients/patient1/overview").status_code == 404
    with client.app.state.db.session() as session:
        connection = session.get(ChartConnection, ("patient1", "doctor"))
        connection.status = "approved"
        session.add(connection)
        session.commit()
    response = client.get("/api/chart/patients/patient1/overview", params={"limit": 1})
    assert response.status_code == 200
    assert response.json()["has_more"] is True
    assert response.json()["records"][0]["archived"] is True
    record = client.get(
        "/api/chart/patients/patient1/overview", params={"limit": 1, "offset": 1}
    ).json()["records"][0]
    assert record["medications"] == ["Example 10 mg"]
    assert record["tests"] == ["CRP"]
    assert [note["summary_en"] for note in record["notes"]] == ["published"]
    assert "transcript" not in record["notes"][0]
    assert client.get("/api/chart/patients/patient2/overview").status_code == 404
    with client.app.state.db.session() as session:
        connection = session.get(ChartConnection, ("patient1", "doctor"))
        connection.status = "revoked"
        session.add(connection)
        session.commit()
    assert client.get("/api/chart/patients/patient1/overview").status_code == 404
    sign_in(client, "patient1")
    assert client.get("/api/chart/patients/patient1/overview").status_code == 403


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
    amendment = client.post("/api/chart/records/record/summaries/summary/amend")
    assert amendment.status_code == 200
    amendment_id = amendment.json()["id"]
    sign_in(client, "patient1")
    assert len(client.get("/api/chart/records/record/summaries").json()["summaries"]) == 1
    sign_in(client, "doctor")
    data["summary_en"] = "Corrected English"
    assert (
        client.post(
            f"/api/chart/records/record/summaries/{amendment_id}?publish=true", json=data
        ).status_code
        == 200
    )
    sign_in(client, "patient1")
    published = client.get("/api/chart/records/record/summaries").json()["summaries"]
    assert len(published) == 2
    assert published[0]["summary_en"] == "English"
    assert published[1]["amends_id"] == "summary"
    assert client.post("/api/chart/connections/doctor/revoke").status_code == 200
    sign_in(client, "doctor")
    assert client.get("/api/chart/records/record/summaries").status_code == 404
