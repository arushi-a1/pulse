import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.main import app
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    # Tests run against the real local Postgres/Redis/moto stack (see
    # README "Testing" section) rather than mocks, so they exercise the same
    # SQL, JSON-payload extraction, and boto3 calls that run in prod.
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _clean_tables(db_session):
    yield
    for table in ("processing_failures", "device_metrics_hourly", "events", "devices"):
        db_session.execute(text(f"DELETE FROM {table}"))
    db_session.commit()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def sample_event():
    def _make(device_id: str = "test-device", event_id: str | None = None) -> dict:
        return {
            "device_id": device_id,
            "timestamp": "2026-08-10T12:00:00Z",
            "event_type": "sensor_reading",
            "payload": {"temperature": 22.0, "battery": 75.0, "latitude": 47.6, "longitude": -122.3},
            **({"event_id": event_id} if event_id else {}),
        }

    return _make


@pytest.fixture()
def unique_id():
    return uuid.uuid4().hex[:16]
