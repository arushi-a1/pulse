from app.clients.redis_client import cache_stats, get_or_set, invalidate


def test_cache_aside_hits_on_second_call(unique_id):
    key = f"test:cache:{unique_id}"
    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return {"value": 42}

    first = get_or_set(key, loader, ttl=5)
    second = get_or_set(key, loader, ttl=5)

    assert first == {"value": 42}
    assert second == {"value": 42}
    assert calls["count"] == 1  # loader only invoked once; second call was a cache hit


def test_cache_invalidate_forces_reload(unique_id):
    key = f"test:cache:{unique_id}"
    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return {"value": calls["count"]}

    get_or_set(key, loader, ttl=5)
    invalidate(key)
    result = get_or_set(key, loader, ttl=5)

    assert calls["count"] == 2
    assert result == {"value": 2}


def test_cache_stats_tracks_hits_and_misses():
    stats_before = cache_stats()
    assert "hit_rate" in stats_before
    assert 0.0 <= stats_before["hit_rate"] <= 1.0
