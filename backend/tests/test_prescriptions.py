import io
import time
import uuid
import wave
from types import SimpleNamespace

from app.pipeline.prescription_schema import PrescribedMedicine, PrescriptionDraft
from app.store.db import ChartConnection
from tests.test_access import access_client as rx_client  # noqa: F401
from tests.test_access import sign_in
from tests.test_chart_digest import connection


def audio():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * 2400)
    return buffer.getvalue()


def create(client, mode="manual", key=None, data=None):
    return client.post(
        "/api/chart/patients/patient1/prescriptions",
        data={"mode": mode, "idempotency_key": key or uuid.uuid4().hex},
        files={"audio": ("fictional.wav", data or audio(), "audio/wav")}
        if mode == "voice"
        else None,
    )


def wait(client, run_id):
    for _ in range(100):
        row = client.app.state.db.get(run_id)
        if row.status not in {"queued", "processing"}:
            return row
        time.sleep(0.01)
    raise AssertionError("Prescription processing did not finish")


def test_manual_prescription_review_publish_amend_and_patient_visibility(request):
    c = request.getfixturevalue("rx_client")
    connection(c)
    sign_in(c, "doctor")
    key = uuid.uuid4().hex
    created = create(c, key=key)
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    assert create(c, key=key).json()["run_id"] == run_id
    path = f"/api/chart/records/{run_id}/summaries"
    draft = c.get(path).json()["summaries"][0]
    sign_in(c, "patient1")
    assert c.get(path).json()["summaries"] == []
    sign_in(c, "doctor")
    save = f"{path}/{draft['id']}"
    medicine = PrescribedMedicine(
        name="Fictional brand",
        strength="৫ mg",
        morning="½",
        noon="0",
        night="",
        duration="চলবে",
        instructions="As dictated",
    )
    body = {
        "transcript": "Manually entered fictional prescription",
        "summary_en": "Fictional note",
        "summary_bn": "কাল্পনিক নোট",
        "prescription": [medicine.model_dump()],
        "expected_revision": 1,
        "reviewed_both_languages": True,
    }
    assert c.post(save + "?publish=true", json=body).status_code == 422
    assert c.post(save, json=body).status_code == 200
    assert c.post(save, json=body).status_code == 409
    body["expected_revision"] = 2
    body["prescription"][0]["confirmed"] = True
    assert c.post(save + "?publish=true", json=body).status_code == 200
    assert c.post(save, json={**body, "expected_revision": 3}).status_code == 409
    sign_in(c, "patient1")
    published = c.get(path).json()["summaries"][0]
    assert published["prescription"][0]["morning"] == "½"
    assert published["prescription"][0]["noon"] == "0"
    assert published["prescription"][0]["night"] == ""
    assert published["prescription"][0]["duration"] == "চলবে"
    sign_in(c, "doctor")
    assert c.post(save + "/amend").status_code == 200
    rows = c.get(path).json()["summaries"]
    assert len(rows) == 2 and rows[-1]["prescription"] == [
        {**published["prescription"][0], "confirmed": False}
    ]
    connection(c, "revoked")
    assert c.get(path).status_code == 404
    assert c.post(save + "/amend").status_code == 404


def test_voice_only_persists_audio_and_transcript_retry_does_not_repeat_asr(request, monkeypatch):
    c = request.getfixturevalue("rx_client")
    connection(c)
    sign_in(c, "doctor")
    calls = {"asr": 0, "structure": 0}

    async def transcribe(*args, **kwargs):
        calls["asr"] += 1
        return {"transcript": "Fictional brand five mg, half morning, zero noon, continue."}

    async def structure(*args, **kwargs):
        calls["structure"] += 1
        assert kwargs["schema"] == PrescriptionDraft
        if calls["structure"] == 1:
            raise TimeoutError("Provider timeout; no clinical text may be logged")
        return SimpleNamespace(
            value=PrescriptionDraft(
                medicines=[
                    PrescribedMedicine(
                        name="Fictional brand",
                        strength="5 mg",
                        morning="½",
                        noon="0",
                        duration="Continue",
                        confirmed=True,
                    )
                ],
                summary_en="Fictional assessment",
                summary_bn="কাল্পনিক মূল্যায়ন",
            )
        )

    monkeypatch.setattr("app.api.prescriptions.transcribe_wav", transcribe)
    c.app.state.router.structured = structure
    key = uuid.uuid4().hex
    response = create(c, "voice", key)
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assert wait(c, run_id).status == "failed"
    assert c.app.state.db.get(run_id).transcript.startswith("Fictional brand")
    assert c.post(f"/api/chart/records/{run_id}/prescription/retry").status_code == 200
    assert wait(c, run_id).status == "reviewing"
    assert calls == {"asr": 1, "structure": 2}
    assert create(c, "voice", key).json()["run_id"] == run_id
    assert c.post(f"/api/chart/records/{run_id}/prescription/retry").status_code == 409
    draft = c.get(f"/api/chart/records/{run_id}/summaries").json()["summaries"][0]
    assert draft["prescription"][0]["confirmed"] is False  # Never accept model confirmation.
    assert c.get(f"/api/runs/{run_id}/files/audio").content == audio()
    sign_in(c, "patient2")
    assert c.get(f"/api/runs/{run_id}/files/audio").status_code == 404


def test_voice_prescription_validation_and_revocation_during_asr(request, monkeypatch):
    c = request.getfixturevalue("rx_client")
    sign_in(c, "doctor")
    assert create(c).status_code == 404
    connection(c)
    assert create(c, "voice", data=b"not wav").status_code == 422

    async def revoke(*args, **kwargs):
        with c.app.state.db.session() as session:
            row = session.get(ChartConnection, ("patient1", "doctor"))
            row.status = "revoked"
            session.add(row)
            session.commit()
        return {"transcript": "Fictional voice"}

    async def forbidden(*args, **kwargs):
        raise AssertionError("Revoked doctors must not reach structuring")

    monkeypatch.setattr("app.api.prescriptions.transcribe_wav", revoke)
    c.app.state.router.structured = forbidden
    result = create(c, "voice")
    run_id = result.json()["run_id"]
    assert wait(c, run_id).status in {"failed", "interrupted"}
    assert c.get(f"/api/chart/records/{run_id}/summaries").status_code == 404
    sign_in(c, "patient1")
    assert create(c).status_code == 403
