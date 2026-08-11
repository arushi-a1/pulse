import datetime as dt
import hashlib
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SensorPayload(BaseModel):
    temperature: float = Field(ge=-100, le=150)
    battery: float = Field(ge=0, le=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class EventIn(BaseModel):
    """What a device/client sends. event_id is optional — if omitted we derive
    a deterministic one so retried/duplicate client sends are still idempotent."""

    device_id: str = Field(min_length=1, max_length=128)
    timestamp: dt.datetime
    event_type: Literal["sensor_reading", "heartbeat", "alert"]
    payload: SensorPayload
    event_id: str | None = Field(default=None, max_length=64)

    @field_validator("device_id")
    @classmethod
    def no_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("device_id must not be blank")
        return v.strip()

    def resolved_event_id(self) -> str:
        if self.event_id:
            return self.event_id
        raw = f"{self.device_id}:{self.event_type}:{self.timestamp.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


class EventAccepted(BaseModel):
    event_id: str
    status: Literal["accepted"] = "accepted"


class DeviceOut(BaseModel):
    device_id: str
    first_seen: dt.datetime
    last_seen: dt.datetime
    event_count: int

    class Config:
        from_attributes = True


class DeviceMetrics(BaseModel):
    device_id: str
    avg_temperature: float | None
    avg_battery: float | None
    reading_count: int
    window: str = "last_hour"


class AnalyticsSummary(BaseModel):
    total_events_processed: int
    active_devices_last_hour: int
    events_per_second_estimate: float
    cache_hit_rate: float


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    redis: bool
    queue: bool
