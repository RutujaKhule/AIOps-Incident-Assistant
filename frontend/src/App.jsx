import { useEffect, useState } from 'react';

import MetricCard from './components/MetricCard.jsx';
import MetricChart from './components/MetricChart.jsx';
import NetworkChart, { formatBytes } from './components/NetworkChart.jsx';
import StatusIndicator from './components/StatusIndicator.jsx';
import { METRIC_THRESHOLDS, REFRESH_INTERVAL_MS } from './config.js';
import {
  analyzeIncident,
  getHealth,
  getIncidentAnalysis,
  getIncidents,
  getLatestMetric,
  getMetricHistory,
  getRecentErrors,
} from './services/api.js';

function getMetricState(value, thresholds) {
  if (!Number.isFinite(value)) return 'neutral';
  if (value >= thresholds.critical) return 'critical';
  if (value >= thresholds.warning) return 'warning';
  return 'normal';
}

function formatTime(timestamp, options = {}) {
  if (!timestamp) return '—';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(undefined, options).format(date);
}

function toChartData(history) {
  return [...history]
    .sort((first, second) => Date.parse(first.timestamp) - Date.parse(second.timestamp))
    .map((metric) => ({
      ...metric,
      time: formatTime(metric.timestamp, { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      fullTime: formatTime(metric.timestamp, { dateStyle: 'medium', timeStyle: 'medium' }),
    }));
}

export default function App() {
  const [connection, setConnection] = useState('checking');
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [recentErrors, setRecentErrors] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState('');
  const [incidentsLoading, setIncidentsLoading] = useState(true);
  const [analysis, setAnalysis] = useState(null);
  const [analysisState, setAnalysisState] = useState('idle');
  const [analysisError, setAnalysisError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(true);
  const [error, setError] = useState('');
  const [logsError, setLogsError] = useState('');

  useEffect(() => {
    let active = true;
    let healthRequestInProgress = false;
    let metricsRequestInProgress = false;
    let logsRequestInProgress = false;
    let incidentsRequestInProgress = false;

    async function refreshMetrics() {
      if (healthRequestInProgress) return;
      healthRequestInProgress = true;

      try {
        await getHealth();
        if (active) setConnection('connected');
      } catch {
        if (active) {
          setConnection('disconnected');
          setError('Unable to connect to monitoring backend.');
          setLogsError('Unable to load recent errors.');
          setIncidents([]);
          setIncidentsLoading(false);
          setAnalysisError('Unable to load incidents.');
        }
        if (active) {
          setLoading(false);
          setLogsLoading(false);
        }
        return;
      } finally {
        healthRequestInProgress = false;
      }

      const refreshRequests = [];
      if (!metricsRequestInProgress) {
        metricsRequestInProgress = true;
        refreshRequests.push(Promise.all([
          getLatestMetric(),
          getMetricHistory({ minutes: 30, limit: 100 }),
        ])
          .then(([nextLatest, nextHistory]) => {
            if (active) {
              setLatest(nextLatest);
              setHistory(nextHistory);
              setLastUpdated(new Date());
              setError('');
            }
          })
          .catch(() => {
            if (active) {
              setError('The backend is connected, but metric data is currently unavailable.');
            }
          })
          .finally(() => {
            metricsRequestInProgress = false;
            if (active) setLoading(false);
          }));
      }

      if (!logsRequestInProgress) {
        logsRequestInProgress = true;
        refreshRequests.push(getRecentErrors({ limit: 100 })
          .then((nextErrors) => {
            if (active) {
              setRecentErrors(nextErrors);
              setLogsError('');
            }
          })
          .catch(() => {
            if (active) setLogsError('Unable to load recent errors.');
          })
          .finally(() => {
            logsRequestInProgress = false;
            if (active) setLogsLoading(false);
          }));
      }

      if (!incidentsRequestInProgress) {
        incidentsRequestInProgress = true;
        refreshRequests.push(getIncidents({ limit: 100 })
          .then((nextIncidents) => {
            if (active) {
              setIncidents(nextIncidents);
              setSelectedIncidentId((currentId) => (
                nextIncidents.some((incident) => incident.incident_id === currentId)
                  ? currentId
                  : nextIncidents[0]?.incident_id || ''
              ));
              setAnalysisError('');
            }
          })
          .catch(() => {
            if (active) setAnalysisError('Unable to load incidents.');
          })
          .finally(() => {
            incidentsRequestInProgress = false;
            if (active) setIncidentsLoading(false);
          }));
      }

      await Promise.all(refreshRequests);
    }

    refreshMetrics();
    const intervalId = window.setInterval(refreshMetrics, REFRESH_INTERVAL_MS);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    let active = true;
    if (!selectedIncidentId) {
      setAnalysis(null);
      setAnalysisState('idle');
      return () => { active = false; };
    }

    setAnalysis(null);
    setAnalysisError('');
    setAnalysisState('loading');
    getIncidentAnalysis(selectedIncidentId)
      .then((latestAnalysis) => {
        if (!active) return;
        setAnalysis(latestAnalysis);
        setAnalysisState(latestAnalysis ? 'success' : 'no-analysis');
      })
      .catch(() => {
        if (!active) return;
        setAnalysisError('Unable to load saved analysis.');
        setAnalysisState('error');
      });

    return () => { active = false; };
  }, [selectedIncidentId]);

  async function handleAnalyzeIncident() {
    if (!selectedIncidentId) return;
    setAnalysis(null);
    setAnalysisError('');
    setAnalysisState('loading');
    try {
      const nextAnalysis = await analyzeIncident(selectedIncidentId);
      setAnalysis(nextAnalysis);
      setAnalysisState('success');
    } catch {
      setAnalysisError('Incident analysis could not be completed.');
      setAnalysisState('error');
    }
  }

  const chartData = toChartData(history);
  const hasNoMetrics = !loading && latest == null && history.length === 0;
  const recentErrorWindow = recentErrors.filter((log) => {
    const timestamp = Date.parse(log.timestamp);
    const age = Date.now() - timestamp;
    return Number.isFinite(timestamp) && age >= 0 && age <= 30 * 60 * 1000;
  });

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span /></div>
          <div>
            <p className="eyebrow">SYSTEM OBSERVABILITY</p>
            <h1>AIOps Incident Assistant</h1>
          </div>
        </div>
        <StatusIndicator status={connection} />
      </header>

      <section className="overview-strip" aria-label="Monitoring overview">
        <div className="overview-item">
          <span className="overview-label">HOSTNAME</span>
          <strong>{latest?.hostname || '—'}</strong>
        </div>
        <div className="overview-item">
          <span className="overview-label">LAST UPDATED</span>
          <strong>{lastUpdated ? formatTime(lastUpdated, { timeStyle: 'medium' }) : 'Waiting for data'}</strong>
        </div>
        <div className="overview-item overview-item--refresh">
          <span className="refresh-indicator" aria-hidden="true" />
          <span>Refreshes every 5 seconds</span>
        </div>
      </section>

      {error && <div className="notice notice--error" role="alert">{error}</div>}
      {loading && !latest && <div className="notice notice--loading" role="status">Fetching live metrics…</div>}
      {hasNoMetrics && (
        <div className="notice notice--empty" role="status">
          <strong>No metrics collected yet</strong>
          <span>Start the monitoring agent to populate this dashboard.</span>
        </div>
      )}

      <section className="metric-grid" aria-label="Current system metrics">
        <MetricCard
          title="CPU Usage"
          mark="CPU"
          value={latest?.cpu_percent != null ? latest.cpu_percent.toFixed(1) : null}
          unit="%"
          state={getMetricState(latest?.cpu_percent, METRIC_THRESHOLDS.cpu)}
        />
        <MetricCard
          title="RAM Usage"
          mark="RAM"
          value={latest?.memory_percent != null ? latest.memory_percent.toFixed(1) : null}
          unit="%"
          state={getMetricState(latest?.memory_percent, METRIC_THRESHOLDS.ram)}
        />
        <MetricCard
          title="Disk Usage"
          mark="DSK"
          value={latest?.disk_percent != null ? latest.disk_percent.toFixed(1) : null}
          unit="%"
          state={getMetricState(latest?.disk_percent, METRIC_THRESHOLDS.disk)}
        />
        <MetricCard title="Network Activity" mark="NET" state="neutral">
          <div className="network-readings">
            <div><span>Sent</span><strong>{latest ? formatBytes(latest.network_bytes_sent) : '—'}</strong></div>
            <div><span>Received</span><strong>{latest ? formatBytes(latest.network_bytes_received) : '—'}</strong></div>
          </div>
        </MetricCard>
      </section>

      <section className="history-section" aria-labelledby="history-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">RECENT TELEMETRY</p>
            <h2 id="history-title">Metric history</h2>
          </div>
          <span className="history-window">Last 30 minutes · up to 100 samples</span>
        </div>
        <div className="chart-grid">
          <MetricChart title="CPU Usage Over Time" data={chartData} dataKey="cpu_percent" color="#247d71" />
          <MetricChart title="RAM Usage Over Time" data={chartData} dataKey="memory_percent" color="#527f9c" />
          <MetricChart title="Disk Usage Over Time" data={chartData} dataKey="disk_percent" color="#bd6a39" />
          <NetworkChart data={chartData} />
        </div>
      </section>

      <section className="recent-errors-section" aria-labelledby="recent-errors-title">
        <div className="section-heading recent-errors-heading">
          <div>
            <p className="eyebrow">APPLICATION LOGS</p>
            <h2 id="recent-errors-title">Recent Errors</h2>
          </div>
          <span className="history-window">
            Errors in recent window: {logsError ? '—' : logsLoading ? '…' : recentErrorWindow.length}
          </span>
        </div>
        {logsLoading ? (
          <div className="log-state" role="status">Loading recent errors…</div>
        ) : logsError ? (
          <div className="log-state log-state--error" role="alert">{logsError}</div>
        ) : recentErrorWindow.length === 0 ? (
          <div className="log-state" role="status">No recent application errors.</div>
        ) : (
          <div className="recent-error-list">
            {recentErrorWindow.map((log) => (
              <article className="recent-error-row" key={log.log_id}>
                <time dateTime={log.timestamp}>
                  {formatTime(log.timestamp, { dateStyle: 'short', timeStyle: 'medium' })}
                </time>
                <span className={`log-level log-level--${log.level.toLowerCase()}`}>{log.level}</span>
                <strong className="recent-error-source">{log.source}</strong>
                <p>{log.message}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="incident-analysis-section" aria-labelledby="incident-analysis-title">
        <div className="section-heading incident-analysis-heading">
          <div>
            <p className="eyebrow">ADVISORY ONLY</p>
            <h2 id="incident-analysis-title">AI Incident Analysis</h2>
          </div>
          {analysis?.provider === 'mock' && (
            <span className="analysis-provider">Free Local Analyzer</span>
          )}
        </div>
        <div className="analysis-controls">
          <label htmlFor="incident-analysis-select">Incident</label>
          <select
            id="incident-analysis-select"
            value={selectedIncidentId}
            onChange={(event) => setSelectedIncidentId(event.target.value)}
            disabled={incidentsLoading || incidents.length === 0}
          >
            {incidents.length === 0 ? (
              <option value="">{incidentsLoading ? 'Loading incidents…' : 'No incidents available'}</option>
            ) : incidents.map((incident) => (
              <option key={incident.incident_id} value={incident.incident_id}>
                {incident.hostname} · {incident.incident_type} · {incident.severity} · {incident.status}
              </option>
            ))}
          </select>
          <button
            className="analyze-button"
            type="button"
            disabled={!selectedIncidentId || analysisState === 'loading'}
            onClick={handleAnalyzeIncident}
          >
            {analysisState === 'loading' ? 'Analyzing…' : 'Analyze Incident'}
          </button>
        </div>
        {analysisError && <div className="analysis-state analysis-state--error" role="alert">{analysisError}</div>}
        {analysisState === 'loading' && <div className="analysis-state" role="status">Loading incident analysis…</div>}
        {analysisState === 'idle' && !incidentsLoading && incidents.length === 0 && (
          <div className="analysis-state" role="status">No incidents available to analyze.</div>
        )}
        {analysisState === 'no-analysis' && (
          <div className="analysis-state" role="status">No saved analysis for this incident. Select Analyze Incident to generate one.</div>
        )}
        {analysisState === 'success' && analysis && (
          <div className="analysis-result" aria-label="Incident analysis result">
            <div className="analysis-summary">
              <div><span>Summary</span><p>{analysis.summary}</p></div>
              <div className="analysis-meta">
                <span>Confidence <strong>{analysis.confidence}</strong></span>
                <span>Provider <strong>{analysis.provider === 'mock' ? 'Free Local Analyzer' : analysis.provider}</strong></span>
              </div>
            </div>
            <div className="analysis-detail-grid">
              <AnalysisList title="Evidence" items={analysis.evidence} />
              <AnalysisList title="Possible Causes" items={analysis.possible_causes} />
              <AnalysisList title="Recommended Next Steps" items={analysis.recommended_next_steps} />
              <AnalysisList title="Limitations" items={analysis.limitations} />
            </div>
          </div>
        )}
      </section>

      <footer className="dashboard-footer">
        <span>DATA SOURCE <strong>FastAPI · MongoDB</strong></span>
        <span>{loading ? 'Refreshing…' : lastUpdated ? `Updated ${formatTime(lastUpdated, { timeStyle: 'short' })}` : 'No update received'}</span>
      </footer>
    </main>
  );
}

function AnalysisList({ title, items }) {
  return (
    <div className="analysis-list">
      <h3>{title}</h3>
      {items?.length ? (
        <ul>{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ul>
      ) : (
        <p className="analysis-muted">No additional items.</p>
      )}
    </div>
  );
}