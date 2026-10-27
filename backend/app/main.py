from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import cases, dev, health, runs, share, voice
from app.config import Settings, get_settings
from app.events import EventBus
from app.limit import limiter
from app.models.router import ModelRouter
from app.pipeline.orchestrator import Orchestrator
from app.store.db import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    timeout = httpx.Timeout(settings.request_timeout_s, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        app.state.http = http
        app.state.router = ModelRouter(settings, http)
        app.state.db = Database(settings)
        app.state.db.purge()
        app.state.orchestrator = Orchestrator(
            settings, http, app.state.router, app.state.bus, app.state.db
        )
        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="MedEdge AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.bus = EventBus()
    app.state.tasks = set()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(runs.router)
    app.include_router(cases.router)
    app.include_router(share.router)
    app.include_router(voice.router)
    if settings.enable_dev_routes:
        app.include_router(dev.router)
    return app


app = create_app()
