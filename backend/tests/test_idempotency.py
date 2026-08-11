
from sqlalchemy import select

from app.models import Device, Event, ProcessingFailure
from worker.processor import TransientProcessingError, process_event


def _message(device_id: str, event_id: str, temperature: float = 20.0) -> dict:
    return {
        "event_id": event_id,
        "device_id": device_id,
        "event_type": "sensor_reading",
        "timestamp": "2026-08-10T12:00:00",
        "payload": {"temperature": temperature, "battery": 50.0, "latitude": 47.6, "longitude": -122.3},
        "request_id": "test-request-id",
    }


def test_process_event_creates_device_and_event(db_session, unique_id):
    msg = _message(f"dev-{unique_id}", f"evt-{unique_id}")
    process_event(db_session, msg, receive_count=1)

    device = db_session.get(Device, f"dev-{unique_id}")
    assert device is not None
    assert device.event_count == 1

    event = db_session.scalar(select(Event).where(Event.event_id == f"evt-{unique_id}"))
    assert event is not None
    assert event.processed_at is not None
    assert event.s3_archive_key is not None


def test_process_event_is_idempotent_on_duplicate_event_id(db_session, unique_id):
    device_id = f"dev-{unique_id}"
    event_id = f"evt-{unique_id}"

    process_event(db_session, _message(device_id, event_id, temperature=20.0), receive_count=1)
    # Same event_id arrives again (SQS at-least-once redelivery) with
    # different payload values -- must be a no-op, not an overwrite.
    process_event(db_session, _message(device_id, event_id, temperature=999.0), receive_count=2)

    events = list(db_session.scalars(select(Event).where(Event.event_id == event_id)))
    assert len(events) == 1
    assert events[0].payload["temperature"] == 20.0  # original value preserved

    device = db_session.get(Device, device_id)
    assert device.event_count == 1  # not double-counted


def test_process_event_increments_device_event_count_across_distinct_events(db_session, unique_id):
    device_id = f"dev-{unique_id}"
    process_event(db_session, _message(device_id, f"evt-a-{unique_id}"), receive_count=1)
    process_event(db_session, _message(device_id, f"evt-b-{unique_id}"), receive_count=1)

    device = db_session.get(Device, device_id)
    assert device.event_count == 2


def test_process_event_raises_transient_error_on_malformed_timestamp(db_session, unique_id):
    # Pydantic guarantees payload completeness on the way in, so the realistic
    # failure mode here is a message that fails to parse downstream (e.g. an
    # unparsable timestamp reaching the hourly-rollup bucketing logic).
    msg = _message(f"dev-{unique_id}", f"evt-{unique_id}")
    msg["timestamp"] = "not-a-valid-timestamp"

    import pytest

    with pytest.raises(TransientProcessingError):
        process_event(db_session, msg, receive_count=1)


def test_failed_processing_is_logged_for_visibility(db_session, unique_id):
    msg = _message(f"dev-{unique_id}", f"evt-{unique_id}")
    msg["timestamp"] = "not-a-valid-timestamp"

    import pytest

    with pytest.raises(TransientProcessingError):
        process_event(db_session, msg, receive_count=3)

    failure = db_session.scalar(
        select(ProcessingFailure).where(ProcessingFailure.event_id == f"evt-{unique_id}")
    )
    assert failure is not None
    assert failure.attempt == 3
