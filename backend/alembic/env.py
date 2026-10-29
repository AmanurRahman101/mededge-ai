from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import SQLModel

from alembic import context
from app.config import Settings
from app.store import db  # noqa: F401 - register SQLModel tables

settings = Settings()
url = settings.database_url_unpooled or settings.database_url
if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
    path = Path(__file__).resolve().parents[1] / url.removeprefix("sqlite:///")
    path.parent.mkdir(parents=True, exist_ok=True)
    url = "sqlite:///" + path.resolve().as_posix()
elif url.startswith("postgres://"):
    url = "postgresql+psycopg://" + url.removeprefix("postgres://")
elif url.startswith("postgresql://"):
    url = "postgresql+psycopg://" + url.removeprefix("postgresql://")

engine = create_engine(url, pool_pre_ping=True)
with engine.connect() as connection:
    context.configure(
        connection=connection, target_metadata=SQLModel.metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()
