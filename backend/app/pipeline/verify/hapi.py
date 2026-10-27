import httpx


async def hapi_validate(http: httpx.AsyncClient, base_url: str, bundle: dict) -> list[str]:
    """Ask a public FHIR server to validate. Network failure is a warning, not a hard error."""
    url = base_url.rstrip("/") + "/Bundle/$validate"
    try:
        response = await http.post(url, json=bundle, headers={"Accept": "application/fhir+json"})
    except httpx.HTTPError as exc:
        return [f"HAPI unreachable: {exc}"]
    if response.status_code >= 500:
        return [f"HAPI HTTP {response.status_code}"]
    body = response.json()
    issues = []
    for issue in body.get("issue") or []:
        if issue.get("severity") in {"error", "fatal"}:
            issues.append(
                issue.get("diagnostics")
                or issue.get("details", {}).get("text")
                or "validation error"
            )
    return issues
