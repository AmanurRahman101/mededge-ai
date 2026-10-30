import asyncio
import io
import wave
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlmodel import select

from app.models.providers import ImagePart, TextPart
from app.pipeline.orchestrator import RunContext
from app.pipeline.schemas import ConsultationDraft, Extraction
from app.store.db import ChartConnection, ClinicalSummary, RunRow
from tests.test_access import access_client, sign_in  # noqa: F401


def recording(seconds=1, rate=16000):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\0\0" * rate * seconds)
    return output.getvalue()


def approved(client):
    with client.app.state.db.session() as session:
        session.add(
            ChartConnection(
                patient_id="patient1",
                doctor_id="doctor",
                status="approved",
                requested_at=datetime.now(UTC),
            )
        )
        session.commit()


def test_combined_submission_requires_approval_and_is_idempotent(request, monkeypatch):
    client = request.getfixturevalue("access_client")
    sign_in(client, "doctor")
    calls = []

    async def capture(ctx):
        calls.append(ctx)

    monkeypatch.setattr(client.app.state.orchestrator, "execute", capture)
    data = {"patient_id": "patient1", "idempotency_key": "stable-1"}
    files = {
        "image": ("report.png", b"image", "image/png"),
        "audio": ("voice.wav", recording(), "audio/wav"),
    }
    assert client.post("/api/runs", data=data, files=files).status_code == 404
    approved(client)
    response = client.post("/api/runs", data=data, files=files)
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assert len(calls) == 1
    assert calls[0].auto_confirm is False
    row = client.app.state.db.get(run_id)
    assert row.owner_id == "patient1" and row.submitted_by == "doctor"
    second = client.post("/api/runs", data=data, files=files)
    assert second.status_code == 200 and second.json()["run_id"] == run_id
    assert len(calls) == 1
    changed = dict(files)
    changed["image"] = ("other.png", b"different", "image/png")
    assert client.post("/api/runs", data=data, files=changed).status_code == 409


def test_combined_submission_requires_audio_and_valid_pcm(request, monkeypatch):
    client = request.getfixturevalue("access_client")
    sign_in(client, "doctor")
    approved(client)
    data = {"patient_id": "patient1", "idempotency_key": "stable-2"}
    image = ("report.png", b"image", "image/png")
    assert client.post("/api/runs", data=data, files={"image": image}).status_code == 422
    assert (
        client.post(
            "/api/runs",
            data=data,
            files={"image": image, "audio": ("bad.wav", b"not a wav", "audio/wav")},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/runs",
            data=data,
            files={"image": image, "audio": ("long.wav", recording(181), "audio/wav")},
        ).status_code
        == 422
    )


def test_reuse_requires_available_source_and_patient_ownership(request, monkeypatch):
    client = request.getfixturevalue("access_client")
    sign_in(client, "doctor")
    approved(client)
    data = {"patient_id": "patient1", "idempotency_key": "stable-3", "source_run_id": "record"}
    files = {"audio": ("voice.wav", recording(), "audio/wav")}
    assert client.post("/api/runs", data=data, files=files).status_code == 409
    folder = client.app.state.db.runs_dir / "record"
    (folder / "redacted.png").write_bytes(b"already redacted")
    calls = []

    async def capture(ctx):
        calls.append(ctx)

    monkeypatch.setattr(client.app.state.orchestrator, "execute", capture)
    response = client.post("/api/runs", data=data, files=files)
    assert response.status_code == 200, response.text
    assert calls[0].image == b"already redacted"
    assert client.get("/api/runs/record").json()["source_available"] is True


def test_public_export_is_disabled(request):
    client = request.getfixturevalue("access_client")
    sign_in(client, "doctor")
    approved(client)
    assert client.post("/api/runs/record/export").status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke_during_voice", [False, True])
async def test_combined_pipeline_uses_image_and_transcript_and_respects_revocation(
    request, monkeypatch, revoke_during_voice
):
    client = request.getfixturevalue("access_client")
    approved(client)
    db = client.app.state.db
    db.add(
        RunRow(
            id="combo",
            status="queued",
            created_at=datetime.now(UTC),
            pseudonym="PT-X",
            owner_id="patient1",
            submitted_by="doctor",
        )
    )
    bus = client.app.state.bus
    bus.open("combo")
    orchestrator = client.app.state.orchestrator
    seen = []

    async def fake_segment(*args):
        return {}

    async def fake_voice(*args):
        if revoke_during_voice:
            with db.session() as session:
                connection = session.get(ChartConnection, ("patient1", "doctor"))
                connection.status = "revoked"
                session.add(connection)
                session.commit()
        return {"transcript": "No diabetes. Take 1+0+1."}

    async def fake_structured(role, *, instructions, parts, schema):
        seen.append(parts)
        assert schema is ConsultationDraft
        return SimpleNamespace(
            value=ConsultationDraft(
                extraction=Extraction(document_type="prescription"),
                summary_en="No diabetes. Take 1+0+1.",
                summary_bn="ডায়াবেটিস নেই। 1+0+1।",
                unresolved=[],
            ),
            target="meta:test",
        )

    monkeypatch.setattr("app.pipeline.orchestrator.segment_page", fake_segment)
    monkeypatch.setattr("app.pipeline.orchestrator.read_text_boxes", lambda image: [])
    monkeypatch.setattr("app.pipeline.orchestrator.transcribe_wav", fake_voice)
    monkeypatch.setattr(orchestrator.router, "structured", fake_structured)
    image = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(image, format="PNG")
    ctx = RunContext("combo", image.getvalue(), recording(), None, True, False, "image/png")
    await orchestrator.execute(ctx)
    with db.session() as session:
        drafts = session.exec(
            select(ClinicalSummary).where(ClinicalSummary.run_id == "combo")
        ).all()
        if revoke_during_voice:
            assert seen == [] and drafts == []
            assert db.get("combo").status == "failed"
        else:
            assert len(seen) == 1
            assert any(isinstance(part, ImagePart) for part in seen[0])
            assert any(
                isinstance(part, TextPart) and "No diabetes" in part.text for part in seen[0]
            )
            assert len(drafts) == 1 and drafts[0].status == "draft"
            assert drafts[0].summary_bn and drafts[0].summary_en
            assert db.get("combo").status == "reviewing"
    assert ctx.audio is None and ctx.image == b""


@pytest.mark.asyncio
async def test_revocation_cancels_active_processing(request, monkeypatch):
    client = request.getfixturevalue("access_client")
    db = client.app.state.db
    db.add(
        RunRow(
            id="cancel",
            status="queued",
            created_at=datetime.now(UTC),
            pseudonym="PT-X",
            owner_id="patient1",
            submitted_by="doctor",
        )
    )
    orchestrator = client.app.state.orchestrator
    client.app.state.bus.open("cancel")
    started = asyncio.Event()

    async def work(ctx):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(orchestrator, "_execute", work)
    ctx = RunContext("cancel", b"image", b"audio", None, False, False)
    task = asyncio.create_task(orchestrator.execute(ctx))
    orchestrator.register_task("cancel", "patient1", "doctor", task)
    await started.wait()
    orchestrator.cancel_connection("patient1", "doctor")
    with pytest.raises(asyncio.CancelledError):
        await task
    assert db.get("cancel").status == "interrupted"
    assert ctx.audio is None and ctx.image == b""
