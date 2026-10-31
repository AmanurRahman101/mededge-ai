import asyncio

from fastapi import APIRouter, Request

from app.auth.security import client_key, require_user, throttle
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
        user = require_user(request)
        throttle(request, "provider-probe-ip", client_key(request), 5, 60)
        throttle(request, "provider-probe-user", user.id, 10, 3600)
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
        "roles": roles,
        "sam": {"provider": settings.sam_provider, "model": settings.sam_model},
        "voice": {"model": settings.voice_model},
        "probes": probes,
    }
