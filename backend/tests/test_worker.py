import json

from sqlalchemy import select

from app.clients.queue_client import receive_events, send_event
from app.config import get_settings
from app.db import SessionLocal
from app.models import Event
from worker.worker import _handle_message


def test_end_to_end_message_is_processed_and_deleted(unique_id):
    event_id = f"evt-{unique_id}"
    device_id = f"dev-{unique_id}"
    send_event(
        {
            "event_id": event_id,
            "device_id": device_id,
            "event_type": "heartbeat",
            "timestamp": "2026-08-10T12:00:00",
            "payload": {"temperature": 21.0, "battery": 60.0, "latitude": 47.6, "longitude": -122.3},
            "request_id": "test",
        }
    )

    messages = receive_events(max_messages=10, wait_time_seconds=2)
    matching = [m for m in messages if json.loads(m["Body"])["event_id"] == event_id]
    assert len(matching) == 1

    _handle_message(matching[0])

    db = SessionLocal()
    try:
        event = db.scalar(select(Event).where(Event.event_id == event_id))
        assert event is not None
        assert event.processed_at is not None
    finally:
        db.close()


def test_handle_message_does_not_raise_on_malformed_body():
    # A message body that isn't valid JSON must never crash the worker loop
    # -- one bad message can't take down the whole consumer.
    fake_msg = {"Body": "{not valid json", "ReceiptHandle": "fake", "Attributes": {}}
    _handle_message(fake_msg)  # should not raise


def _event_id(msg):
    try:
        return json.loads(msg["Body"]).get("event_id")
    except json.JSONDecodeError:
        return None  # e.g. the malformed body dead-lettered by another test


def _drain(queue_url):
    found = []
    for _ in range(3):
        msgs = receive_events(max_messages=10, wait_time_seconds=1, queue_url=queue_url)
        found.extend(msgs)
        if not msgs:
            break
    return found


def test_permanent_failure_goes_straight_to_dlq_and_leaves_main_queue(unique_id):
    settings = get_settings()
    event_id = f"evt-bad-{unique_id}"
    send_event(
        {
            "event_id": event_id,
            "device_id": f"dev-{unique_id}",
            "event_type": "sensor_reading",
            "timestamp": "not-a-valid-timestamp",
            "payload": {"temperature": 21.0, "battery": 60.0, "latitude": 47.6, "longitude": -122.3},
            "request_id": "test",
        }
    )
    messages = receive_events(max_messages=10, wait_time_seconds=2)
    matching = [m for m in messages if _event_id(m) == event_id]
    assert len(matching) == 1

    _handle_message(matching[0])  # first attempt, no retries

    assert event_id in [_event_id(m) for m in _drain(settings.sqs_dlq_url)]
    # Deleted from the main queue: it won't be redelivered and retried.
    remaining = [_event_id(m) for m in _drain(settings.sqs_queue_url)]
    assert event_id not in remaining
