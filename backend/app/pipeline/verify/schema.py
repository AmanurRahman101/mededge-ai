import json

from app.pipeline.verify.report import Finding


def schema_errors(bundle: dict) -> list[Finding]:
    try:
        from fhir.resources.R4B.bundle import Bundle
    except ImportError as exc:
        return [Finding("$", f"FHIR library unavailable: {exc}", "schema")]
    try:
        Bundle.model_validate(bundle)
    except Exception as exc:
        message = str(exc).replace("\n", " ")[:500]
        return [Finding("$", message, "schema")]
    return []


def bundle_json(bundle: dict) -> str:
    return json.dumps(bundle, separators=(",", ":"))
