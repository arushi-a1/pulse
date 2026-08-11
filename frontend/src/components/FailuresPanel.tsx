import { useEffect, useState } from "react";
import { api, ProcessingFailure } from "../api";

export function FailuresPanel() {
  const [failures, setFailures] = useState<ProcessingFailure[]>([]);

  useEffect(() => {
    const load = () => api.failures(10).then(setFailures).catch(() => setFailures([]));
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="panel">
      <h2>Processing Failures</h2>
      {failures.length === 0 ? (
        <p className="success-text">No processing failures recorded.</p>
      ) : (
        <table className="events-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Attempt</th>
              <th>Error</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {failures.map((f, i) => (
              <tr key={`${f.event_id}-${i}`}>
                <td>{f.event_id.slice(0, 12)}…</td>
                <td>{f.attempt}</td>
                <td>{f.error.slice(0, 60)}</td>
                <td>{new Date(f.created_at).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
