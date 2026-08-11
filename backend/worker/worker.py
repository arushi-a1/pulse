"""
Standalone worker process (run as its own ECS service/task in prod, `python
-m worker.worker` locally). Deliberately separate from the API process so it
scales independently: worker desired-count tracks SQS ApproximateNumberOf
MessagesVisible, while the API tracks request count/CPU.

Failure handling summary (see README "Failure Scenarios" for the full table):
  - Transient error (DB/S3 blip)  -> message left on queue, SQS redelivers
                                      after visibility timeout, exponential
                                      backoff is achieved via SQS's own
                                      redrive + a jittered sleep here.
  - Same event fails repeatedly   -> after `worker_max_receive_count`
                                      attempts, SQS's redrive policy moves it
                                      to the DLQ automatically (configured in
                                      Terraform, not in this code).
  - Worker process crashes mid-  -> message is simply not deleted; it
    processing                     becomes visible again and is retried by
                                    another worker. Idempotency guarantees
                                    this is safe even if the crash happened
                                    after a partial commit.
  - Duplicate delivery            -> handled by the unique event_id
                                      constraint in processor.process_event.
"""
import json
import logging
import random
import signal
import time

from app.clients.queue_client import delete_event, receive_events
from app.config import get_settings
from app.db import SessionLocal
from app.logging_config import ContextFilter, configure_logging
from worker.processor import PermanentProcessingError, TransientProcessingError, process_event

configure_logging()
logging.getLogger().addFilter(ContextFilter(service="worker"))
logger = logging.getLogger(__name__)

settings = get_settings()
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("shutdown_signal_received", extra={"signal": signum})
    _shutdown = True


def run_forever() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    logger.info("worker_started")

    consecutive_empty_polls = 0

    while not _shutdown:
        try:
            messages = receive_events(max_messages=settings.worker_batch_size, wait_time_seconds=5)
        except Exception as exc:
            # Queue itself unreachable (network partition, wrong creds, etc).
            # Back off instead of hot-looping and log loudly so CloudWatch
            # alarms on worker error rate can fire.
            logger.error("queue_poll_failed", extra={"error": str(exc)})
            time.sleep(min(2 ** min(consecutive_empty_polls, 5), 30))
            consecutive_empty_polls += 1
            continue

        if not messages:
            consecutive_empty_polls += 1
            time.sleep(settings.worker_poll_interval_seconds)
            continue

        consecutive_empty_polls = 0
        for msg in messages:
            _handle_message(msg)

    logger.info("worker_stopped_gracefully")


def _handle_message(msg: dict) -> None:
    receive_count = int(msg.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
    try:
        body = json.loads(msg["Body"])
    except (KeyError, json.JSONDecodeError) as exc:
        # Malformed message body can never succeed -> do not delete, let it
        # exhaust retries and land in the DLQ for manual inspection rather
        # than silently discarding it.
        logger.error("malformed_message", extra={"error": str(exc)})
        return

    db = SessionLocal()
    try:
        process_event(db, body, receive_count)
        delete_event(msg["ReceiptHandle"])  # only delete on confirmed success
    except TransientProcessingError:
        # Jittered backoff before this worker moves on, so a struggling
        # dependency (e.g. RDS under load) gets breathing room; the message
        # itself is retried by SQS on its own visibility-timeout schedule.
        time.sleep(min(0.5 * (2 ** min(receive_count, 4)), 8) + random.uniform(0, 0.5))
    except PermanentProcessingError:
        logger.error("permanent_failure_awaiting_dlq", extra={"event_id": body.get("event_id")})
    finally:
        db.close()


if __name__ == "__main__":
    run_forever()
