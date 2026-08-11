import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.queue_client import queue_depth
from app.clients.redis_client import cache_stats, get_or_set
from app.models import Device, Event
from app.schemas import AnalyticsSummary, DeviceMetrics


def get_summary(db: Session) -> AnalyticsSummary:
    def load() -> dict:
        total = db.scalar(select(func.count(Event.id))) or 0
        one_hour_ago = dt.datetime.utcnow() - dt.timedelta(hours=1)
        active = db.scalar(
            select(func.count(func.distinct(Event.device_id))).where(Event.received_at >= one_hour_ago)
        ) or 0
        recent_count = db.scalar(
            select(func.count(Event.id)).where(Event.received_at >= dt.datetime.utcnow() - dt.timedelta(seconds=60))
        ) or 0
        return {
            "total_events_processed": total,
            "active_devices_last_hour": active,
            "events_per_second_estimate": round(recent_count / 60, 3),
        }

    cached = get_or_set("analytics:summary", load, ttl=15)
    cached["cache_hit_rate"] = cache_stats()["hit_rate"]
    return AnalyticsSummary(**cached)


def get_device_metrics(db: Session, device_id: str) -> DeviceMetrics | None:
    def load() -> dict | None:
        one_hour_ago = dt.datetime.utcnow() - dt.timedelta(hours=1)
        row = db.execute(
            select(
                func.avg(Event.payload["temperature"].as_float()),
                func.avg(Event.payload["battery"].as_float()),
                func.count(Event.id),
            ).where(Event.device_id == device_id, Event.received_at >= one_hour_ago)
        ).first()
        if not row or row[2] == 0:
            device_exists = db.get(Device, device_id)
            if not device_exists:
                return None
            return {"device_id": device_id, "avg_temperature": None, "avg_battery": None, "reading_count": 0}
        return {
            "device_id": device_id,
            "avg_temperature": round(row[0], 2) if row[0] is not None else None,
            "avg_battery": round(row[1], 2) if row[1] is not None else None,
            "reading_count": row[2],
        }

    result = get_or_set(f"analytics:device:{device_id}", load, ttl=30)
    return DeviceMetrics(**result) if result else None


def queue_depth_snapshot() -> int:
    try:
        return queue_depth()
    except Exception:
        return -1  # queue unreachable; surfaced as degraded in /health, not a crash
