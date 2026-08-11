import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clients.queue_client import queue_depth
from app.clients.redis_client import client as redis_client
from app.db import get_db
from app.schemas import HealthStatus

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthStatus)
def liveness() -> HealthStatus:
    """Liveness: process is up. Kept dependency-free so ECS doesn't kill a
    healthy container just because a downstream is briefly unavailable."""
    return HealthStatus(status="ok", database=True, redis=True, queue=True)


@router.get("/health/ready", response_model=HealthStatus)
def readiness(db: Session = Depends(get_db)) -> HealthStatus:
    """Readiness: can this instance actually serve traffic. Used by the ECS
    target group health check to pull an instance out of rotation."""
    db_ok = redis_ok = queue_ok = True

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness_db_failed", extra={"error": str(exc)})
        db_ok = False

    try:
        redis_client.ping()
    except Exception as exc:
        logger.warning("readiness_redis_failed", extra={"error": str(exc)})
        redis_ok = False

    try:
        queue_depth()
    except Exception as exc:
        logger.warning("readiness_queue_failed", extra={"error": str(exc)})
        queue_ok = False

    status = "ok" if (db_ok and queue_ok) else "degraded"  # redis is best-effort, not required
    return HealthStatus(status=status, database=db_ok, redis=redis_ok, queue=queue_ok)
