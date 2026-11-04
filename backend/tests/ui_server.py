"""Fictional local browser fixture. No external emails or model calls."""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.auth.security import digest
from app.config import Settings
from app.main import create_app
from app.pipeline.chart_digest import DigestItem, DigestResult
from app.pipeline.prescription_schema import PrescribedMedicine, PrescriptionDraft
from app.store.db import AuthSession, AuthUser, ChartConnection, ClinicalSummary, Database, RunRow

root = (Path(__file__).resolve().parents[1] / "var" / f"ui-{uuid.uuid4().hex}").resolve()
root.mkdir(parents=True)
settings = Settings(
    _env_file=None,
    app_env="test",
    app_base_url="http://127.0.0.1:8023",
    cors_origins="http://127.0.0.1:8023",
    database_url=f"sqlite:///{(root / 'test.db').as_posix()}",
    runs_dir=str(root / "runs"),
)
db = Database(settings)
now = datetime.now(UTC)
with db.session() as session:
    for uid, name, role in [
        ("ui-doctor", "Dr. Farah (fictional)", "doctor"),
        ("ui-patient", "Nadia (fictional)", "patient"),
    ]:
        session.add(
            AuthUser(
                id=uid,
                full_name=name,
                email=f"{uid}@example.test",
                password_hash="unused",
                role=role,
                verified=True,
                created_at=now,
            )
        )
        session.add(
            AuthSession(
                id=digest(uid),
                user_id=uid,
                csrf_token=f"csrf-{uid}",
                expires_at=now + timedelta(hours=2),
            )
        )
    session.add(
        ChartConnection(
            patient_id="ui-patient",
            doctor_id="ui-doctor",
            status="approved",
            requested_at=now,
            decided_at=now,
            consent_version="chart-access-v2",
        )
    )
    session.add(
        RunRow(
            id="ui-report",
            owner_id="ui-patient",
            status="reviewing",
            created_at=now,
            pseudonym="FICTIONAL",
            title="Follow-up report",
            document_type="prescription",
            extraction_json=json.dumps(
                {
                    "document_type": "prescription",
                    "rows": [],
                    "medications": [{"raw_text": "Fictional medicine 10 mg"}],
                    "advised_tests": [{"raw_name": "CRP"}],
                }
            ),
        )
    )
    session.add(
        RunRow(
            id="ui-draft",
            owner_id="ui-patient",
            status="reviewing",
            created_at=now,
            pseudonym="FICTIONAL",
            title="Today's visit",
            document_type="other",
        )
    )
    session.add(
        ClinicalSummary(
            id="ui-old",
            run_id="ui-report",
            author_id="ui-doctor",
            status="published",
            created_at=now,
            published_at=now,
            transcript="Earlier version",
            summary_en="Superseded note",
            summary_bn="পুরনো নোট",
        )
    )
    session.add(
        ClinicalSummary(
            id="ui-note",
            run_id="ui-report",
            author_id="ui-doctor",
            status="published",
            created_at=now,
            published_at=now,
            amends_id="ui-old",
            transcript="Fictional reviewed note",
            summary_en=(
                "Follow-up: symptoms improved. No fever reported. "
                "Repeat the advised test before the next review."
            ),
            summary_bn="ফলো-আপ: উপসর্গ কমেছে। জ্বর নেই। পরবর্তী পর্যালোচনার আগে পরামর্শকৃত পরীক্ষাটি করুন।",
        )
    )
    session.add(
        ClinicalSummary(
            id="ui-edit",
            run_id="ui-draft",
            author_id="ui-doctor",
            status="draft",
            created_at=now,
            transcript="Fictional follow-up: no new concerns.",
            summary_en="No new concerns reported at the fictional follow-up.",
            summary_bn="কাল্পনিক ফলো-আপে নতুন কোনো উদ্বেগের কথা বলা হয়নি।",
        )
    )
    session.commit()
folder = root / "runs" / "ui-report"
folder.mkdir(parents=True)
image = Image.new("RGB", (600, 740), "#fbfaf4")
draw = ImageDraw.Draw(image)
draw.text((30, 30), "FICTIONAL REPORT - NO REAL PATIENT DATA", fill="#222")
draw.rectangle((20, 80, 580, 150), fill="#fcc")
draw.text((30, 200), "Test advised: CRP", fill="#222")
for name in ["overlay.png", "redacted.png", "original.png"]:
    image.save(folder / name)
app = create_app(settings)
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def fixture_lifespan(app):
    async with original_lifespan(app):

        async def fake_asr(*args, **kwargs):
            return {
                "transcript": ("Fictional medicine five mg, half in the morning, "
                               "zero at noon, one at night, continue.")
            }

        from app.api import prescriptions

        prescriptions.transcribe_wav = fake_asr

        async def fake_search(query, page=1):
            return {
                "products": [
                    {
                        "code": "fictional-product",
                        "brand": "Fictional reference brand",
                        "composition": "Fictional ingredient 5 mg",
                        "form": "Tablet",
                        "manufacturer": "Fictional manufacturer",
                        "dar_number": "fixture",
                        "source_version": "test",
                        "source_url": "https://example.test/registry",
                    }
                ],
                "total": 1,
                "page": page,
                "has_more": False,
                "checked_at": "2026-11-04T00:00:00Z",
                "stale": False,
            }

        app.state.medicine_reference.search = fake_search

        async def fake_provider(*args, **kwargs):
            if kwargs["schema"] == PrescriptionDraft:
                return SimpleNamespace(
                    value=PrescriptionDraft(
                        medicines=[
                            PrescribedMedicine(
                                name="Fictional medicine",
                                strength="5 mg",
                                morning="½",
                                noon="0",
                                night="1",
                                duration="Continue",
                            )
                        ],
                        summary_en="Fictional doctor assessment.",
                        summary_bn="কাল্পনিক মূল্যায়ন।",
                    )
                )
            notes = json.loads(kwargs["parts"][0].text)
            return SimpleNamespace(
                value=DigestResult(
                    narrative_en=" ".join(n["english"] for n in notes),
                    narrative_bn=" ".join(n["bangla"] for n in notes),
                    items=[
                        DigestItem(
                            category="assessment",
                            text_en=n["english"],
                            text_bn=n["bangla"],
                            source_ids=[n["id"]],
                        )
                        for n in notes
                    ],
                )
            )

        app.state.router.structured = fake_provider
        yield


app.router.lifespan_context = fixture_lifespan
