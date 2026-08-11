"""
NOT part of Pulse's real API surface. This router exists solely so the load
tests can produce an apples-to-apples comparison between synchronous
in-request processing and the actual async SQS-based pipeline, using the
exact same processing logic (worker.processor.process_event) either way.

In a real deployment this router would not be mounted at all -- it's wired
in behind ENABLE_BENCHMARK_ROUTES so it's opt-in and obviously not
production surface area.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import EventIn
from worker.processor import TransientProcessingError, process_event

router = APIRouter(prefix="/benchmark", tags=["benchmark - not production API"])
logger = logging.getLogger(__name__)


@router.post("/sync-events", status_code=202)
def ingest_event_synchronously(event: EventIn, db: Session = Depends(get_db)) -> dict:
    """Does validation + DB write + S3 archive + rollup update all inline on
    the request thread -- i.e. the naive approach Pulse deliberately avoids.
    Used only to measure the latency/throughput cost of synchronous
    processing under load, for the README comparison."""
    message = {
        "event_id": event.resolved_event_id(),
        "device_id": event.device_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat(),
        "payload": event.payload.model_dump(),
        "request_id": "benchmark",
    }
    try:
        process_event(db, message, receive_count=1)
    except TransientProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"event_id": message["event_id"], "status": "processed_synchronously"}
