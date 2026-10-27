import asyncio
import hashlib
import json
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.events import EventBus, EventKind, Stage
from app.models.providers import ImagePart, ProviderError, TextPart
from app.models.router import ModelRouter, NoProviderAvailable
from app.pipeline.agent.loop import run_agent
from app.pipeline.agent.prompts import ENCOUNTER_INSTRUCTIONS, EXTRACT_INSTRUCTIONS
from app.pipeline.fallback_assembler import assemble
from app.pipeline.ocr_anchors import identifier_boxes, read_text_boxes
from app.pipeline.redact import redact
from app.pipeline.schemas import EncounterFields, Extraction
from app.pipeline.segment import segment_page
from app.pipeline.terminology import search_loinc, search_rxterms
from app.pipeline.transcribe import transcribe_wav
from app.pipeline.units import normalize_unit
from app.pipeline.verify import verify
from app.store.db import Database

SHARE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SAM_CALL_USD = 0.01
EXTRACT_USD = 0.04
AGENT_USD = 0.08
VOICE_USD = 0.01


@dataclass
class RunContext:
    run_id: str
    image: bytes
    audio: bytes | None
    case_id: str | None
    auto_confirm: bool
    inject_fault: bool
    mime: str = "image/jpeg"


def pseudonym_for(run_id: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{run_id}".encode()).hexdigest()[:4].upper()
    return f"PT-ANON-{digest}"


def share_code() -> str:
    return "".join(secrets.choice(SHARE_ALPHABET) for _ in range(6))


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        http: httpx.AsyncClient,
        router: ModelRouter,
        bus: EventBus,
        db: Database,
    ):
        self.settings = settings
        self.http = http
        self.router = router
        self.bus = bus
        self.db = db
        self.gates: dict[str, asyncio.Event] = {}

    def confirm(self, run_id: str) -> bool:
        gate = self.gates.get(run_id)
        if gate is None:
            return False
        gate.set()
        return True

    async def execute(self, ctx: RunContext, on_done: Callable[[], None] | None = None) -> None:
        run_id = ctx.run_id
        try:
            await self._execute(ctx)
        except Exception as exc:  # noqa: BLE001 - the run must close even when a stage crashes
            self.bus.publish(run_id, Stage.SYSTEM, EventKind.ERROR, f"Run failed: {exc}")
            self.db.update(run_id, status="failed")
        finally:
            self.gates.pop(run_id, None)
            if self.bus.exists(run_id):
                self.bus.close(run_id)
            if on_done:
                on_done()

    async def _execute(self, ctx: RunContext) -> None:
        run_id = ctx.run_id
        self.gates.setdefault(run_id, asyncio.Event())
        anon = pseudonym_for(run_id, self.settings.pseudonym_salt)
        self.bus.publish(
            run_id, Stage.SYSTEM, EventKind.STARTED, f"Session {anon}", data={"pseudonym": anon}
        )
        over_budget = self.db.spent_today() >= self.settings.daily_budget_usd

        if over_budget and ctx.case_id:
            await self._replay_case(ctx, anon, "Replay of a recorded run. Daily budget reached.")
            return
        if over_budget:
            self.bus.publish(
                run_id,
                Stage.SYSTEM,
                EventKind.ERROR,
                "Daily budget reached. Open a sample case to replay a recorded run.",
                data={"replay": True},
            )
            self.db.update(run_id, status="failed", replay=True)
            return

        image = ImagePart(ctx.image, ctx.mime)
        self.bus.publish(
            run_id,
            Stage.SEGMENT,
            EventKind.STARTED,
            "Finding page regions",
            model=self.settings.sam_model,
        )
        try:
            regions = await segment_page(self.http, self.settings, image)
            self.db.add_spend(SAM_CALL_USD * 7)
        except (ProviderError, NotImplementedError) as exc:
            regions = {name: [] for name in ("sheet of paper", "table")}
            self.bus.publish(
                run_id, Stage.SEGMENT, EventKind.WARNING, f"Segmentation skipped: {exc}"
            )
        else:
            counts = ", ".join(f"{name} {len(boxes)}" for name, boxes in regions.items() if boxes)
            self.bus.publish(
                run_id,
                Stage.SEGMENT,
                EventKind.COMPLETED,
                counts or "No regions matched",
                model=self.settings.sam_model,
            )

        import cv2
        import numpy as np

        decoded = cv2.imdecode(np.frombuffer(ctx.image, dtype=np.uint8), cv2.IMREAD_COLOR)
        anchors = identifier_boxes(read_text_boxes(decoded)) if decoded is not None else []
        result = redact(ctx.image, regions, anchors)
        folder = self.db.runs_dir / run_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "redacted.png").write_bytes(result.redacted_png)
        (folder / "overlay.png").write_bytes(result.overlay_png)
        if result.table_png:
            (folder / "table.png").write_bytes(result.table_png)
        self.bus.publish(
            run_id,
            Stage.REDACT,
            EventKind.COMPLETED,
            f"Hid {len(result.hidden_boxes)} region(s). Confirm before the page is read.",
            data={
                "overlay_url": f"/api/runs/{run_id}/files/overlay.png",
                "redacted_url": f"/api/runs/{run_id}/files/redacted.png",
                "hidden": len(result.hidden_boxes),
            },
        )
        self.db.update(run_id, status="awaiting_confirmation")
        if ctx.auto_confirm:
            self.bus.publish(
                run_id, Stage.REDACT, EventKind.PROGRESS, "Sample case confirmed automatically"
            )
        else:
            gate = self.gates[run_id]
            try:
                await asyncio.wait_for(gate.wait(), timeout=1800)
            except TimeoutError:
                self.bus.publish(run_id, Stage.REDACT, EventKind.ERROR, "Confirmation timed out")
                self.db.update(run_id, status="failed")
                return

        crop = result.table_png or result.redacted_png
        self.bus.publish(run_id, Stage.EXTRACT, EventKind.STARTED, "Reading the redacted page")
        try:
            extracted = await self.router.structured(
                "extractor",
                instructions=EXTRACT_INSTRUCTIONS,
                parts=[TextPart("Read this redacted page."), ImagePart(crop, "image/png")],
                schema=Extraction,
            )
        except NoProviderAvailable as exc:
            if ctx.case_id:
                await self._replay_case(
                    ctx,
                    anon,
                    "No model is configured. Showing this sample sheet's recorded reading.",
                )
                return
            self.bus.publish(run_id, Stage.EXTRACT, EventKind.ERROR, str(exc))
            self.db.update(run_id, status="failed")
            return
        extraction = extracted.value
        self.db.add_spend(EXTRACT_USD)
        kept = [row for row in extraction.rows if not row.contains_identifier]
        dropped = len(extraction.rows) - len(kept)
        extraction.rows = kept
        self.bus.publish(
            run_id,
            Stage.EXTRACT,
            EventKind.COMPLETED,
            f"Read {len(kept)} lab row(s) and {len(extraction.medications)} medication(s)",
            model=str(extracted.target),
            latency_ms=extracted.latency_ms,
            data={"dropped_identifier_rows": dropped, "fell_back": extracted.fell_back},
        )

        encounter, transcript = await self._encounter(run_id, ctx.audio)
        self.db.add_spend(AGENT_USD)
        self.bus.publish(
            run_id,
            Stage.AGENT,
            EventKind.STARTED,
            "Building the FHIR bundle",
            model="muse-spark-1.3",
        )

        def publish_tool(name: str, payload: dict, result: bool = False) -> None:
            kind = EventKind.TOOL_RESULT if result else EventKind.TOOL_CALL
            summary = (
                payload.get("term")
                or payload.get("name")
                or payload.get("unit_text")
                or payload.get("ok")
            )
            self.bus.publish(run_id, Stage.AGENT, kind, f"{name} {summary}", data={"tool": name})

        agent = await run_agent(
            self.http,
            self.settings,
            extraction,
            encounter,
            anon,
            inject_fault=ctx.inject_fault,
            publish=publish_tool,
        )
        used_fallback = False
        bundle = agent.bundle
        if bundle is None:
            used_fallback = True
            self.bus.publish(
                run_id,
                Stage.AGENT,
                EventKind.WARNING,
                f"Agent stopped: {agent.error}. Assembling locally.",
            )
            bundle = await self._adopt_fallback(agent, extraction, encounter, anon)
        report = verify(bundle, extraction, agent.state.allowed_loinc, agent.state.allowed_units)
        if not report.ok and not used_fallback:
            self.bus.publish(
                run_id, Stage.VERIFY, EventKind.WARNING, "Final check failed. Assembling locally."
            )
            bundle = await self._adopt_fallback(agent, extraction, encounter, anon)
            used_fallback = True
            report = verify(
                bundle, extraction, agent.state.allowed_loinc, agent.state.allowed_units
            )
        self.bus.publish(
            run_id,
            Stage.VERIFY,
            EventKind.COMPLETED if report.ok else EventKind.WARNING,
            "Bundle valid, 0 errors" if report.ok else report.as_text(),
            data={"used_fallback": used_fallback, "inject_fault": ctx.inject_fault},
        )
        self.db.update(
            run_id,
            status="reviewing",
            document_type=extraction.document_type,
            extraction_json=extraction.model_dump_json(),
            encounter_json=encounter.model_dump_json(),
            bundle_json=json.dumps(bundle),
            transcript=transcript,
            extractor_model=str(extracted.target),
            used_fallback=used_fallback,
            inject_fault=ctx.inject_fault,
        )

    async def _encounter(
        self, run_id: str, audio: bytes | None
    ) -> tuple[EncounterFields, str | None]:
        if not audio:
            return EncounterFields(), None
        self.bus.publish(
            run_id,
            Stage.TRANSCRIBE,
            EventKind.STARTED,
            "Transcribing the visit note",
            model=self.settings.voice_model,
        )
        try:
            payload = await transcribe_wav(self.http, self.settings, audio)
        except ProviderError as exc:
            self.bus.publish(run_id, Stage.TRANSCRIBE, EventKind.WARNING, str(exc))
            return EncounterFields(), None
        self.db.add_spend(VOICE_USD)
        transcript = str(payload.get("transcript") or "")
        self.bus.publish(
            run_id,
            Stage.TRANSCRIBE,
            EventKind.COMPLETED,
            transcript or "(no speech detected)",
            model=self.settings.voice_model,
            data={"audio_ms": payload.get("audioDurationMs")},
        )
        if not transcript.strip():
            return EncounterFields(), transcript
        try:
            structured = await self.router.structured(
                "structurer",
                instructions=ENCOUNTER_INSTRUCTIONS,
                parts=[TextPart(transcript)],
                schema=EncounterFields,
            )
        except NoProviderAvailable as exc:
            self.bus.publish(run_id, Stage.STRUCTURE, EventKind.WARNING, str(exc))
            return EncounterFields(note=transcript), transcript
        self.bus.publish(
            run_id,
            Stage.STRUCTURE,
            EventKind.COMPLETED,
            f"{structured.value.class_code} {structured.value.status}",
            model=str(structured.target),
            latency_ms=structured.latency_ms,
        )
        return structured.value, transcript

    async def _adopt_fallback(
        self, agent, extraction: Extraction, encounter: EncounterFields, anon: str
    ) -> dict:
        bundle, codes, units = await self._fallback(extraction, encounter, anon)
        agent.state.allowed_loinc.update(codes)
        agent.state.allowed_units.update(units)
        return bundle

    async def _fallback(
        self, extraction: Extraction, encounter: EncounterFields, anon: str
    ) -> tuple[dict, set[str], set[str]]:
        loinc = {}
        allowed_units = set()
        for row in extraction.rows:
            unit = normalize_unit(row.unit)
            if unit:
                allowed_units.add(unit)
            try:
                hits = await search_loinc(self.http, row.raw_name)
            except httpx.HTTPError:
                hits = []
            if hits:
                loinc[row.raw_name.lower()] = hits[0]
        rx: dict[str, str | None] = {}
        for item in extraction.medications:
            try:
                hits = await search_rxterms(self.http, item.drug_name)
            except httpx.HTTPError:
                hits = []
            rx[item.drug_name.lower()] = hits[0].rxcui if hits else None
        bundle = assemble(extraction, encounter, anon, loinc, rx)
        return bundle, {hit.code for hit in loinc.values()}, allowed_units

    async def _replay_case(self, ctx: RunContext, anon: str, reason: str) -> None:
        from app.pipeline.cases import load_case

        case = load_case(ctx.case_id or "")
        self.bus.publish(
            ctx.run_id,
            Stage.SYSTEM,
            EventKind.WARNING,
            reason,
            data={"replay": True, "simulated": True},
        )
        if case is None:
            self.db.update(ctx.run_id, status="failed", replay=True)
            return
        extraction = Extraction.model_validate(case["extraction"])
        encounter = EncounterFields.model_validate(case.get("encounter") or {})
        bundle = assemble(extraction, encounter, anon, {})
        self.db.update(
            ctx.run_id,
            status="reviewing",
            replay=True,
            extraction_json=extraction.model_dump_json(),
            encounter_json=encounter.model_dump_json(),
            bundle_json=json.dumps(bundle),
            document_type=extraction.document_type,
            used_fallback=True,
        )
        self.bus.publish(
            ctx.run_id,
            Stage.VERIFY,
            EventKind.COMPLETED,
            "Replayed recorded bundle",
            data={"replay": True},
        )


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]
