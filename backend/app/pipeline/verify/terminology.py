from app.pipeline.terminology import loinc_is_valid
from app.pipeline.verify.report import Finding

LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"


def terminology_errors(
    bundle: dict, allowed_loinc: set[str], allowed_units: set[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for index, entry in enumerate(bundle.get("entry") or []):
        resource = entry.get("resource") or {}
        if resource.get("resourceType") != "Observation":
            continue
        for coding in (resource.get("code") or {}).get("coding") or []:
            if coding.get("system") != LOINC_SYSTEM:
                continue
            code = str(coding.get("code") or "")
            if not loinc_is_valid(code):
                findings.append(
                    Finding(
                        f"entry[{index}].code", f"{code} is not a valid LOINC code", "terminology"
                    )
                )
            elif allowed_loinc and code not in allowed_loinc:
                findings.append(
                    Finding(
                        f"entry[{index}].code",
                        f"{code} was not returned by the LOINC lookup",
                        "terminology",
                    )
                )
        quantity = resource.get("valueQuantity") or {}
        unit = quantity.get("code") or quantity.get("unit")
        if unit and allowed_units and unit not in allowed_units:
            findings.append(
                Finding(
                    f"entry[{index}].valueQuantity",
                    f"{unit} is not an allowed UCUM code",
                    "terminology",
                )
            )
        if unit and quantity.get("system") not in (None, UCUM_SYSTEM):
            findings.append(
                Finding(
                    f"entry[{index}].valueQuantity.system",
                    "unit system must be UCUM",
                    "terminology",
                )
            )
    return findings
