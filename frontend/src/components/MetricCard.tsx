interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
  tone?: "default" | "warning" | "danger";
}

export function MetricCard({ label, value, sublabel, tone = "default" }: MetricCardProps) {
  return (
    <div className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__label">{label}</div>
      <div className="metric-card__value">{value}</div>
      {sublabel && <div className="metric-card__sublabel">{sublabel}</div>}
    </div>
  );
}
