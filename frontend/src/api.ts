const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface AnalyticsSummary {
  total_events_processed: number;
  active_devices_last_hour: number;
  events_per_second_estimate: number;
  cache_hit_rate: number;
}

export interface QueueStatus {
  approximate_queue_depth: number;
}

export interface CacheStatus {
  hits: number;
  misses: number;
  hit_rate: number;
}

export interface Device {
  device_id: string;
  first_seen: string;
  last_seen: string;
  event_count: number;
}

export interface DeviceMetrics {
  device_id: string;
  avg_temperature: number | null;
  avg_battery: number | null;
  reading_count: number;
  window: string;
}

export interface ProcessingFailure {
  event_id: string;
  error: string;
  attempt: number;
  created_at: string;
}

export interface RecentEvent {
  event_id: string;
  event_type: string;
  payload: Record<string, number>;
  received_at: string;
  processed_at: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`);
  if (!resp.ok) {
    throw new Error(`${path} failed with status ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  summary: () => getJson<AnalyticsSummary>("/analytics/summary"),
  queue: () => getJson<QueueStatus>("/analytics/queue"),
  cache: () => getJson<CacheStatus>("/analytics/cache"),
  devices: (limit = 50) => getJson<Device[]>(`/devices?limit=${limit}`),
  deviceMetrics: (deviceId: string) => getJson<DeviceMetrics>(`/devices/${deviceId}/metrics`),
  deviceEvents: (deviceId: string, limit = 10) =>
    getJson<RecentEvent[]>(`/devices/${deviceId}/events?limit=${limit}`),
  failures: (limit = 20) => getJson<ProcessingFailure[]>(`/analytics/failures?limit=${limit}`),
};
