import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export function formatBytes(value) {
  if (!Number.isFinite(value)) return '—';
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let amount = value;
  let unitIndex = -1;
  do {
    amount /= 1024;
    unitIndex += 1;
  } while (amount >= 1024 && unitIndex < units.length - 1);
  return `${amount.toFixed(1)} ${units[unitIndex]}`;
}

export default function NetworkChart({ data }) {
  return (
    <section className="chart-panel" aria-label="Network Activity">
      <div className="chart-panel__heading">
        <h2>Network Activity</h2>
        <div className="chart-legend" aria-label="Chart legend">
          <span><i className="chart-legend__swatch chart-legend__swatch--sent" />Sent</span>
          <span><i className="chart-legend__swatch chart-legend__swatch--received" />Received</span>
        </div>
      </div>
      {data.length === 0 ? (
        <div className="chart-empty">Waiting for metric history</div>
      ) : (
        <div className="chart-canvas">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke="#e5eae5" strokeDasharray="3 5" vertical={false} />
              <XAxis
                dataKey="time"
                tickLine={false}
                axisLine={false}
                minTickGap={28}
                tick={{ fill: '#77827a', fontSize: 11 }}
              />
              <YAxis
                tickFormatter={(value) => formatBytes(value)}
                tickLine={false}
                axisLine={false}
                width={54}
                tick={{ fill: '#77827a', fontSize: 11 }}
              />
              <Tooltip
                labelFormatter={(_label, payload) => payload?.[0]?.payload?.fullTime || ''}
                formatter={(value, name) => [formatBytes(value), name]}
                contentStyle={{ border: '1px solid #dce3dc', borderRadius: 6, fontSize: 12 }}
              />
              <Line
                type="monotone"
                dataKey="network_bytes_sent"
                name="Sent"
                stroke="#bd6a39"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="network_bytes_received"
                name="Received"
                stroke="#247d71"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}