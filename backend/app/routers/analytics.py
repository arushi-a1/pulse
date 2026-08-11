from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.redis_client import cache_stats
from app.db import get_db
from app.models import ProcessingFailure
from app.schemas import AnalyticsSummary
from app.services.analytics_service import get_summary, queue_depth_snapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(db: Session = Depends(get_db)) -> AnalyticsSummary:
    return get_summary(db)


@router.get("/queue")
def queue_status() -> dict:
    return {"approximate_queue_depth": queue_depth_snapshot()}


@router.get("/cache")
def cache_status() -> dict:
    return cache_stats()


@router.get("/failures")
def recent_failures(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    limit = min(limit, 100)
    rows = db.scalars(
        select(ProcessingFailure).order_by(ProcessingFailure.created_at.desc()).limit(limit)
    )
    return [
        {"event_id": r.event_id, "error": r.error, "attempt": r.attempt, "created_at": r.created_at}
        for r in rows
    ]
