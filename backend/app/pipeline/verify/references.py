from app.pipeline.verify.report import Finding


def reference_errors(bundle: dict) -> list[Finding]:
    findings: list[Finding] = []
    entries = bundle.get("entry") or []
    known = {entry.get("fullUrl") for entry in entries if entry.get("fullUrl")}
    for index, entry in enumerate(entries):
        if "request" not in entry:
            findings.append(
                Finding(f"entry[{index}].request", "transaction entry has no request", "references")
            )
        resource = entry.get("resource") or {}
        for path, value in _references(resource, "resource"):
            if isinstance(value, str) and value.startswith("urn:uuid:") and value not in known:
                findings.append(
                    Finding(f"entry[{index}].{path}", f"unresolved reference {value}", "references")
                )
    return findings


def _references(node: object, path: str):
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}"
            if key == "reference" and isinstance(value, str):
                yield child, value
            else:
                yield from _references(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _references(value, f"{path}[{index}]")
