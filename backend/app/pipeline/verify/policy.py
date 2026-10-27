import re

from app.pipeline.schemas import Extraction
from app.pipeline.verify.report import Finding

_ADVICE = re.compile(
    r"\b(diagnosed|diagnosis|recommend(?:ed|ation)?|you should|"
    r"treatment plan|abnormal|high risk|low risk)\b",
    re.I,
)


def policy_errors(bundle: dict, extraction: Extraction) -> list[Finding]:
    findings: list[Finding] = []
    for index, entry in enumerate(bundle.get("entry") or []):
        resource = entry.get("resource") or {}
        kind = resource.get("resourceType")
        if kind == "Condition":
            findings.append(
                Finding(f"entry[{index}]", "Condition resources are not allowed", "policy")
            )
        if kind == "Observation" and resource.get("interpretation"):
            findings.append(
                Finding(
                    f"entry[{index}].interpretation",
                    "computed interpretation is not allowed",
                    "policy",
                )
            )
        blob = _text(resource)
        if _ADVICE.search(blob):
            findings.append(
                Finding(
                    f"entry[{index}]", "text contains a clinical conclusion or advice", "policy"
                )
            )
        if kind == "MedicationRequest":
            text = ((resource.get("medicationCodeableConcept") or {}).get("text")) or ""
            known = [
                item.drug_name for item in extraction.medications if not item.contains_identifier
            ]
            if known and not any(name.lower() in text.lower() for name in known):
                findings.append(
                    Finding(f"entry[{index}]", "medication was not on the source page", "policy")
                )
    return findings


def _text(node: object) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return " ".join(_text(value) for value in node.values())
    if isinstance(node, list):
        return " ".join(_text(value) for value in node)
    return ""
