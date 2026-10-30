from collections import Counter

from app.pipeline.schemas import Extraction
from app.pipeline.units import normalize_unit
from app.pipeline.verify.report import Finding


def fidelity_errors(bundle: dict, extraction: Extraction) -> list[Finding]:
    findings: list[Finding] = []
    observations = [
        entry.get("resource") or {}
        for entry in bundle.get("entry") or []
        if (entry.get("resource") or {}).get("resourceType") == "Observation"
    ]
    medications = [
        entry.get("resource") or {}
        for entry in bundle.get("entry") or []
        if (entry.get("resource") or {}).get("resourceType") == "MedicationRequest"
    ]
    rows = [row for row in extraction.rows if not row.contains_identifier]
    scripts = [item for item in extraction.medications if not item.contains_identifier]
    test_requests = [
        entry.get("resource") or {}
        for entry in bundle.get("entry") or []
        if (entry.get("resource") or {}).get("resourceType") == "ServiceRequest"
    ]
    expected_tests = Counter(test.raw_name.strip().casefold() for test in extraction.advised_tests)
    actual_tests = Counter(
        str((request.get("code") or {}).get("text") or "").strip().casefold()
        for request in test_requests
    )
    if expected_tests != actual_tests:
        findings.append(
            Finding("ServiceRequest", "test requests do not match the extracted tests", "fidelity")
        )
    if len(observations) != len(rows):
        findings.append(
            Finding(
                "Observation",
                f"expected {len(rows)} observations, found {len(observations)}",
                "fidelity",
            )
        )
    if len(medications) != len(scripts):
        findings.append(
            Finding(
                "MedicationRequest",
                f"expected {len(scripts)} medication requests, found {len(medications)}",
                "fidelity",
            )
        )
    for index, (row, observation) in enumerate(zip(rows, observations, strict=False)):
        quantity = observation.get("valueQuantity") or {}
        if row.value is not None and quantity.get("value") != row.value:
            findings.append(
                Finding(
                    f"Observation[{index}].value",
                    f"value {quantity.get('value')} != printed {row.value}",
                    "fidelity",
                )
            )
        expected_unit = normalize_unit(row.unit)
        actual_unit = quantity.get("code") or quantity.get("unit")
        if expected_unit and actual_unit and actual_unit != expected_unit:
            findings.append(
                Finding(
                    f"Observation[{index}].unit",
                    f"unit {actual_unit} != {expected_unit}",
                    "fidelity",
                )
            )
        low, high = _range(observation)
        if row.ref_low is not None and low != row.ref_low:
            findings.append(
                Finding(
                    f"Observation[{index}].ref_low",
                    "reference low does not match the page",
                    "fidelity",
                )
            )
        if row.ref_high is not None and high != row.ref_high:
            findings.append(
                Finding(
                    f"Observation[{index}].ref_high",
                    "reference high does not match the page",
                    "fidelity",
                )
            )
    for index, (script, request) in enumerate(zip(scripts, medications, strict=False)):
        text = ((request.get("medicationCodeableConcept") or {}).get("text")) or ""
        if (
            script.drug_name.lower() not in text.lower()
            and script.raw_text.lower() not in text.lower()
        ):
            findings.append(
                Finding(
                    f"MedicationRequest[{index}]",
                    "drug text does not match the prescription",
                    "fidelity",
                )
            )
    return findings


def _range(observation: dict) -> tuple[float | None, float | None]:
    ranges = observation.get("referenceRange") or []
    if not ranges:
        return None, None
    first = ranges[0]
    low = (first.get("low") or {}).get("value")
    high = (first.get("high") or {}).get("value")
    return low, high
