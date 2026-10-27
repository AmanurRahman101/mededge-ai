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


async def live() -> str:
    from app.config import get_settings
    from app.models.providers import ImagePart, TextPart
    from app.models.router import ModelRouter
    from app.pipeline.agent.prompts import EXTRACT_INSTRUCTIONS
    from app.pipeline.cases import SAMPLES, load_case

    import httpx

    settings = get_settings()
    if not settings.model_api_key:
        return "skipped (MODEL_API_KEY is not set)"
    case = load_case("cbc")
    if case is None:
        return "skipped (no cbc sample)"
    image = ImagePart((SAMPLES / case["file"]).read_bytes(), "image/png")
    async with httpx.AsyncClient(timeout=180) as http:
        result = await ModelRouter(settings, http).structured(
            "extractor",
            instructions=EXTRACT_INSTRUCTIONS,
            parts=[TextPart("Read this page."), image],
            schema=Extraction,
        )
    expected = {row["raw_name"] for row in case["extraction"]["rows"]}
    found = {row.raw_name for row in result.value.rows}
    return f"{result.target} matched {len(expected & found)}/{len(expected)} names in {result.latency_ms} ms"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="Also call the configured extractor once")
    args = parser.parse_args()
    report = offline()
    if args.live:
        report["live_extractor"] = asyncio.run(live())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
