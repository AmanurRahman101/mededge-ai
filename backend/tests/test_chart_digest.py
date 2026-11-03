import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.pipeline.chart_digest import DigestItem, DigestResult, ensure_digest, inputs
from app.store.db import ChartConnection, ChartDigest, ClinicalSummary, RunRow
from tests.test_access import access_client as chart_client  # noqa: F401
from tests.test_access import sign_in


def note(client, id="note", **values):
    defaults = dict(
        id=id,
        run_id="record",
        author_id="doctor",
        status="published",
        transcript="Original spoken assessment",
        summary_en="Fictional reviewed note",
        summary_bn="পর্যালোচিত নোট",
        created_at=datetime.now(UTC),
        published_at=datetime.now(UTC),
    )
    defaults.update(values)
    with client.app.state.db.session() as session:
        session.add(ClinicalSummary(**defaults))
        session.commit()


def connection(client, status="approved"):
    with client.app.state.db.session() as session:
        current = session.get(ChartConnection, ("patient1", "doctor"))
        if current is None:
            current = ChartConnection(
                patient_id="patient1",
                doctor_id="doctor",
                status=status,
                requested_at=datetime.now(UTC),
            )
        current.status = status
        session.add(current)
        session.commit()


def test_full_summary_latest_amendment_no_drafts_or_other_patient(request):
    c = request.getfixturevalue("chart_client")
    note(c)
    note(c, "amendment", amends_id="note", summary_en="Corrected note")
    note(c, "draft", status="draft", summary_en="Secret draft")
    now = datetime.now(UTC)
    with c.app.state.db.session() as s:
        for i in range(60):
            s.add(
                RunRow(
                    id=f"r{i}",
                    status="reviewing",
                    created_at=now,
                    pseudonym="Fictional",
                    owner_id="patient1",
                    archived=True,
                )
            )
        s.add(
            RunRow(
                id="other",
                status="reviewing",
                created_at=now,
                pseudonym="Other patient",
                owner_id="patient2",
            )
        )
        s.commit()
    c.app.state.db.update("record", extraction_json='{"medications":null,"rows":1}')
    sign_in(c, "patient1")
    response = c.get("/api/chart/patients/patient1/summary")
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["record_count"] == 61
    assert data["published_note_count"] == 1
    saved = next(r for r in data["records"] if r["run_id"] == "record")
    assert saved["notes"][0]["summary_en"] == "Corrected note"
    assert saved["medications"] == []
    assert "Secret draft" not in response.text
    assert "transcript" not in response.text
    assert c.get("/api/chart/patients/patient2/summary").status_code == 404


@pytest.mark.parametrize("status", ["pending", "declined", "revoked"])
def test_both_summary_endpoints_require_active_consent(request, status):
    c = request.getfixturevalue("chart_client")
    connection(c, status)
    sign_in(c, "doctor")
    path = "/api/chart/patients/patient1/summary"
    assert c.get(path).status_code == 404
    assert c.post(path).status_code == 404


async def test_digest_cache_coalesces_calls_survives_restart_and_excludes_ocr(request):
    c = request.getfixturevalue("chart_client")
    note(c)
    c.app.state.db.update("record", extraction_json='{"medications":[{"raw_text":"UNVERIFIED"}]}')
    calls = []

    async def provider(*args, **kwargs):
        calls.append(kwargs)
        await asyncio.sleep(0)
        return SimpleNamespace(
            value=DigestResult(
                items=[
                    DigestItem(
                        category="assessment",
                        text_en="Fictional note",
                        text_bn="কাল্পনিক নোট",
                        source_ids=["note"],
                    )
                ]
            )
        )

    c.app.state.router.structured = provider
    results = await asyncio.gather(
        ensure_digest(c.app, "patient1"), ensure_digest(c.app, "patient1")
    )
    assert all(r["status"] == "ready" for r in results)
    assert len(calls) == 1
    assert "UNVERIFIED" not in calls[0]["parts"][0].text
    c.app.state.chart_digest_tasks = {}  # Application restarted, DB cache persists.
    assert (await ensure_digest(c.app, "patient1"))["status"] == "ready"
    assert len(calls) == 1
    note(c, "correction", amends_id="note")
    await ensure_digest(c.app, "patient1")
    assert len(calls) == 2
    assert '"id": "note"' not in calls[-1]["parts"][0].text


async def test_deletion_during_inference_does_not_persist_deleted_content(request):
    c = request.getfixturevalue("chart_client")
    note(c)

    async def provider(*args, **kwargs):
        with c.app.state.db.session() as session:
            session.delete(session.get(ClinicalSummary, "note"))
            session.commit()
        return SimpleNamespace(
            value=DigestResult(
                items=[
                    DigestItem(
                        category="assessment",
                        text_en="Deleted clinical text",
                        text_bn="নোট",
                        source_ids=["note"],
                    )
                ]
            )
        )

    c.app.state.router.structured = provider
    assert (await ensure_digest(c.app, "patient1"))["status"] == "empty"
    with c.app.state.db.session() as s:
        assert "Deleted clinical text" not in s.get(ChartDigest, "patient1").items_json


async def test_invalid_sources_and_provider_failure_preserve_notes(request):
    c = request.getfixturevalue("chart_client")
    note(c)
    calls = 0

    async def provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            value=DigestResult(
                items=[
                    DigestItem(
                        category="care",
                        text_en="Invented reference",
                        text_bn="নোট",
                        source_ids=["other"],
                    )
                ]
            )
        )

    c.app.state.router.structured = provider
    assert (await ensure_digest(c.app, "patient1"))["status"] == "failed"
    assert (await ensure_digest(c.app, "patient1"))["status"] == "failed"
    assert calls == 1  # No repeated paid calls on reopening failed history.
    assert len(inputs(c.app.state.db, "patient1")[1]) == 1


def test_revocation_while_digest_runs_denies_response(request):
    c = request.getfixturevalue("chart_client")
    note(c)
    connection(c)
    sign_in(c, "doctor")

    async def provider(*args, **kwargs):
        connection(c, "revoked")
        return SimpleNamespace(value=DigestResult(items=[]))

    c.app.state.router.structured = provider
    assert c.post("/api/chart/patients/patient1/summary").status_code == 404


def test_delete_removes_cached_digest_and_sources(request):
    c = request.getfixturevalue("chart_client")
    note(c)
    with c.app.state.db.session() as s:
        s.add(
            ChartDigest(
                patient_id="patient1",
                fingerprint="old",
                updated_at=datetime.now(UTC),
                status="ready",
                items_json='[{"text_en":"Deleted clinical text"}]',
            )
        )
        s.commit()
    sign_in(c, "patient1")
    assert c.delete("/api/chart/records/record").status_code == 200
    with c.app.state.db.session() as s:
        cache = s.get(ChartDigest, "patient1")
        assert cache is None or cache.items_json == "[]"
    assert c.get("/api/chart/patients/patient1/summary").json()["record_count"] == 0


async def test_explicit_retry_recovers_failed_summary(request):
    c = request.getfixturevalue("chart_client")
    note(c)
    calls = []

    async def provider(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("Fictional provider timeout")
        return SimpleNamespace(value=DigestResult(items=[]))

    c.app.state.router.structured = provider
    assert (await ensure_digest(c.app, "patient1"))["status"] == "failed"
    assert (await ensure_digest(c.app, "patient1"))["status"] == "failed"
    assert len(calls) == 1
    assert (await ensure_digest(c.app, "patient1", retry=True))["status"] == "ready"
    assert len(calls) == 2


def test_history_without_source_checks_remains_available_on_storage_outage(request, monkeypatch):
    c = request.getfixturevalue("chart_client")

    def broken(*args):
        raise AssertionError("History must not query file storage")

    monkeypatch.setattr("app.api.chart.source_available", broken)
    sign_in(c, "patient1")
    assert c.get("/api/chart/records?include_source=false").status_code == 200
    assert c.get("/api/chart/patients/patient1/summary").status_code == 200
    connection(c)
    sign_in(c, "doctor")
    assert c.get("/api/chart/patients/patient1/overview?include_source=false").status_code == 200
