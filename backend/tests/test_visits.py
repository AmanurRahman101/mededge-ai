from datetime import UTC, datetime, timedelta

from app.auth.security import digest
from app.store.db import AuthSession, AuthUser, ChartConnection, Visit
from tests.test_access import access_client, sign_in  # noqa: F401


def setup_doctors(client):
    now = datetime.now(UTC)
    with client.app.state.db.session() as session:
        session.add(
            AuthUser(
                id="doctor2",
                full_name="Doctor Two",
                email="two@example.test",
                role="doctor",
                password_hash="unused",
                verified=True,
                created_at=now,
            )
        )
        session.add(
            AuthSession(
                id=digest("doctor2"),
                user_id="doctor2",
                csrf_token="csrf-doctor2",
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
        )
        for doctor in ("doctor", "doctor2"):
            session.add(
                ChartConnection(
                    patient_id="patient1", doctor_id=doctor, status="approved", requested_at=now
                )
            )
        session.commit()
    sign_in(client, "doctor")


def start(client, key="start"):
    response = client.post("/api/visits", json={"patient_id": "patient1", "idempotency_key": key})
    assert response.status_code == 200, response.text
    return response.json()


def test_visit_isolation_idempotency_and_patient_ownership(request):
    client = request.getfixturevalue("access_client")
    setup_doctors(client)
    visit = start(client)
    assert start(client)["id"] == visit["id"]
    assert start(client, "another-click")["id"] == visit["id"]
    note = client.post(f"/api/visits/{visit['id']}/notes", json={"idempotency_key": "note"}).json()
    run_id = note["run_id"]
    assert client.app.state.db.get(run_id).owner_id == "patient1"
    assert client.app.state.db.get(run_id).visit_id == visit["id"]
    sign_in(client, "doctor2")
    assert client.get(f"/api/visits/{visit['id']}").status_code == 404
    assert client.get(f"/api/runs/{run_id}").status_code == 404
    records = client.get("/api/chart/records?patient_id=patient1&include_source=false").json()
    assert run_id not in [r["run_id"] for r in records["records"]]
    own_visit = start(client, "doctor2-visit")
    assert own_visit["id"] != visit["id"]
    sign_in(client, "patient2")
    assert client.get(f"/api/visits/{visit['id']}").status_code == 404
    sign_in(client, "patient1")
    result = client.get(f"/api/visits/{visit['id']}").json()
    assert result["can_edit"] is False
    assert "transcript" not in result["records"][0]
    assert (
        client.post(
            "/api/visits", json={"patient_id": "patient1", "idempotency_key": "x"}
        ).status_code
        == 403
    )


def test_visit_publication_completion_revocation_and_no_guessed_legacy_visit(request):
    client = request.getfixturevalue("access_client")
    setup_doctors(client)
    visit = start(client)
    assert client.app.state.db.get("record").visit_id is None
    linked = client.post(f"/api/visits/{visit['id']}/reports", json={"run_id": "record"})
    assert linked.status_code == 200
    assert client.app.state.db.get("record").visit_id is None
    assert (
        client.post(f"/api/visits/{visit['id']}/reports", json={"run_id": "record"}).status_code
        == 200
    )
    note = client.post(f"/api/visits/{visit['id']}/notes", json={"idempotency_key": "note"}).json()
    run_id = note["run_id"]
    summary = client.get(f"/api/chart/records/{run_id}/summaries").json()["summaries"][0]
    details = client.get(f"/api/visits/{visit['id']}").json()
    assert (
        client.post(
            f"/api/visits/{visit['id']}/complete", json={"expected_revision": details["revision"]}
        ).status_code
        == 409
    )
    body = {
        "expected_revision": summary["revision"],
        "summary_en": "Fictional reviewed follow-up.",
        "summary_bn": "কাল্পনিক পর্যালোচনা।",
        "transcript": "Doctor's original note.",
        "reviewed_both_languages": True,
        "acknowledge_unresolved": True,
    }
    assert (
        client.post(
            f"/api/chart/records/{run_id}/summaries/{summary['id']}?publish=true", json=body
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/visits/{visit['id']}/complete", json={"expected_revision": 1}
        ).status_code
        == 409
    )
    response = client.post(
        f"/api/visits/{visit['id']}/complete", json={"expected_revision": details["revision"]}
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(
            f"/api/visits/{visit['id']}/notes", json={"idempotency_key": "late"}
        ).status_code
        == 409
    )
    sign_in(client, "doctor2")
    assert client.get(f"/api/visits/{visit['id']}").status_code == 200
    assert client.get(f"/api/runs/{run_id}").status_code == 200
    assert (
        client.post(
            f"/api/visits/{visit['id']}/notes", json={"idempotency_key": "intrude"}
        ).status_code
        == 404
    )
    sign_in(client, "patient1")
    assert client.post("/api/chart/connections/doctor2/revoke").status_code == 200
    sign_in(client, "doctor2")
    assert client.get(f"/api/visits/{visit['id']}").status_code == 404
    assert client.get(f"/api/runs/{run_id}").status_code == 404
    sign_in(client, "doctor")
    new_visit = start(client, "next-consultation")
    assert new_visit["id"] != visit["id"]


def test_prescription_is_bound_to_own_open_visit_and_idempotency(request):
    client = request.getfixturevalue("access_client")
    setup_doctors(client)
    visit = start(client)
    response = client.post(
        "/api/chart/patients/patient1/prescriptions",
        data={
            "mode": "manual",
            "idempotency_key": "visit-rx",
            "visit_id": visit["id"],
        },
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assert client.app.state.db.get(run_id).visit_id == visit["id"]
    assert client.get(f"/api/runs/{run_id}").json()["visit_id"] == visit["id"]
    sign_in(client, "doctor2")
    assert (
        client.post(
            "/api/chart/patients/patient1/prescriptions",
            data={
                "mode": "manual",
                "idempotency_key": "intrude",
                "visit_id": visit["id"],
            },
        ).status_code
        == 404
    )
    sign_in(client, "doctor")
    with client.app.state.db.session() as session:
        row = session.get(Visit, visit["id"])
        row.status = "completed"
        session.add(row)
        session.commit()
    assert (
        client.post(
            "/api/chart/patients/patient1/prescriptions",
            data={
                "mode": "manual",
                "idempotency_key": "late",
                "visit_id": visit["id"],
            },
        ).status_code
        == 409
    )


def test_discard_draft_removes_files_and_references_without_touching_earlier_report(request):
    from app.store.db import ClinicalSummary, RunRow, VisitReference

    client = request.getfixturevalue("access_client")
    setup_doctors(client)
    visit = start(client)
    response = client.post(f"/api/visits/{visit['id']}/notes", json={"idempotency_key": "discard"})
    run_id = response.json()["run_id"]
    folder = client.app.state.db.runs_dir / run_id
    folder.mkdir(parents=True)
    (folder / "fictional.txt").write_text("fictional")
    assert client.delete(f"/api/visits/{visit['id']}").status_code == 409
    sign_in(client, "doctor2")
    assert client.delete(f"/api/visits/{visit['id']}/drafts/{run_id}").status_code == 404
    sign_in(client, "doctor")
    assert client.delete(f"/api/visits/{visit['id']}/drafts/{run_id}").status_code == 200
    assert not folder.exists()
    assert client.app.state.db.get(run_id) is None
    with client.app.state.db.session() as session:
        from sqlmodel import select

        assert not session.exec(
            select(ClinicalSummary).where(ClinicalSummary.run_id == run_id)
        ).all()
        earlier = session.exec(select(RunRow).where(RunRow.owner_id == "patient1")).first()
        earlier_id = earlier.id if earlier else None
        if earlier:
            session.add(
                VisitReference(
                    visit_id=visit["id"],
                    run_id=earlier.id,
                    added_by="doctor",
                    added_at=datetime.now(UTC),
                )
            )
            session.commit()
    if earlier_id:
        sign_in(client, "patient1")
        assert client.delete(f"/api/chart/records/{earlier_id}").status_code == 200
        sign_in(client, "doctor")
    assert client.delete(f"/api/visits/{visit['id']}").status_code == 200
    assert client.get(f"/api/visits/{visit['id']}").status_code == 404
