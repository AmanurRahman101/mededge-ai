"""Shared demo accounts for judges: two verified users, a consent link, fictional records.

Everything here is fictional. Seeded records come from the recorded sample readings and
cost no model calls. Runs the demo users create are removed on a timer.
"""

import asyncio
import json
import shutil
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlmodel import select

from app.api.auth import password_hash
from app.config import Settings
from app.pipeline.cases import SAMPLES, list_cases
from app.pipeline.fallback_assembler import assemble
from app.pipeline.schemas import EncounterFields, Extraction, LoincHit
from app.pipeline.terminology import loinc_is_valid
from app.store.db import (
    AuthUser,
    ChartConnection,
    ClinicalSummary,
    ConsentEvent,
    Database,
    RunRow,
)

PATIENT_ID = "demo-patient"
DOCTOR_ID = "demo-doctor"
MAX_AGE = timedelta(hours=3)
LOINC_BY_NAME = {
    "haemoglobin": ("718-7", "Hemoglobin [Mass/volume] in Blood"),
    "s. creatinine": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
    "platelets": ("777-3", "Platelets [#/volume] in Blood by Automated count"),
    "esr": ("4537-7", "Erythrocyte sedimentation rate"),
    "wbc": ("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
    "cholesterol": ("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
    "triglyceride": ("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
    "hdl": ("2085-9", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"),
    "ldl": ("13457-7", "Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation"),
}
SAMPLE_NOTE_EN = "Outpatient follow-up. Fasting specimen collected at 8:30. Route to nephrology."
SAMPLE_NOTE_BN = "বহির্বিভাগ ফলো-আপ। সকাল ৮:৩০-এ উপবাসে নমুনা নেওয়া হয়েছে। নেফ্রোলজিতে পাঠান।"


def enabled(settings: Settings) -> bool:
    return bool(
        settings.demo_patient_email
        and settings.demo_doctor_email
        and settings.demo_password
        and settings.demo_password.get_secret_value()
    )


def is_demo(user_id: str | None) -> bool:
    return bool(user_id) and user_id in (PATIENT_ID, DOCTOR_ID)


def _loinc_map(extraction: Extraction) -> dict[str, LoincHit]:
    found = {}
    for row in extraction.rows:
        entry = LOINC_BY_NAME.get(row.raw_name.lower())
        if entry and loinc_is_valid(entry[0]):
            found[row.raw_name.lower()] = LoincHit(code=entry[0], display=entry[1])
    return found


def seed(db: Database, settings: Settings) -> None:
    if not enabled(settings):
        return
    now = datetime.now(UTC)
    hashed = password_hash.hash(settings.demo_password.get_secret_value())
    with db.session() as session:
        for user_id, email, name, role in (
            (PATIENT_ID, settings.demo_patient_email, "Demo Patient", "patient"),
            (DOCTOR_ID, settings.demo_doctor_email, "Demo Doctor", "doctor"),
        ):
            user = session.get(AuthUser, user_id)
            if user is None:
                session.add(
                    AuthUser(
                        id=user_id, email=email.lower(), full_name=name,
                        password_hash=hashed, role=role, verified=True, created_at=now,
                    )
                )
            else:
                user.email = email.lower()
                user.password_hash = hashed
                user.verified = True
                session.add(user)
        session.commit()
        connection = session.get(ChartConnection, (PATIENT_ID, DOCTOR_ID))
        if connection is None:
            session.add(
                ChartConnection(
                    patient_id=PATIENT_ID, doctor_id=DOCTOR_ID, status="approved",
                    requested_at=now, decided_at=now, consent_version="demo",
                    request_id=uuid.uuid4().hex,
                )
            )
        elif connection.status != "approved":
            connection.status = "approved"
            session.add(connection)
        session.commit()
        has_consent = session.exec(
            select(ConsentEvent).where(ConsentEvent.patient_id == PATIENT_ID)
        ).first()
        if has_consent is None:
            session.add(
                ConsentEvent(
                    id=uuid.uuid4().hex, patient_id=PATIENT_ID, doctor_id=DOCTOR_ID,
                    actor_id=PATIENT_ID, action="approved", version="demo",
                    scope="shared fictional demo accounts",
                    consent_text="Shared demo accounts hold fictional data only.",
                    occurred_at=now,
                )
            )
            session.commit()
    for index, case in enumerate(list_cases()):
        run_id = f"demo-{case['id']}"
        if db.get(run_id) is not None:
            continue
        extraction = Extraction.model_validate(case["extraction"])
        pseudonym = f"PT-DEMO-{index + 1:02d}"
        bundle = assemble(extraction, EncounterFields(), pseudonym, _loinc_map(extraction), {})
        db.add(
            RunRow(
                id=run_id, status="reviewing", created_at=now - timedelta(minutes=index),
                pseudonym=pseudonym, owner_id=PATIENT_ID, document_type=extraction.document_type,
                extraction_json=extraction.model_dump_json(),
                encounter_json=EncounterFields().model_dump_json(),
                bundle_json=json.dumps(bundle), replay=True, title=case["title"],
                extractor_model="recorded sample reading",
                submitted_by=DOCTOR_ID if index == 0 else PATIENT_ID,
            )
        )
        folder = db.runs_dir / run_id
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("redacted.png", "overlay.png"):
            shutil.copyfile(SAMPLES / case["file"], folder / name)
        if index == 0:
            with db.session() as session:
                session.add(
                    ClinicalSummary(
                        id=f"demo-note-{run_id}", run_id=run_id, author_id=DOCTOR_ID,
                        transcript=SAMPLE_NOTE_EN, summary_en=SAMPLE_NOTE_EN,
                        summary_bn=SAMPLE_NOTE_BN, unresolved="[]", status="published",
                        created_at=now, published_at=now,
                    )
                )
                session.commit()


def reset(db: Database, settings: Settings) -> None:
    """Remove stale demo runs (seeded ones included), then restore the seeded records."""
    if not enabled(settings):
        return
    cutoff = datetime.now(UTC) - MAX_AGE
    with db.session() as session:
        rows = session.exec(select(RunRow).where(RunRow.owner_id == PATIENT_ID)).all()
        stale = []
        for row in rows:
            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created < cutoff:
                stale.append(row.id)
        for run_id in stale:
            session.exec(delete(ClinicalSummary).where(ClinicalSummary.run_id == run_id))
            session.exec(delete(RunRow).where(RunRow.id == run_id))
        session.commit()
    for run_id in stale:
        shutil.rmtree(db.runs_dir / run_id, ignore_errors=True)
    seed(db, settings)


async def reset_loop(db: Database, settings: Settings) -> None:
    while True:
        await asyncio.sleep(3600)
        try:
            await asyncio.to_thread(reset, db, settings)
        except Exception:  # noqa: BLE001 - a failed reset must never stop the service
            continue
