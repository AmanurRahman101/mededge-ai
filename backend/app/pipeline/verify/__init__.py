from app.pipeline.schemas import Extraction
from app.pipeline.verify.fidelity import fidelity_errors
from app.pipeline.verify.policy import policy_errors
from app.pipeline.verify.references import reference_errors
from app.pipeline.verify.report import Finding, Report
from app.pipeline.verify.schema import schema_errors
from app.pipeline.verify.terminology import terminology_errors

__all__ = ["Finding", "Report", "verify"]


def verify(
    bundle: dict,
    extraction: Extraction,
    allowed_loinc: set[str],
    allowed_units: set[str],
) -> Report:
    findings: list[Finding] = []
    findings.extend(schema_errors(bundle))
    if not any(item.layer == "schema" for item in findings):
        findings.extend(reference_errors(bundle))
        findings.extend(terminology_errors(bundle, allowed_loinc, allowed_units))
        findings.extend(fidelity_errors(bundle, extraction))
        findings.extend(policy_errors(bundle, extraction))
    return Report(findings)
