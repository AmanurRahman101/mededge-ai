import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import update

from app import demo
from app.api import auth, cases, chart, dev, health, runs, share
from app.auth.security import verify_request
from app.config import REPO_ROOT, Settings, get_settings
from app.events import EventBus
from app.limit import limiter
from app.models.router import ModelRouter
from app.pipeline.orchestrator import Orchestrator
from app.store.db import Database, RunRow
from app.store.object_storage import configured_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    if settings.app_env == "production":
        from urllib.parse import urlsplit

        public_url = urlsplit(settings.app_base_url)
        if (
            public_url.scheme != "https"
            or not public_url.netloc
            or public_url.path not in ("", "/")
            or public_url.query
            or public_url.fragment
        ):
            raise RuntimeError("Production requires an HTTPS APP_BASE_URL origin.")
        if not settings.database_url.startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        ):
            raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")
        salt = settings.pseudonym_salt
        if salt in ("", "mededge", "change-me") or len(salt) < 16:
            raise RuntimeError("Production requires a unique PSEUDONYM_SALT of 16+ characters.")
        if (
            not settings.resend_api_key
            or not settings.resend_api_key.get_secret_value()
            or not settings.resend_from_email
        ):
            raise RuntimeError("Production requires RESEND_API_KEY and RESEND_FROM_EMAIL.")
    timeout = httpx.Timeout(settings.request_timeout_s, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        app.state.http = http
        app.state.router = ModelRouter(settings, http)
        app.state.db = Database(settings)
        app.state.object_storage = configured_storage(settings)
        # In-process jobs and confirmation gates do not survive a restart.
        with app.state.db.session() as session:
            session.exec(
                update(RunRow)
                .where(RunRow.status.in_(["queued", "awaiting_confirmation", "processing"]))
                .values(status="interrupted")
            )
            session.commit()
        app.state.orchestrator = Orchestrator(
            settings, http, app.state.router, app.state.bus, app.state.db
        )
        app.state.orchestrator.storage = app.state.object_storage
        await asyncio.to_thread(demo.reset, app.state.db, settings)
        reset_task = asyncio.create_task(demo.reset_loop(app.state.db, settings))
        try:
            yield
        finally:
            reset_task.cancel()


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
        allow_origins=(
            [settings.app_base_url.rstrip("/")]
            if settings.app_env == "production"
            else settings.cors_origin_list
        ),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def protect_api_mutations(request: Request, call_next):
        if request.url.path.startswith("/api/dev/") and (
            settings.app_env == "production" or not settings.enable_dev_routes
        ):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        if request.url.path.startswith("/api/") and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            try:
                verify_request(request)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        response = await call_next(request)
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if settings.app_env == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            )
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chart.router)
    app.include_router(runs.router)
    app.include_router(cases.router)
    app.include_router(share.router)
    if settings.enable_dev_routes and settings.app_env != "production":
        app.include_router(dev.router)

    @app.api_route(
        "/api/{unmatched:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def unknown_api(unmatched: str):
        raise HTTPException(status_code=404, detail="Not found")

    # The production container serves the built browser app from the same
    # origin as the API. In development Vite handles these routes instead.
    frontend_dir = (REPO_ROOT / "frontend" / "dist").resolve()
    if (frontend_dir / "index.html").is_file():

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str) -> FileResponse:
            if path == "api" or path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            asset = (frontend_dir / path).resolve()
            if not asset.is_relative_to(frontend_dir):
                raise HTTPException(status_code=404, detail="Not found")
            if asset.is_file():
                return FileResponse(asset, headers={"Referrer-Policy": "no-referrer"})
            if "." in asset.name:
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(
                frontend_dir / "index.html",
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )

    return app


app = create_app()
