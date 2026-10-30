import io

import pytest
from PIL import Image, ImageDraw

from app.config import Settings
from app.pipeline.dosage import dose_timing
from app.pipeline.fallback_assembler import assemble
from app.pipeline.ocr_anchors import TextBox, identifier_boxes
from app.pipeline.redact import redact
from app.pipeline.sam_local import segment_local
from app.pipeline.schemas import EncounterFields, Extraction, LabRow, LoincHit, MedicationRow
from app.pipeline.segment import SamBox
from app.pipeline.terminology import loinc_check_digit, loinc_is_valid
from app.pipeline.units import normalize_unit
from app.pipeline.verify import verify


def test_unit_dialects():
    assert normalize_unit("lakh/cumm") == "10*5/uL"
    assert normalize_unit("gm%") == "g/dL"
    assert normalize_unit("mg%") == "mg/dL"
    assert normalize_unit("/cumm") == "/uL"
    assert normalize_unit("mm/1st hr") == "mm/h"
    assert normalize_unit("mmol/L") == "mmol/L"


def test_loinc_check_digit_matches_published_codes():
    assert loinc_check_digit("2160") == 0
    assert loinc_is_valid("2160-0")
    assert loinc_is_valid("718-7")
    assert not loinc_is_valid("2160-1")
    assert not loinc_is_valid("not-a-code")


def test_dose_pattern_becomes_a_schedule_without_adding_advice():
    timing = dose_timing("1+0+1", "after meal")
    assert timing is not None
    assert timing["repeat"]["when"] == ["MORN", "NIGHT", "PC"]
    assert "text" not in timing
    assert dose_timing("once daily", None) is None


def test_ocr_anchors_keep_identifier_lines_only():
    boxes = [
        TextBox(0, 0, 10, 10, "Name: Karim"),
        TextBox(0, 20, 40, 30, "01711 000000"),
        TextBox(0, 40, 80, 50, "Haemoglobin 11.2"),
    ]
    found = identifier_boxes(boxes)
    assert [box.text for box in found] == ["Name: Karim", "01711 000000"]


def _sheet() -> bytes:
    image = Image.new("RGB", (400, 600), (250, 250, 246))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 30, 360, 120), outline=(0, 0, 0))
    draw.text((50, 50), "Name: Example", fill=(0, 0, 0))
    draw.rectangle((40, 180, 360, 520), outline=(0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_redaction_blurs_the_band_above_the_table():
    regions = {
        "sheet of paper": [SamBox(1, 10, 10, 390, 580, 400, 600, 0.9)],
        "table": [SamBox(2, 40, 180, 360, 520, 400, 600, 0.8)],
        "barcode": [SamBox(3, 300, 40, 370, 90, 400, 600, 0.7)],
    }
    result = redact(_sheet(), regions, [])
    assert result.table_png
    assert result.hidden_boxes
    assert result.page_box == (10, 10, 390, 580)


def test_without_a_table_header_remains_hidden_even_with_identifier_matches():
    anchors = [TextBox(50, 40, 200, 70, "Name: Example")]
    result = redact(_sheet(), {}, anchors)
    assert (0, 0, 400, 144) in result.hidden_boxes
    assert len(result.hidden_boxes) == 2


def test_overlay_marks_full_page_for_reading_when_no_table_is_detected():
    result = redact(_sheet(), {}, [])
    overlay = Image.open(io.BytesIO(result.overlay_png)).convert("RGB")
    header = overlay.getpixel((200, 100))
    content = overlay.getpixel((200, 300))
    assert header[0] > header[1]  # Redaction remains visible over the green area.
    assert content[1] > content[0]  # The rest of the page is marked for reading.


def _extraction() -> Extraction:
    return Extraction(
        document_type="lab_report",
        rows=[
            LabRow(raw_name="S. Creatinine", value=1.4, unit="mg/dL", ref_low=0.7, ref_high=1.2),
        ],
        medications=[
            MedicationRow(
                raw_text="Napa 1+0+1 after meal",
                drug_name="Napa",
                dose_text="1+0+1",
                timing_text="after meal",
            )
        ],
    )


def test_assembled_bundle_passes_every_verifier_layer():
    extraction = _extraction()
    extraction.document_type = "mixed"
    bundle = assemble(
        extraction,
        EncounterFields(note="Outpatient follow-up, specimen at 08:30, route to nephrology."),
        "PT-ANON-8841",
        {
            "s. creatinine": LoincHit(
                code="2160-0", display="Creatinine [Mass/volume] in Serum or Plasma"
            )
        },
    )
    report = verify(bundle, extraction, {"2160-0"}, {"mg/dL"})
    assert report.ok, report.as_text()
    kinds = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert "Condition" not in kinds
    assert "MedicationRequest" in kinds


def test_policy_rejects_a_diagnosis():
    extraction = Extraction(
        document_type="lab_report", rows=[LabRow(raw_name="Hb", value=11.2, unit="g/dL")]
    )
    bundle = assemble(extraction, EncounterFields(note="diagnosis: anemia"), "PT-ANON-0001", {})
    report = verify(bundle, extraction, set(), {"g/dL"})
    assert any(item.layer == "policy" for item in report.findings)


def test_fidelity_catches_a_changed_value():
    extraction = Extraction(
        document_type="lab_report", rows=[LabRow(raw_name="Hb", value=11.2, unit="g/dL")]
    )
    bundle = assemble(extraction, EncounterFields(), "PT-ANON-0001", {})
    bundle["entry"][2]["resource"]["valueQuantity"]["value"] = 99
    report = verify(bundle, extraction, set(), {"g/dL"})
    assert any(item.layer == "fidelity" for item in report.findings)


@pytest.mark.asyncio
async def test_local_sam_explains_the_missing_checkpoint():
    from app.models.providers import ImagePart, ProviderError

    with pytest.raises(ProviderError, match="SAM_LOCAL_CHECKPOINT"):
        await segment_local(ImagePart(b"nope"), ("table",), "")


def test_settings_still_construct(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path.as_posix()}/t.db")
    assert settings.sam_provider == "meta"
