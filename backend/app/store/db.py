from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


class RunRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str
    created_at: datetime
    pseudonym: str
    document_type: str | None = None
    extraction_json: str | None = None
    encounter_json: str | None = None
    bundle_json: str | None = None
    transcript: str | None = None
    extractor_model: str | None = None
    used_fallback: bool = False
    replay: bool = False
    inject_fault: bool = False
    share_code: str | None = None
    share_expires: datetime | None = None


class SpendRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    day: str
    usd: float


class TermCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    payload: str


class Database:
    def __init__(self, settings: Settings):
        url = settings.database_url
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            path = (BACKEND_DIR / url.removeprefix("sqlite:///")).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            url = "sqlite:///" + path.as_posix()
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(self.engine)
        self.runs_dir = (BACKEND_DIR / settings.runs_dir).resolve()
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def session(self) -> Session:
        return Session(self.engine)

    def add(self, row: RunRow) -> None:
        with self.session() as session:
            session.add(row)
            session.commit()

    def save(self, row: RunRow) -> None:
        with self.session() as session:
            session.add(row)
            session.commit()

    def get(self, run_id: str) -> RunRow | None:
        with self.session() as session:
            return session.get(RunRow, run_id)

    def update(self, run_id: str, **values: object) -> RunRow | None:
        with self.session() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                return None
            for key, value in values.items():
                setattr(row, key, value)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def by_share(self, code: str) -> RunRow | None:
        with self.session() as session:
            row = session.exec(select(RunRow).where(RunRow.share_code == code)).first()
            if row is None or row.share_expires is None:
                return None
            expires = row.share_expires
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires < datetime.now(UTC):
                return None
            return row

    def spent_today(self) -> float:
        day = datetime.now(UTC).date().isoformat()
        with self.session() as session:
            total = session.exec(select(func.sum(SpendRow.usd)).where(SpendRow.day == day)).one()
        return float(total or 0)

    def add_spend(self, usd: float) -> None:
        with self.session() as session:
            session.add(SpendRow(day=datetime.now(UTC).date().isoformat(), usd=usd))
            session.commit()

    def purge(self, hours: int = 24) -> None:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        with self.session() as session:
            rows = session.exec(select(RunRow)).all()
            for row in rows:
                created = row.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if created < cutoff:
                    session.delete(row)
            session.commit()
