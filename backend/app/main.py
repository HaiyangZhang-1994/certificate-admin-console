from fastapi import FastAPI

from app.contracts import HealthResponse
from app.errors import register_error_handlers
from app.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Certificate Admin API",
        version="1.0.0",
        description="Tenant-isolated certificate administration API.",
    )
    register_error_handlers(app)

    @app.get("/api/health", response_model=HealthResponse, operation_id="health", tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="certificate-admin-api")

    app.include_router(router)
    return app


app = create_app()
