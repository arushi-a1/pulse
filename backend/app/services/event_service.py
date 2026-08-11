import logging

from app.clients.queue_client import send_event
from app.schemas import EventIn

logger = logging.getLogger(__name__)


def enqueue_event(event: EventIn, request_id: str) -> str:
    """The only thing the API does synchronously: validate (already done by
    Pydantic before we get here) and enqueue. No DB write, no S3 call, no
    analytics update happens on this path — that's the worker's job. This is
    what keeps POST /events latency flat under load."""
    event_id = event.resolved_event_id()
    message = {
        "event_id": event_id,
        "device_id": event.device_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat(),
        "payload": event.payload.model_dump(),
        "request_id": request_id,
    }
    send_event(message)
    logger.info("event_enqueued", extra={"request_id": request_id, "event_id": event_id, "device_id": event.device_id})
    return event_id
