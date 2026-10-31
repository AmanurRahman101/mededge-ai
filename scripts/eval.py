"""Offline checks against the fictional sample sheets, plus an optional live model run.

The offline numbers do not claim model accuracy. They check the deterministic pieces:
unit dialects, LOINC check digits, and FHIR assembly of the sample ground truth.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline.cases import list_cases  # noqa: E402
from app.pipeline.fallback_assembler import assemble  # noqa: E402
from app.pipeline.schemas import EncounterFields, Extraction  # noqa: E402
from app.pipeline.terminology import loinc_is_valid  # noqa: E402
from app.pipeline.units import normalize_unit  # noqa: E402
from app.pipeline.verify import verify  # noqa: E402

DIALECTS = {
    "lakh/cumm": "10*5/uL",
    "gm%": "g/dL",
    "mg%": "mg/dL",
    "/cumm": "/uL",
    "mm/1st hr": "mm/h",
    "mmol/L": "mmol/L",
}
CODES = ["2160-0", "718-7", "2093-3", "2085-9", "13457-7"]


def offline() -> dict:
    dialect_hits = sum(normalize_unit(src) == dst for src, dst in DIALECTS.items())
    code_hits = sum(loinc_is_valid(code) for code in CODES)
    bundles_ok = 0
    for case in list_cases():
        extraction = Extraction.model_validate(case["extraction"])
        bundle = assemble(extraction, EncounterFields(), "PT-ANON-EVAL", {})
        units = {normalize_unit(row.unit) for row in extraction.rows if normalize_unit(row.unit)}
        if verify(bundle, extraction, set(), units).ok:
            bundles_ok += 1
    total = len(list_cases())
    return {
        "unit_dialects": f"{dialect_hits}/{len(DIALECTS)}",
        "loinc_check_digits": f"{code_hits}/{len(CODES)}",
        "sample_bundles_valid": f"{bundles_ok}/{total}",
    }


def _norm(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


async def live() -> dict:
    """One structured read of each fictional sample. Names must match exactly after folding."""
    from app.config import get_settings
    from app.models.providers import ImagePart, TextPart
    from app.models.router import ModelRouter
    from app.pipeline.agent.prompts import EXTRACT_INSTRUCTIONS
    from app.pipeline.cases import SAMPLES, list_cases

    import httpx

    settings = get_settings()
    if not settings.model_api_key:
        return {"status": "skipped", "reason": "MODEL_API_KEY is not set"}
    report: dict = {"cases": []}
    async with httpx.AsyncClient(timeout=180) as http:
        router = ModelRouter(settings, http)
        for case in list_cases():
            image = ImagePart((SAMPLES / case["file"]).read_bytes(), "image/png")
            result = await router.structured(
                "extractor",
                instructions=EXTRACT_INSTRUCTIONS,
                parts=[TextPart("Read this page."), image],
                schema=Extraction,
            )
            expected_rows = case["extraction"]["rows"]
            found = {_norm(row.raw_name): row for row in result.value.rows}
            name_hits = 0
            value_hits = 0
            for row in expected_rows:
                match = found.get(_norm(row["raw_name"]))
                if match is None:
                    continue
                name_hits += 1
                if row.get("value") is not None and match.value == row["value"]:
                    value_hits += 1
            expected_meds = case["extraction"].get("medications", [])
            found_meds = [
                (_norm(f"{item.drug_name or ''} {item.raw_text}"), item)
                for item in result.value.medications
            ]
            med_hits = 0
            dose_hits = 0
            for item in expected_meds:
                needle = _norm(item.get("drug_name") or item["raw_text"])
                match = next((med for key, med in found_meds if needle and needle in key), None)
                if match is None:
                    continue
                med_hits += 1
                observed = f"{match.dose_text or ''} {match.raw_text}"
                if item.get("dose_text") and item["dose_text"] in observed:
                    dose_hits += 1
            entry = {
                "id": case["id"],
                "model": str(result.target),
                "latency_ms": result.latency_ms,
                "fell_back": result.fell_back,
            }
            if expected_rows:
                entry["names"] = f"{name_hits}/{len(expected_rows)}"
                entry["values"] = f"{value_hits}/{len(expected_rows)}"
            if expected_meds:
                entry["medications"] = f"{med_hits}/{len(expected_meds)}"
                entry["doses"] = f"{dose_hits}/{len(expected_meds)}"
            report["cases"].append(entry)
    report["ran_on"] = "2026-11-01"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="Also call the configured extractor once")
    args = parser.parse_args()
    report = offline()
    if args.live:
        report["live_extractor"] = asyncio.run(live())
        out = Path(__file__).resolve().parent / "out"
        out.mkdir(exist_ok=True)
        (out / "eval-live.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
