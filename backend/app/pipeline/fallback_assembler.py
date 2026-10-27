import uuid
from datetime import UTC, datetime

from app.pipeline.dosage import dose_timing
from app.pipeline.schemas import EncounterFields, Extraction, LoincHit
from app.pipeline.units import normalize_unit

LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
ACT = "http://terminology.hl7.org/CodeSystem/v3-ActCode"


def _id() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


def assemble(
    extraction: Extraction,
    encounter: EncounterFields,
    pseudonym: str,
    loinc_by_name: dict[str, LoincHit],
    rx_by_name: dict[str, str | None] | None = None,
) -> dict:
    """Build a valid R4 transaction bundle from already-checked fields. No model is involved."""
    patient_id, encounter_id = _id(), _id()
    now = encounter.effective_datetime or datetime.now(UTC).replace(microsecond=0).isoformat()
    rx_by_name = rx_by_name or {}
    entries = [
        _entry(
            patient_id,
            {
                "resourceType": "Patient",
                "identifier": [{"system": "urn:mededge:anon", "value": pseudonym}],
                "name": [{"text": pseudonym}],
            },
            "Patient",
        ),
        _entry(
            encounter_id,
            {
                "resourceType": "Encounter",
                "status": encounter.status,
                "class": {
                    "system": ACT,
                    "code": encounter.class_code,
                    "display": encounter.class_display,
                },
                "subject": {"reference": patient_id},
                "period": {"start": now},
            },
            "Encounter",
        ),
    ]
    if encounter.note:
        entries[1]["resource"]["text"] = {
            "status": "additional",
            "div": f"<div>{_xml(encounter.note)}</div>",
        }

    observation_ids: list[str] = []
    for row in extraction.rows:
        if row.contains_identifier:
            continue
        observation_id = _id()
        observation_ids.append(observation_id)
        hit = loinc_by_name.get(row.raw_name.lower())
        code: dict = {"text": row.raw_name}
        if hit:
            code["coding"] = [{"system": LOINC, "code": hit.code, "display": hit.display}]
        resource: dict = {
            "resourceType": "Observation",
            "status": "final",
            "code": code,
            "subject": {"reference": patient_id},
            "encounter": {"reference": encounter_id},
            "effectiveDateTime": now,
        }
        unit = normalize_unit(row.unit)
        if row.value is not None and unit:
            resource["valueQuantity"] = {
                "value": row.value,
                "unit": unit,
                "system": UCUM,
                "code": unit,
            }
        elif row.value_text:
            resource["valueString"] = row.value_text
        if row.ref_low is not None or row.ref_high is not None:
            ref: dict = {}
            if row.ref_low is not None and unit:
                ref["low"] = {"value": row.ref_low, "unit": unit, "system": UCUM, "code": unit}
            if row.ref_high is not None and unit:
                ref["high"] = {"value": row.ref_high, "unit": unit, "system": UCUM, "code": unit}
            if row.ref_text:
                ref["text"] = row.ref_text
            if ref:
                resource["referenceRange"] = [ref]
        entries.append(_entry(observation_id, resource, "Observation"))

    for item in extraction.medications:
        if item.contains_identifier:
            continue
        dosage: dict = {
            "text": " ".join(
                part for part in (item.dose_text, item.timing_text, item.duration_text) if part
            )
        }
        timing = dose_timing(item.dose_text, item.timing_text)
        if timing:
            dosage["timing"] = timing
        concept: dict = {"text": item.raw_text or item.drug_name}
        rxcui = rx_by_name.get(item.drug_name.lower())
        if rxcui:
            concept["coding"] = [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": rxcui,
                    "display": item.drug_name,
                }
            ]
        entries.append(
            _entry(
                _id(),
                {
                    "resourceType": "MedicationRequest",
                    "status": "active",
                    "intent": "order",
                    "medicationCodeableConcept": concept,
                    "subject": {"reference": patient_id},
                    "encounter": {"reference": encounter_id},
                    "dosageInstruction": [dosage] if dosage["text"] else [{"text": item.raw_text}],
                },
                "MedicationRequest",
            )
        )

    if observation_ids and extraction.document_type in {"lab_report", "mixed"}:
        entries.append(
            _entry(
                _id(),
                {
                    "resourceType": "DiagnosticReport",
                    "status": "final",
                    "code": {"text": "Laboratory report"},
                    "subject": {"reference": patient_id},
                    "encounter": {"reference": encounter_id},
                    "effectiveDateTime": now,
                    "result": [{"reference": item} for item in observation_ids],
                },
                "DiagnosticReport",
            )
        )

    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def _entry(full_url: str, resource: dict, url: str) -> dict:
    return {"fullUrl": full_url, "resource": resource, "request": {"method": "POST", "url": url}}


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
