import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("pulse.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Stamps every request with a correlation id (or reuses one supplied by
    an upstream caller/load balancer), attaches it to the response, and logs
    a structured access line. The worker logs the same event_id in every
    message it processes, so a single event can be traced end-to-end through
    CloudWatch Logs Insights by filtering on request_id / event_id."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
