import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.logging_config import ContextFilter, configure_logging
from app.middleware import RequestContextMiddleware
from app.routers import analytics, devices, events, health

configure_logging()
logging.getLogger().addFilter(ContextFilter(service="api"))
logger = logging.getLogger(__name__)

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

app = FastAPI(
    title="Pulse",
    description="Distributed real-time event processing and analytics platform",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Centralized error handling: never leak stack traces, always return a
    # consistent, structured error body with the request id for correlation.
    request_id = getattr(request.state, "request_id", "-")
    logger.warning("validation_error", extra={"request_id": request_id, "errors": exc.errors()})
    # pydantic's error "ctx" can carry a raw Exception object (e.g. from a
    # field_validator raising ValueError), which json.dumps can't serialize.
    # Strip ctx and keep the human-readable msg/loc/type instead.
    safe_errors = [{k: v for k, v in err.items() if k != "ctx"} for err in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "validation_error", "request_id": request_id, "details": jsonable_encoder(safe_errors)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    logger.error("unhandled_exception", extra={"request_id": request_id, "error": str(exc)}, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "request_id": request_id},
    )


app.include_router(health.router)
app.include_router(events.router)
app.include_router(devices.router)
app.include_router(analytics.router)

if os.getenv("ENABLE_BENCHMARK_ROUTES") == "1":
    from app.routers import benchmark

    app.include_router(benchmark.router)
    logger.warning("benchmark_routes_enabled", extra={"note": "not for production use"})


@app.get("/")
def root():
    return {"service": "pulse", "status": "running"}
