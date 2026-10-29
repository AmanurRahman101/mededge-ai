"""PostgreSQL integration; set TEST_POSTGRES_URL to a disposable database."""

import os
import re
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth.email import _reserve
from app.config import Settings
from app.main import create_app
from app.store.db import AuthCounter

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
