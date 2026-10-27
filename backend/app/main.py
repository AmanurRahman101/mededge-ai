from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dev, health, runs
from app.config import Settings, get_settings
from app.events import EventBus
from app.models.router import ModelRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    timeout = httpx.Timeout(settings.request_timeout_s, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        app.state.http = http
        app.state.router = ModelRouter(settings, http)
        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="MedEdge AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.bus = EventBus()
    app.state.tasks = set()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(runs.router)
    if settings.enable_dev_routes:
        app.include_router(dev.router)
    return app


app = create_app()
