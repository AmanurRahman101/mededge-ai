import asyncio

from fastapi import APIRouter, Request

from app.config import ROLES, Settings
from app.models.providers import probe

router = APIRouter()


@router.get("/api/health")
async def health(request: Request, probe_providers: bool = False) -> dict:
    settings: Settings = request.app.state.settings

    roles = {}
    used: set[str] = set()
    for role in ROLES:
        chain = []
        for target in settings.chain(role):
            endpoint = settings.endpoint(target.provider)
            configured = bool(endpoint and endpoint.configured)
            if configured:
                used.add(target.provider)
            chain.append({"target": str(target), "configured": configured})
        roles[role] = chain

    probes: dict[str, dict] = {}
    if probe_providers:
        names = sorted(used)
        results = await asyncio.gather(
            *(probe(settings.endpoint(name), request.app.state.http) for name in names)
        )
        probes = {
            name: {"ok": ok, "detail": detail}
            for name, (ok, detail) in zip(names, results, strict=True)
        }

    return {
        "status": "ok",
        "meta_key_present": bool(
            settings.model_api_key and settings.model_api_key.get_secret_value()
        ),
        "budget": {
            "spent_today_usd": request.app.state.db.spent_today(),
            "daily_limit_usd": settings.daily_budget_usd,
        },
        "roles": roles,
        "sam": {"provider": settings.sam_provider, "model": settings.sam_model},
        "voice": {"model": settings.voice_model},
        "probes": probes,
    }
