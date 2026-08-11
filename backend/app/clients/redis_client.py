import json
import logging
from collections.abc import Callable
from typing import Any

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
client = redis.Redis(connection_pool=_pool)

# In-process counters exposed via /metrics. In prod these are also emitted as
# CloudWatch custom metrics (see app.metrics_emitter) so we can chart cache
# hit rate over time instead of just at-a-point-in-time.
_stats = {"hits": 0, "misses": 0}


def cache_stats() -> dict[str, float]:
    total = _stats["hits"] + _stats["misses"]
    hit_rate = (_stats["hits"] / total) if total else 0.0
    return {"hits": _stats["hits"], "misses": _stats["misses"], "hit_rate": round(hit_rate, 4)}


def get_or_set(key: str, loader: Callable[[], Any], ttl: int | None = None) -> Any:
    """Cache-aside: try Redis first, fall back to `loader()` on miss, then
    populate the cache. A Redis outage degrades to always-miss rather than
    failing the request (see graceful degradation in the reliability docs)."""
    ttl = ttl or settings.cache_ttl_seconds
    try:
        cached = client.get(key)
        if cached is not None:
            _stats["hits"] += 1
            return json.loads(cached)
    except redis.RedisError as exc:
        logger.warning("redis_get_failed", extra={"error": str(exc), "key": key})

    _stats["misses"] += 1
    value = loader()
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except redis.RedisError as exc:
        logger.warning("redis_set_failed", extra={"error": str(exc), "key": key})
    return value


def invalidate(key: str) -> None:
    try:
        client.delete(key)
    except redis.RedisError as exc:
        logger.warning("redis_invalidate_failed", extra={"error": str(exc), "key": key})


def invalidate_prefix(prefix: str) -> None:
    try:
        for k in client.scan_iter(f"{prefix}*"):
            client.delete(k)
    except redis.RedisError as exc:
        logger.warning("redis_invalidate_prefix_failed", extra={"error": str(exc), "prefix": prefix})
