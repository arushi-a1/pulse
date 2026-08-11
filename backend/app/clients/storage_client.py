import json
import logging
from typing import Any

import boto3

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = boto3.client(
    "s3",
    region_name=settings.aws_region,
    endpoint_url=settings.aws_endpoint_url,
)


def archive_raw_event(event_id: str, device_id: str, raw_event: dict[str, Any]) -> str:
    """Archives the raw, untransformed event JSON to S3, keyed by device/date
    so it's cheap to scan a device's history or bulk-export by day. Kept
    separate from the structured Postgres row so the raw record survives
    schema changes / reprocessing needs."""
    key = f"raw-events/{device_id}/{event_id}.json"
    _client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=json.dumps(raw_event, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    return key


def ensure_bucket() -> None:
    """Local-dev/localstack convenience only — in real AWS the bucket is
    provisioned by Terraform, never by application code."""
    try:
        _client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        _client.create_bucket(Bucket=settings.s3_bucket)
