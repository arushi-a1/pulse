import { useEffect, useState } from "react";
import { api, Device, DeviceMetrics, RecentEvent } from "../api";

export function DeviceExplorer() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<DeviceMetrics | null>(null);
  const [events, setEvents] = useState<RecentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => api.devices(20).then(setDevices).catch((e) => setError(String(e)));
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.deviceMetrics(selected).then(setMetrics).catch(() => setMetrics(null));
    api.deviceEvents(selected, 10).then(setEvents).catch(() => setEvents([]));
  }, [selected]);

  return (
    <section className="panel">
      <h2>Devices</h2>
      {error && <p className="error-text">{error}</p>}
      <div className="device-explorer">
        <ul className="device-list">
          {devices.map((d) => (
            <li
              key={d.device_id}
              className={d.device_id === selected ? "device-list__item device-list__item--active" : "device-list__item"}
              onClick={() => setSelected(d.device_id)}
            >
              <span>{d.device_id}</span>
              <span className="device-list__count">{d.event_count} events</span>
            </li>
          ))}
          {devices.length === 0 && <li className="device-list__empty">No devices yet — send some events.</li>}
        </ul>

        <div className="device-detail">
          {selected ? (
            <>
              <h3>{selected}</h3>
              {metrics ? (
                <dl className="device-detail__metrics">
                  <dt>Avg temperature (1h)</dt>
                  <dd>{metrics.avg_temperature ?? "—"}</dd>
                  <dt>Avg battery (1h)</dt>
                  <dd>{metrics.avg_battery ?? "—"}</dd>
                  <dt>Readings (1h)</dt>
                  <dd>{metrics.reading_count}</dd>
                </dl>
              ) : (
                <p>No metrics yet for this device.</p>
              )}

              <h4>Recent events</h4>
              <table className="events-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Temp</th>
                    <th>Battery</th>
                    <th>Received</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.event_id}>
                      <td>{e.event_type}</td>
                      <td>{e.payload.temperature ?? "—"}</td>
                      <td>{e.payload.battery ?? "—"}</td>
                      <td>{new Date(e.received_at).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                  {events.length === 0 && (
                    <tr>
                      <td colSpan={4}>No events recorded yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>Select a device to see its metrics and recent events.</p>
          )}
        </div>
      </div>
    </section>
  );
}
