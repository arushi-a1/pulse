import datetime as dt
import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.clients.redis_client import invalidate, invalidate_prefix
from app.clients.storage_client import archive_raw_event
from app.models import Device, DeviceMetricHourly, Event, ProcessingFailure

logger = logging.getLogger(__name__)


class TransientProcessingError(Exception):
    """Raised for retryable failures (DB hiccup, S3 timeout). The message is
    NOT deleted from SQS when this is raised, so it becomes visible again
    after the visibility timeout and SQS itself retries delivery."""


class PermanentProcessingError(Exception):
    """Raised for failures that will never succeed on retry (malformed
    payload that somehow got past validation). Still not deleted here —
    left to age out to the DLQ after max receives rather than silently
    dropped, so nothing is ever lost without a trace."""


def process_event(db: Session, message_body: dict, receive_count: int) -> None:
    event_id = message_body["event_id"]
    device_id = message_body["device_id"]

    # --- Idempotency guard -------------------------------------------------
    # A duplicate can arrive because: (a) SQS's at-least-once delivery model,
    # (b) a client retry after a timed-out but actually-successful POST, or
    # (c) a worker crash after processing but before deleting the message.
    # The unique constraint on events.event_id makes re-processing a no-op.
    existing = db.query(Event).filter(Event.event_id == event_id).one_or_none()
    if existing is not None:
        logger.info(
            "duplicate_event_skipped",
            extra={"event_id": event_id, "device_id": device_id, "request_id": message_body.get("request_id", "-")},
        )
        return

    try:
        _upsert_device(db, device_id, message_body["timestamp"])
        s3_key = archive_raw_event(event_id, device_id, message_body)

        event_row = Event(
            event_id=event_id,
            device_id=device_id,
            event_type=message_body["event_type"],
            payload=message_body["payload"],
            processed_at=dt.datetime.utcnow(),
            s3_archive_key=s3_key,
        )
        db.add(event_row)
        _update_hourly_rollup(db, device_id, message_body)
        db.commit()

        invalidate(f"analytics:device:{device_id}")
        invalidate_prefix("analytics:summary")

        logger.info(
            "event_processed",
            extra={"event_id": event_id, "device_id": device_id, "request_id": message_body.get("request_id", "-")},
        )
    except Exception as exc:
        db.rollback()
        _record_failure(db, event_id, str(exc), receive_count)
        logger.error(
            "event_processing_failed",
            extra={"event_id": event_id, "device_id": device_id, "attempt": receive_count, "error": str(exc)},
        )
        raise TransientProcessingError(str(exc)) from exc


def _upsert_device(db: Session, device_id: str, timestamp: str) -> None:
    stmt = insert(Device).values(
        device_id=device_id,
        first_seen=timestamp,
        last_seen=timestamp,
        event_count=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["device_id"],
        set_={"last_seen": timestamp, "event_count": Device.event_count + 1},
    )
    db.execute(stmt)


def _update_hourly_rollup(db: Session, device_id: str, message_body: dict) -> None:
    ts = dt.datetime.fromisoformat(message_body["timestamp"])
    hour_bucket = ts.replace(minute=0, second=0, microsecond=0)
    payload = message_body["payload"]

    existing = (
        db.query(DeviceMetricHourly)
        .filter(DeviceMetricHourly.device_id == device_id, DeviceMetricHourly.hour_bucket == hour_bucket)
        .one_or_none()
    )
    if existing:
        n = existing.reading_count
        existing.avg_temperature = ((existing.avg_temperature or 0) * n + payload["temperature"]) / (n + 1)
        existing.avg_battery = ((existing.avg_battery or 0) * n + payload["battery"]) / (n + 1)
        existing.reading_count = n + 1
    else:
        db.add(
            DeviceMetricHourly(
                device_id=device_id,
                hour_bucket=hour_bucket,
                avg_temperature=payload.get("temperature"),
                avg_battery=payload.get("battery"),
                reading_count=1,
            )
        )


def _record_failure(db: Session, event_id: str, error: str, attempt: int) -> None:
    try:
        db.add(ProcessingFailure(event_id=event_id, error=error[:1024], attempt=attempt))
        db.commit()
    except Exception:
        db.rollback()  # never let failure logging itself crash the worker
