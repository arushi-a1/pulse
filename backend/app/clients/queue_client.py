"""
Thin wrapper around boto3 SQS. Using the same client code against localstack
(local dev, via AWS_ENDPOINT_URL) and real AWS SQS (prod, endpoint_url=None)
means the async pipeline is exercised identically in both environments —
what we load-test locally is the same code path that runs in ECS.
"""
import json
import logging
from typing import Any

import boto3
from botocore.config import Config
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = boto3.client(
    "sqs",
    region_name=settings.aws_region,
    endpoint_url=settings.aws_endpoint_url,
    config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
def send_event(message: dict[str, Any], queue_url: str | None = None) -> str:
    """Enqueue one event. Retries with exponential backoff on transient
    boto3/network errors before surfacing a failure to the caller."""
    resp = _client.send_message(
        QueueUrl=queue_url or settings.sqs_queue_url,
        MessageBody=json.dumps(message, default=str),
    )
    return resp["MessageId"]


def receive_events(max_messages: int = 10, wait_time_seconds: int = 5, queue_url: str | None = None) -> list[dict]:
    resp = _client.receive_message(
        QueueUrl=queue_url or settings.sqs_queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_time_seconds,
        AttributeNames=["ApproximateReceiveCount"],
    )
    return resp.get("Messages", [])


def delete_event(receipt_handle: str, queue_url: str | None = None) -> None:
    _client.delete_message(QueueUrl=queue_url or settings.sqs_queue_url, ReceiptHandle=receipt_handle)


def move_to_dlq(raw_body: str, reason: str) -> None:
    """Sends a message that can never succeed straight to the DLQ (with the
    reason attached) instead of waiting for SQS's redrive policy to move it
    after max receives. The caller deletes it from the main queue only after
    this succeeds, so a failure here falls back to normal redrive."""
    _client.send_message(
        QueueUrl=settings.sqs_dlq_url,
        MessageBody=raw_body,
        MessageAttributes={"failure_reason": {"DataType": "String", "StringValue": reason[:1024] or "unknown"}},
    )


def queue_depth(queue_url: str | None = None) -> int:
    """Used both by the /analytics endpoint and, in prod, backs the CloudWatch
    ApproximateNumberOfMessagesVisible alarm that drives worker autoscaling."""
    resp = _client.get_queue_attributes(
        QueueUrl=queue_url or settings.sqs_queue_url,
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    return int(resp["Attributes"]["ApproximateNumberOfMessages"])
