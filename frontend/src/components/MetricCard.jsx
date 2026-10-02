const STATE_LABELS = {
  normal: 'Normal',
  warning: 'Warning',
  critical: 'Critical',
  neutral: 'Live counters',
};

export default function MetricCard({ title, mark, value, unit, state = 'neutral', children }) {
  return (
    <article className={`metric-card metric-card--${state}`}>
      <div className="metric-card__heading">
        <span className="metric-card__mark" aria-hidden="true">{mark}</span>
        <h2>{title}</h2>
        <span className={`state-label state-label--${state}`}>{STATE_LABELS[state]}</span>
      </div>
      {children || (
        <p className="metric-card__value">
          {value == null ? '—' : value}
          {value != null && unit && <span className="metric-card__unit">{unit}</span>}
        </p>
      )}
    </article>
  );
}