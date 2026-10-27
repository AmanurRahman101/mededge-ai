from app.pipeline.cases import list_cases
from app.pipeline.fallback_assembler import assemble
from app.pipeline.schemas import EncounterFields, Extraction
from app.pipeline.units import normalize_unit
from app.pipeline.verify import verify


def test_fictional_samples_assemble_into_valid_bundles():
    cases = list_cases()
    assert [case["id"] for case in cases] == ["cbc", "lipid", "prescription"]
    for case in cases:
        extraction = Extraction.model_validate(case["extraction"])
        bundle = assemble(extraction, EncounterFields(), "PT-ANON-EVAL", {})
        units = {normalize_unit(row.unit) for row in extraction.rows if normalize_unit(row.unit)}
        report = verify(bundle, extraction, set(), units)
        assert report.ok, report.as_text()
