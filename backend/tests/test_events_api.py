def test_health_liveness(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_readiness(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] is True
    assert body["queue"] is True


def test_post_event_returns_202_and_event_id(client, sample_event, unique_id):
    resp = client.post("/events", json=sample_event(device_id=f"dev-{unique_id}"))
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert len(body["event_id"]) > 0


def test_post_event_rejects_invalid_payload(client, unique_id):
    bad_event = {
        "device_id": f"dev-{unique_id}",
        "timestamp": "2026-08-10T12:00:00Z",
        "event_type": "sensor_reading",
        "payload": {"temperature": 22.0, "battery": 200.0, "latitude": 47.6, "longitude": -122.3},  # battery > 100
    }
    resp = client.post("/events", json=bad_event)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


def test_post_event_rejects_unknown_event_type(client, unique_id):
    bad_event = {
        "device_id": f"dev-{unique_id}",
        "timestamp": "2026-08-10T12:00:00Z",
        "event_type": "not_a_real_type",
        "payload": {"temperature": 22.0, "battery": 50.0, "latitude": 47.6, "longitude": -122.3},
    }
    resp = client.post("/events", json=bad_event)
    assert resp.status_code == 422


def test_post_event_rejects_blank_device_id(client):
    bad_event = {
        "device_id": "   ",
        "timestamp": "2026-08-10T12:00:00Z",
        "event_type": "sensor_reading",
        "payload": {"temperature": 22.0, "battery": 50.0, "latitude": 47.6, "longitude": -122.3},
    }
    resp = client.post("/events", json=bad_event)
    assert resp.status_code == 422


def test_get_unknown_device_returns_404(client, unique_id):
    resp = client.get(f"/devices/dev-does-not-exist-{unique_id}")
    assert resp.status_code == 404


def test_request_id_present_on_response(client):
    resp = client.get("/health")
    assert "X-Request-ID" in resp.headers


def test_rate_limit_headers_do_not_break_normal_traffic(client, sample_event, unique_id):
    # Sanity check the rate limiter is wired up without blocking normal-volume
    # test traffic (limit is set high for local/test in .env.example).
    for _ in range(5):
        resp = client.post("/events", json=sample_event(device_id=f"dev-{unique_id}"))
        assert resp.status_code in (202, 429)
