from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import UniqueConstraint, func, inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


class RunRow(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("submitted_by", "submission_key", name="uq_run_submission"),)
    id: str = Field(primary_key=True)
    status: str
    created_at: datetime
    pseudonym: str
    owner_id: str | None = Field(default=None, index=True)
    document_type: str | None = None
    extraction_json: str | None = None
    encounter_json: str | None = None
    bundle_json: str | None = None
    transcript: str | None = None
    extractor_model: str | None = None
    used_fallback: bool = False
    replay: bool = False
    inject_fault: bool = False
    share_code: str | None = Field(default=None, unique=True, index=True)
    share_expires: datetime | None = None
    title: str = "Report"
    submitted_by: str | None = Field(default=None, index=True)
    submission_key: str | None = None
    submission_digest: str | None = None
    archived: bool = False
    trace_json: str | None = None


class ChartConnection(SQLModel, table=True):
    patient_id: str = Field(primary_key=True, foreign_key="authuser.id")
    doctor_id: str = Field(primary_key=True, foreign_key="authuser.id")
    status: str = "pending"
    requested_at: datetime
    decided_at: datetime | None = None
    consent_version: str | None = None
    request_id: str | None = Field(default=None, index=True, unique=True)


class ConnectionCode(SQLModel, table=True):
    id: str = Field(primary_key=True)
    patient_id: str = Field(index=True, foreign_key="authuser.id")
    expires_at: datetime
    consumed_at: datetime | None = None


class ChartActivity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    patient_id: str = Field(index=True, foreign_key="authuser.id")
    actor_id: str = Field(foreign_key="authuser.id")
    action: str
    occurred_at: datetime
    run_id: str | None = Field(default=None, index=True)


class ConsentEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    patient_id: str = Field(index=True, foreign_key="authuser.id")
    doctor_id: str = Field(index=True, foreign_key="authuser.id")
    actor_id: str = Field(foreign_key="authuser.id")
    action: str
    version: str
    scope: str
    consent_text: str
    occurred_at: datetime


class ClinicalSummary(SQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True, foreign_key="runrow.id")
    author_id: str = Field(foreign_key="authuser.id")
    transcript: str
    summary_en: str
    summary_bn: str
    unresolved: str = ""
    status: str = "draft"
    created_at: datetime
    published_at: datetime | None = None
    amends_id: str | None = Field(default=None, foreign_key="clinicalsummary.id")


class SpendRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    day: str
    usd: float


class TermCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    payload: str


class AuthUser(SQLModel, table=True):
    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: str
    password_hash: str
    role: str
    verified: bool = False
    created_at: datetime


class AuthSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True, foreign_key="authuser.id")
    csrf_token: str
    expires_at: datetime


class AuthToken(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True, foreign_key="authuser.id")
    kind: str
    expires_at: datetime
    consumed_at: datetime | None = None


class AuthCounter(SQLModel, table=True):
    key: str = Field(primary_key=True)
    count: int = 0
    expires_at: datetime


class RunGrant(SQLModel, table=True):
    run_id: str = Field(primary_key=True, foreign_key="runrow.id")
    user_id: str = Field(primary_key=True, foreign_key="authuser.id")
    expires_at: datetime


class Database:
    def __init__(self, settings: Settings):
        url = settings.database_url
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            path = (BACKEND_DIR / url.removeprefix("sqlite:///")).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            url = "sqlite:///" + path.as_posix()
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgres://")
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        kwargs = (
            {"connect_args": {"check_same_thread": False}}
            if url.startswith("sqlite:")
            else {"pool_size": 2, "max_overflow": 1, "pool_pre_ping": True}
        )
        self.engine = create_engine(url, **kwargs)
        SQLModel.metadata.create_all(self.engine)
        # Existing prototype databases predate ownership. Keep old rows ownerless.
        if "owner_id" not in {c["name"] for c in inspect(self.engine).get_columns("runrow")}:
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE runrow ADD COLUMN owner_id VARCHAR"))
        if "trace_json" not in {c["name"] for c in inspect(self.engine).get_columns("runrow")}:
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE runrow ADD COLUMN trace_json TEXT"))
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

