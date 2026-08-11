import json

from sqlalchemy import select

from app.clients.queue_client import receive_events, send_event
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
    # -- it should be logged and skipped so one bad message can't take down
    # the whole consumer.
    fake_msg = {"Body": "{not valid json", "ReceiptHandle": "fake", "Attributes": {}}
    _handle_message(fake_msg)  # should not raise
