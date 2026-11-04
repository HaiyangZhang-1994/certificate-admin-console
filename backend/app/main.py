import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.exc import OperationalError

from app.contracts import ErrorCode, HealthResponse
from app.database import initialize, make_engine
from app.errors import error_response, register_error_handlers
from app.routes import router
from app.seed import seed
from app.services.auth import Sessions

logger = logging.getLogger(__name__)


def create_app(database_url=None, *, seed_demo=None, busy_timeout=3000) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(database_url, busy_timeout)
        app.state.engine = engine
        app.state.sessions = Sessions(int(os.getenv("SESSION_TTL_SECONDS", "28800")))
        app.state.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
        try:
            initialize(engine)
            should_seed = seed_demo if seed_demo is not None else os.getenv("SEED_DEMO") == "true"
            if should_seed:
                seed(engine)
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Certificate Admin API",
        version="1.0.0",
        description="Tenant-isolated certificate administration API.",
        lifespan=lifespan,
    )
    register_error_handlers(app)

    allowed_origins = {
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173").split(",")
    }

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if not origin or origin == "null" or origin not in allowed_origins:
                return error_response(403, ErrorCode.FORBIDDEN_ORIGIN, "Origin is not allowed.")
        try:
            return await call_next(request)
        except OperationalError as exc:
            if (getattr(exc.orig, "sqlite_errorcode", 0) & 0xFF) in (5, 6):
                return error_response(
                    503, ErrorCode.DATABASE_BUSY, "Please retry with the same idempotency key."
                )
            logger.exception("Database operation failed")
            return error_response(500, ErrorCode.INTERNAL_ERROR, "Operation failed.")
        except Exception:
            logger.exception("Request failed")
            return error_response(500, ErrorCode.INTERNAL_ERROR, "Operation failed.")

    @app.get("/api/health", response_model=HealthResponse, operation_id="health", tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="certificate-admin-api")

    app.include_router(router)
    return app


app = create_app()
