import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_production_rejects_unconfigured_email_and_database():
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_base_url="https://mededge.example",
        database_url="sqlite:///ignored.db",
    )
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        with TestClient(create_app(settings)):
            pass


def test_production_rejects_the_default_pseudonym_salt():
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_base_url="https://mededge.example",
        database_url="postgresql://u:p@localhost/db",
    )
    with pytest.raises(RuntimeError, match="PSEUDONYM_SALT"):
        with TestClient(create_app(settings)):
            pass


def test_migration_keeps_legacy_rows_ownerless(tmp_path: Path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE runrow (id VARCHAR PRIMARY KEY, status VARCHAR NOT NULL, "
            "created_at DATETIME NOT NULL, pseudonym VARCHAR NOT NULL, "
            "share_code VARCHAR, share_expires DATETIME)"
        )
        connection.executemany(
            "INSERT INTO runrow (id, status, created_at, pseudonym, share_code) "
            "VALUES (?, 'reviewing', '2026-01-01', 'ANON', 'ABC234')",
            [("old-a",), ("old-b",)],
        )
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    env["DATABASE_URL_UNPOOLED"] = ""
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT id, owner_id, share_code FROM runrow ORDER BY id"
        ).fetchall()
        assert rows == [("old-a", None, None), ("old-b", None, None)]
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20261101_trace",
        )


def test_migrations_prefer_direct_database_url(tmp_path: Path):
    runtime_database = tmp_path / "runtime.db"
    migration_database = tmp_path / "migrations.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{runtime_database.as_posix()}"
    env["DATABASE_URL_UNPOOLED"] = f"sqlite:///{migration_database.as_posix()}"
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not runtime_database.exists()
    with sqlite3.connect(migration_database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20261101_trace",
        )
