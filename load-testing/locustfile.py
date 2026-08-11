"""
Load test against the real Pulse API (POST /events -> SQS enqueue).

Run against the local docker-compose stack (or, as documented in the README,
the bare-process local stack used to develop this project):

    locust -f load-testing/locustfile.py --host http://localhost:8000

Headless example (the actual command used to produce the numbers in the
README's Performance Results section):

    locust -f load-testing/locustfile.py --host http://localhost:8000 \
        --headless -u 50 -r 10 -t 60s --csv=load-testing/results/async_50u
"""
import random
import uuid

from locust import HttpUser, task, between


def _random_event() -> dict:
    return {
        "device_id": f"uav-{random.randint(1, 200):04d}",
        "timestamp": "2026-08-10T12:00:00Z",
        "event_type": random.choice(["sensor_reading", "heartbeat"]),
        "payload": {
            "temperature": round(random.uniform(-10, 45), 2),
            "battery": round(random.uniform(0, 100), 2),
            "latitude": round(random.uniform(-90, 90), 4),
            "longitude": round(random.uniform(-180, 180), 4),
        },
        "event_id": uuid.uuid4().hex,  # unique per request; not testing dedup here
    }


class PulseUser(HttpUser):
    """Simulates a fleet of devices continuously posting telemetry, plus the
    occasional dashboard read (mixed read/write load, closer to real usage
    than a pure write benchmark)."""

    wait_time = between(0.05, 0.2)

    @task(8)
    def post_event(self):
        self.client.post("/events", json=_random_event(), name="POST /events")

    @task(1)
    def read_summary(self):
        self.client.get("/analytics/summary", name="GET /analytics/summary")

    @task(1)
    def read_device_metrics(self):
        device_id = f"uav-{random.randint(1, 200):04d}"
        self.client.get(f"/devices/{device_id}/metrics", name="GET /devices/:id/metrics")
