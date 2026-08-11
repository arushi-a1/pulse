"""
Simulates a small fleet of devices sending telemetry to a running Pulse API.
Not part of the test suite or load-testing harness -- just a convenience
script for demoing the dashboard locally with a steady trickle of events.

    python scripts/seed_events.py --devices 20 --rate 5 --duration 60
"""
import argparse
import random
import time
import uuid

import requests


def random_event(device_id: str) -> dict:
    return {
        "device_id": device_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_type": random.choice(["sensor_reading", "sensor_reading", "sensor_reading", "heartbeat"]),
        "payload": {
            "temperature": round(random.uniform(-10, 45), 2),
            "battery": round(random.uniform(5, 100), 2),
            "latitude": round(random.uniform(47.4, 47.8), 4),  # roughly Seattle area
            "longitude": round(random.uniform(-122.5, -122.1), 4),
        },
        "event_id": uuid.uuid4().hex,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Pulse with simulated device telemetry")
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--devices", type=int, default=10)
    parser.add_argument("--rate", type=float, default=2.0, help="events per second, aggregate")
    parser.add_argument("--duration", type=int, default=30, help="seconds to run")
    args = parser.parse_args()

    device_ids = [f"uav-{i:04d}" for i in range(args.devices)]
    interval = 1.0 / args.rate
    end_time = time.time() + args.duration
    sent, failed = 0, 0

    print(f"Sending ~{args.rate} events/sec across {args.devices} devices for {args.duration}s to {args.host}")
    while time.time() < end_time:
        device_id = random.choice(device_ids)
        try:
            resp = requests.post(f"{args.host}/events", json=random_event(device_id), timeout=5)
            if resp.status_code == 202:
                sent += 1
            else:
                failed += 1
        except requests.RequestException:
            failed += 1
        time.sleep(interval)

    print(f"Done. Sent={sent} Failed={failed}")


if __name__ == "__main__":
    main()
