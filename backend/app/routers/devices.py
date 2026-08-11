from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Device, Event
from app.schemas import DeviceMetrics, DeviceOut
from app.services.analytics_service import get_device_metrics

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
def list_devices(limit: int = 50, db: Session = Depends(get_db)) -> list[Device]:
    limit = min(limit, 200)
    return list(db.scalars(select(Device).order_by(Device.last_seen.desc()).limit(limit)))


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)) -> Device:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return device


@router.get("/{device_id}/metrics", response_model=DeviceMetrics)
def device_metrics(device_id: str, db: Session = Depends(get_db)) -> DeviceMetrics:
    metrics = get_device_metrics(db, device_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="device not found")
    return metrics


@router.get("/{device_id}/events")
def device_recent_events(device_id: str, limit: int = 20, db: Session = Depends(get_db)):
    limit = min(limit, 100)
    events = db.scalars(
        select(Event).where(Event.device_id == device_id).order_by(Event.received_at.desc()).limit(limit)
    )
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "payload": e.payload,
            "received_at": e.received_at,
            "processed_at": e.processed_at,
        }
        for e in events
    ]
