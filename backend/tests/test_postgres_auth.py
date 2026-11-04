"""PostgreSQL integration; set TEST_POSTGRES_URL to a disposable database."""

import os
import re
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete

from app import demo
from app.auth.email import _reserve
from app.auth.security import digest
from app.config import Settings
from app.main import create_app
from app.pipeline.chart_digest import DigestItem, DigestResult
from app.store.db import (
    AuthCounter,
    AuthSession,
    AuthUser,
    ChartActivity,
    ChartConnection,
    ClinicalSummary,
    RunGrant,
    RunRow,
    Visit,
    VisitReference,
)

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL is not configured")


def test_postgres_migration_auth_and_atomic_budget(tmp_path: Path):
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = str(PG_URL)
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        check=False,
    )
    assert migration.returncode == 0, "PostgreSQL Alembic migration failed"
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=PG_URL,
        runs_dir=str(tmp_path / "runs"),
        app_base_url="http://localhost:5173",
    )
    with TestClient(create_app(settings), headers={"Origin": "http://localhost:5173"}) as client:
        email = f"test-{uuid.uuid4().hex}@example.org"
        password = "long safe passphrase 123"
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": "Test Person",
                "email": email,
                "password": password,
                "role": "doctor",
            },
        )
        assert response.status_code == 202, response.text
        mail = next((tmp_path / "mail").glob("*.eml")).read_text(encoding="utf-8")
        token = re.search(r"#token=([^\s]+)", mail).group(1)
        response = client.post("/api/auth/verify", json={"token": token, "password": password})
        assert response.status_code == 200, response.text
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        assert response.json()["user"]["role"] == "doctor"
        doctor_id = response.json()["user"]["id"]
        client.headers["x-csrf-token"] = response.json()["csrf_token"]
        patient_id, record_id, note_id = [uuid.uuid4().hex for _ in range(3)]
        now = datetime.now(UTC)
        with client.app.state.db.session() as session:
            session.add(
                AuthUser(
                    id=patient_id,
                    email=f"{patient_id}@example.org",
                    full_name="Fictional patient",
                    password_hash="unused",
                    role="patient",
                    verified=True,
                    created_at=now,
                )
            )
            session.commit()
            session.add(
                RunRow(
                    id=record_id,
                    owner_id=patient_id,
                    status="reviewing",
                    created_at=now,
                    pseudonym="Fictional",
                )
            )
            session.add(
                ChartConnection(
                    patient_id=patient_id, doctor_id=doctor_id, status="approved", requested_at=now
                )
            )
            session.commit()
            session.add(
                ClinicalSummary(
                    id=note_id,
                    run_id=record_id,
                    author_id=doctor_id,
                    transcript="Fictional note",
                    summary_en="Fictional note",
                    summary_bn="কাল্পনিক নোট",
                    status="published",
                    created_at=now,
                    published_at=now,
                )
            )
            session.commit()
        calls = []

        async def provider(*args, **kwargs):
            calls.append(1)
            return SimpleNamespace(
                value=DigestResult(
                    narrative_en="Fictional health narrative",
                    narrative_bn="কাল্পনিক স্বাস্থ্য বিবরণ",
                    items=[
                        DigestItem(
                            category="assessment",
                            text_en="Fictional note",
                            text_bn="কাল্পনিক নোট",
                            source_ids=[note_id],
                        )
                    ],
                )
            )

        client.app.state.router.structured = provider
        path = f"/api/chart/patients/{patient_id}/summary"
        assert client.get(path).json()["published_note_count"] == 1
        assert client.post(path).json()["status"] == "ready"
        assert client.post(path).json()["status"] == "ready"
        assert len(calls) == 1
        # The additive medicine migration supports durable patient-reported use.
        doctor_cookie = client.cookies.get("mededge_session")
        doctor_csrf = client.headers["x-csrf-token"]
        patient_token = uuid.uuid4().hex
        with client.app.state.db.session() as session:
            session.add(
                AuthSession(
                    id=digest(patient_token),
                    user_id=patient_id,
                    csrf_token="fictional-csrf",
                    expires_at=now + timedelta(hours=1),
                )
            )
            session.commit()
        client.cookies.clear()
        client.cookies.set("mededge_session", patient_token)
        client.headers["x-csrf-token"] = "fictional-csrf"
        medicines_path = f"/api/chart/patients/{patient_id}/medicines"
        medicine = {"id": uuid.uuid4().hex, "name": "Fictional medicine 5 mg"}
        assert client.post(medicines_path, json=medicine).status_code == 200
        assert client.post(medicines_path, json=medicine).status_code == 200
        assert len(client.get(medicines_path).json()["medicines"]) == 1
        client.cookies.clear()
        client.cookies.set("mededge_session", doctor_cookie)
        client.headers["x-csrf-token"] = doctor_csrf
        assert client.get(medicines_path).status_code == 200

        # Explicit migration and prescription publication on PostgreSQL.
        def start_visit(index):
            return client.post(
                "/api/visits",
                json={
                    "patient_id": patient_id,
                    "idempotency_key": f"concurrent-visit-{index}",
                },
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            visit_responses = list(executor.map(start_visit, (1, 2)))
        assert all(response.status_code == 200 for response in visit_responses)
        visit_id = visit_responses[0].json()["id"]
        assert visit_responses[1].json()["id"] == visit_id
        created = client.post(
            f"/api/chart/patients/{patient_id}/prescriptions",
            data={"mode": "manual", "idempotency_key": uuid.uuid4().hex, "visit_id": visit_id},
        )
        assert created.status_code == 200, created.text
        rx_id = created.json()["run_id"]
        assert client.get(f"/api/runs/{rx_id}").json()["input_mode"] == "manual_prescription"
        summary_path = f"/api/chart/records/{rx_id}/summaries"
        rx_note = client.get(summary_path).json()["summaries"][0]
        body = {
            "transcript": "Fictional manually authored prescription",
            "summary_en": "Fictional note",
            "summary_bn": "কাল্পনিক নোট",
            "expected_revision": 1,
            "reviewed_both_languages": True,
            "prescription": [
                {
                    "id": "fictional",
                    "name": "Fictional medicine",
                    "morning": "½",
                    "noon": "0",
                    "night": "",
                    "duration": "চলবে",
                    "confirmed": True,
                }
            ],
        }
        assert (
            client.post(f"{summary_path}/{rx_note['id']}?publish=true", json=body).status_code
            == 200
        )
        assert client.get(summary_path).json()["summaries"][0]["prescription"][0]["morning"] == "½"
        visit = client.get(f"/api/visits/{visit_id}").json()
        assert visit["records"][0]["run_id"] == rx_id
        assert (
            client.post(
                f"/api/visits/{visit_id}/complete", json={"expected_revision": visit["revision"]}
            ).status_code
            == 200
        )

        assert client.post(f"/api/chart/connections/{patient_id}/revoke").status_code == 200
        assert client.get(medicines_path).status_code == 404
        assert client.get(path).status_code == 404
        assert client.post(path).status_code == 404
        assert client.get(f"/api/visits/{visit_id}").status_code == 404

        # Two concurrent requests share a single remaining daily reservation.
        with client.app.state.db.session() as session:
            session.exec(delete(AuthCounter).where(AuthCounter.key.like("mail:%")))
            session.commit()
        settings.auth_email_daily_limit = 1
        request = SimpleNamespace(app=client.app)
        barrier = Barrier(2)

        def reserve(index):
            barrier.wait()
            try:
                _reserve(request, f"recipient-{index}@example.org")
                return 200
            except HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = sorted(executor.map(reserve, (1, 2)))
        assert results == [200, 429]

        # Real foreign keys must not let stale demo cleanup break startup.
        demo_settings = settings.model_copy(
            update={
                "demo_patient_email": "demo-patient@example.test",
                "demo_doctor_email": "demo-doctor@example.test",
                "demo_password": SecretStr("fictional-test-passphrase"),
            }
        )
        db = client.app.state.db
        demo.seed(db, demo_settings)
        stale_id = uuid.uuid4().hex
        old = now - timedelta(hours=5)
        db.add(
            RunRow(
                id=stale_id,
                owner_id=demo.PATIENT_ID,
                status="reviewing",
                created_at=old,
                pseudonym="Fictional",
            )
        )
        with db.session() as session:
            session.add(
                Visit(
                    id="stale-demo-visit",
                    patient_id=demo.PATIENT_ID,
                    doctor_id=demo.DOCTOR_ID,
                    created_at=old,
                    submission_key="demo",
                )
            )
            session.flush()
            session.add(
                VisitReference(
                    visit_id="stale-demo-visit",
                    run_id=stale_id,
                    added_by=demo.DOCTOR_ID,
                    added_at=old,
                )
            )
            session.add(RunGrant(run_id=stale_id, user_id=demo.DOCTOR_ID, expires_at=now))
            session.add(
                ChartActivity(
                    id=uuid.uuid4().hex,
                    patient_id=demo.PATIENT_ID,
                    actor_id=demo.DOCTOR_ID,
                    action="prescription_created",
                    occurred_at=old,
                    run_id=stale_id,
                )
            )
            session.commit()
        demo.reset(db, demo_settings)
        assert db.get(stale_id) is None
        with db.session() as session:
            assert session.get(Visit, "stale-demo-visit") is None
        assert db.get(record_id) is not None
