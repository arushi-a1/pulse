"""
Centralized configuration. Every value is sourced from the environment so
nothing secret ever lives in source control. See .env.example for the full
list of variables and docker-compose.yml for local defaults.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "pulse"
    environment: str = "local"  # local | dev | prod
    log_level: str = "INFO"

    # Postgres
    database_url: str = "postgresql://pulse:pulse@localhost:5432/pulse"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 30

    # Queue (SQS in prod, SQS-compatible endpoint via localstack for local dev)
    aws_region: str = "us-west-2"
    aws_endpoint_url: str | None = "http://localhost:4566"  # None in real AWS
    sqs_queue_url: str = "http://localhost:4566/000000000000/pulse-events"
    sqs_dlq_url: str = "http://localhost:4566/000000000000/pulse-events-dlq"

    # S3
    s3_bucket: str = "pulse-raw-events"

    # Worker
    worker_poll_interval_seconds: float = 1.0
    worker_max_receive_count: int = 5  # after this many failed attempts -> DLQ
    worker_batch_size: int = 10

    # Security
    rate_limit_per_minute: int = 600
    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
