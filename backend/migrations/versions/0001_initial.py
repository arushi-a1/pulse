"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(128), primary_key=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_count", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.device_id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("s3_archive_key", sa.String(256), nullable=True),
    )
    op.create_unique_constraint("uq_events_event_id", "events", ["event_id"])
    op.create_index("ix_events_device_received", "events", ["device_id", "received_at"])

    op.create_table(
        "device_metrics_hourly",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.device_id"), nullable=False),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avg_temperature", sa.Float, nullable=True),
        sa.Column("avg_battery", sa.Float, nullable=True),
        sa.Column("reading_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_unique_constraint("uq_device_hour", "device_metrics_hourly", ["device_id", "hour_bucket"])

    op.create_table(
        "processing_failures",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("error", sa.String(1024), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processing_failures")
    op.drop_table("device_metrics_hourly")
    op.drop_table("events")
    op.drop_table("devices")
