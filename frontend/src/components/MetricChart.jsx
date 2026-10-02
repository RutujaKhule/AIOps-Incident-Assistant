import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

function formatPercent(value) {
  return `${Number(value).toFixed(1)}%`;
}

export default function MetricChart({ title, data, dataKey, color }) {
  return (
    <section className="chart-panel" aria-label={title}>
      <div className="chart-panel__heading">
        <h2>{title}</h2>
        <span className="chart-panel__unit">Percent</span>
      </div>
      {data.length === 0 ? (
        <div className="chart-empty">Waiting for metric history</div>
      ) : (
        <div className="chart-canvas">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="#e5eae5" strokeDasharray="3 5" vertical={false} />
              <XAxis
                dataKey="time"
                tickLine={false}
                axisLine={false}
                minTickGap={28}
                tick={{ fill: '#77827a', fontSize: 11 }}
              />
              <YAxis
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickFormatter={formatPercent}
                tickLine={false}
                axisLine={false}
                width={48}
                tick={{ fill: '#77827a', fontSize: 11 }}
              />
              <Tooltip
                labelFormatter={(_label, payload) => payload?.[0]?.payload?.fullTime || ''}
                formatter={(value) => [formatPercent(value), title.replace(' Over Time', '')]}
                contentStyle={{ border: '1px solid #dce3dc', borderRadius: 6, fontSize: 12 }}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}