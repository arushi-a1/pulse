"""
Benchmark-only comparison load test, exercising /benchmark/sync-events (see
app/routers/benchmark.py). Requires ENABLE_BENCHMARK_ROUTES=1 on the API.

    locust -f load-testing/locustfile_sync_benchmark.py --host http://localhost:8000 \
        --headless -u 50 -r 10 -t 60s --csv=load-testing/results/sync_50u
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
        "event_id": uuid.uuid4().hex,
    }


class SyncBenchmarkUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task
    def post_event_sync(self):
        self.client.post("/benchmark/sync-events", json=_random_event(), name="POST /benchmark/sync-events")
