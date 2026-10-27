import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.pipeline.schemas import Extraction, LoincHit
from app.pipeline.terminology import lookup_ucum, search_loinc, search_rxterms
from app.pipeline.units import normalize_unit
from app.pipeline.verify import verify
from app.pipeline.verify.report import Report

ToolFn = Callable[[dict], Awaitable[dict]]


@dataclass
class ToolState:
    extraction: Extraction
    allowed_loinc: set[str] = field(default_factory=set)
    allowed_units: set[str] = field(default_factory=set)
    loinc_by_name: dict[str, LoincHit] = field(default_factory=dict)
    rx_by_name: dict[str, str | None] = field(default_factory=dict)
    submissions: int = 0
    last_report: Report | None = None
    accepted_bundle: dict | None = None
    inject_fault: bool = False
    _fault_sent: bool = False


def tool_specs() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "search_loinc",
            "description": "Look up a printed lab name in NLM LOINC. Returns up to 5 codes.",
            "parameters": {
                "type": "object",
                "properties": {"term": {"type": "string", "description": "Printed test name"}},
                "required": ["term"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "lookup_ucum",
            "description": "Resolve a printed unit to UCUM, using the local dialect map then NLM.",
            "parameters": {
                "type": "object",
                "properties": {"unit_text": {"type": "string"}},
                "required": ["unit_text"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "search_rxterms",
            "description": "Look up a printed drug name in NLM RxTerms.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "submit_bundle",
            "description": "Validate a FHIR R4 transaction Bundle. Returns ok or errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bundle": {"type": "object", "description": "The FHIR Bundle object"}
                },
                "required": ["bundle"],
                "additionalProperties": False,
            },
        },
    ]


def make_tools(http: httpx.AsyncClient, state: ToolState) -> dict[str, ToolFn]:
    async def _search_loinc(args: dict) -> dict:
        term = str(args.get("term") or "")
        hits = await search_loinc(http, term)
        for hit in hits:
            state.allowed_loinc.add(hit.code)
            state.loinc_by_name.setdefault(term.lower(), hit)
        return {"term": term, "hits": [hit.model_dump() for hit in hits]}

    async def _lookup_ucum(args: dict) -> dict:
        raw = str(args.get("unit_text") or "")
        mapped = normalize_unit(raw)
        codes = [mapped] if mapped else []
        try:
            remote = await lookup_ucum(http, raw)
        except httpx.HTTPError:
            remote = []
        for code in [*codes, *remote]:
            if code:
                state.allowed_units.add(code)
        return {"unit_text": raw, "ucum": codes[0] if codes else None, "also": remote}

    async def _search_rxterms(args: dict) -> dict:
        name = str(args.get("name") or "")
        try:
            hits = await search_rxterms(http, name)
        except httpx.HTTPError:
            hits = []
        if hits:
            state.rx_by_name[name.lower()] = hits[0].rxcui
        else:
            state.rx_by_name.setdefault(name.lower(), None)
        return {"name": name, "hits": [hit.model_dump() for hit in hits]}

    async def _submit_bundle(args: dict) -> dict:
        bundle = args.get("bundle")
        if isinstance(bundle, str):
            bundle = json.loads(bundle)
        state.submissions += 1
        if not isinstance(bundle, dict):
            return {"ok": False, "errors": ["bundle must be an object"]}
        report = verify(bundle, state.extraction, state.allowed_loinc, state.allowed_units)
        if state.inject_fault and not state._fault_sent:
            state._fault_sent = True
            from app.pipeline.verify.report import Finding

            report.findings.insert(
                0,
                Finding(
                    "Observation.status", "Injected fault: missing Observation.status", "schema"
                ),
            )
        state.last_report = report
        if report.ok:
            state.accepted_bundle = bundle
            return {"ok": True, "errors": []}
        return {"ok": False, "errors": report.as_text().splitlines()}

    return {
        "search_loinc": _search_loinc,
        "lookup_ucum": _lookup_ucum,
        "search_rxterms": _search_rxterms,
        "submit_bundle": _submit_bundle,
    }
