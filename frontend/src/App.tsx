import { useEffect, useState } from "react";
import { api, AnalyticsSummary, QueueStatus, CacheStatus } from "./api";
import { MetricCard } from "./components/MetricCard";
import { DeviceExplorer } from "./components/DeviceExplorer";
import { FailuresPanel } from "./components/FailuresPanel";

const POLL_INTERVAL_MS = 3000;

export default function App() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [cache, setCache] = useState<CacheStatus | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const [s, q, c] = await Promise.all([api.summary(), api.queue(), api.cache()]);
        if (cancelled) return;
        setSummary(s);
        setQueue(q);
        setCache(c);
        setConnectionError(null);
      } catch (err) {
        if (!cancelled) setConnectionError("Unable to reach the Pulse API. Is it running?");
      }
    };

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const queueDepth = queue?.approximate_queue_depth ?? 0;
  const queueTone = queueDepth > 1000 ? "danger" : queueDepth > 200 ? "warning" : "default";

  return (
    <div className="app">
      <header className="app__header">
        <h1>Pulse</h1>
        <p>Distributed real-time event processing &amp; analytics</p>
      </header>

      {connectionError && <div className="banner banner--error">{connectionError}</div>}

      <section className="metrics-grid">
        <MetricCard
          label="Total Events Processed"
          value={summary ? summary.total_events_processed.toLocaleString() : "—"}
        />
        <MetricCard
          label="Events / sec (est.)"
          value={summary ? summary.events_per_second_estimate.toFixed(2) : "—"}
        />
        <MetricCard
          label="Active Devices (1h)"
          value={summary ? summary.active_devices_last_hour.toLocaleString() : "—"}
        />
        <MetricCard
          label="Queue Depth"
          value={queue ? queueDepth.toLocaleString() : "—"}
          sublabel="Approximate SQS backlog"
          tone={queueTone}
        />
        <MetricCard
          label="Cache Hit Rate"
          value={cache ? `${(cache.hit_rate * 100).toFixed(1)}%` : "—"}
          sublabel={cache ? `${cache.hits} hits / ${cache.misses} misses` : undefined}
        />
      </section>

      <DeviceExplorer />
      <FailuresPanel />

      <footer className="app__footer">
        Polling every {POLL_INTERVAL_MS / 1000}s · Backend: {import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}
      </footer>
    </div>
  );
}
