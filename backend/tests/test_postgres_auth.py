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
from sqlalchemy import delete

from app.auth.email import _reserve
from app.auth.security import digest
from app.config import Settings
from app.main import create_app
from app.pipeline.chart_digest import DigestItem, DigestResult
from app.store.db import (
    AuthCounter,
    AuthSession,
    AuthUser,
    ChartConnection,
    ClinicalSummary,
    RunRow,
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
        assert client.post(f"/api/chart/connections/{patient_id}/revoke").status_code == 200
        assert client.get(medicines_path).status_code == 404
        assert client.get(path).status_code == 404
        assert client.post(path).status_code == 404

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
