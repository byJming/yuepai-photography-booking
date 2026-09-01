from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import redis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.database import build_engine, build_session_factory
from app.core.errors import BusinessError
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def _payload(data: Any, request_id: str) -> dict[str, Any]:
    return {"data": data, "request_id": request_id}


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.app_log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(8.0))
        resolved.media_root.mkdir(parents=True, exist_ok=True)
        try:
            yield
        finally:
            await app.state.http_client.aclose()
            app.state.redis.close()
            app.state.engine.dispose()

    app = FastAPI(title="摄影预约 API", version="1.0.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = build_engine(resolved)
    app.state.session_factory = build_session_factory(app.state.engine)
    app.state.redis = redis.Redis.from_url(resolved.redis_url, decode_responses=True)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith(resolved.admin_api_v1_prefix):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.public_message,
                    "details": exc.details,
                },
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "请检查填写内容。",
                    "details": {"fields": details},
                },
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unexpected_error",
            exc_info=exc,
            extra={"request_id": request.state.request_id, "error_code": "INTERNAL_ERROR"},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务暂时不可用，请稍后重试。",
                    "details": {},
                },
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health/live")
    def live(request: Request) -> dict[str, Any]:
        return _payload({"status": "ok"}, request.state.request_id)

    @app.get("/health/ready")
    def ready(request: Request) -> JSONResponse:
        checks: dict[str, str] = {}
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["mysql"] = "ok"
        except Exception:
            checks["mysql"] = "error"
        try:
            app.state.redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
        status_code = 200 if all(value == "ok" for value in checks.values()) else 503
        return JSONResponse(
            status_code=status_code,
            content=_payload(
                {"status": "ok" if status_code == 200 else "degraded", **checks},
                request.state.request_id,
            ),
        )

    from app.admin_api.auth import router as admin_auth_router
    from app.admin_api.bookings import router as admin_booking_router
    from app.admin_api.content import router as admin_content_router
    from app.api.auth import router as customer_auth_router
    from app.api.bookings import router as customer_booking_router
    from app.api.public import router as public_router

    app.include_router(customer_auth_router, prefix=resolved.api_v1_prefix)
    app.include_router(customer_booking_router, prefix=resolved.api_v1_prefix)
    app.include_router(public_router, prefix=resolved.api_v1_prefix)
    app.include_router(admin_auth_router, prefix=resolved.admin_api_v1_prefix)
    app.include_router(admin_booking_router, prefix=resolved.admin_api_v1_prefix)
    app.include_router(admin_content_router, prefix=resolved.admin_api_v1_prefix)

    return app


app = create_app()
