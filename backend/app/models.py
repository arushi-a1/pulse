import datetime as dt

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)
    event_count: Mapped[int] = mapped_column(Integer, default=0)

    events: Mapped[list["Event"]] = relationship(back_populates="device")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_events_event_id"),  # idempotency guarantee
        Index("ix_events_device_received", "device_id", "received_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    s3_archive_key: Mapped[str | None] = mapped_column(String(256), nullable=True)

    device: Mapped["Device"] = relationship(back_populates="events")


class DeviceMetricHourly(Base):
    __tablename__ = "device_metrics_hourly"
    __table_args__ = (UniqueConstraint("device_id", "hour_bucket", name="uq_device_hour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    hour_bucket: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    avg_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_battery: Mapped[float | None] = mapped_column(Float, nullable=True)
    reading_count: Mapped[int] = mapped_column(Integer, default=0)


class ProcessingFailure(Base):
    __tablename__ = "processing_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    error: Mapped[str] = mapped_column(String(1024), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)
