import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import App from './App.jsx';
import {
  analyzeIncident,
  getHealth,
  getIncidentAnalysis,
  getIncidents,
  getLatestMetric,
  getMetricHistory,
  getRecentErrors,
} from './services/api.js';

vi.mock('./services/api.js', () => ({
  getHealth: vi.fn(),
  getLatestMetric: vi.fn(),
  getMetricHistory: vi.fn(),
  getRecentErrors: vi.fn(),
  getIncidents: vi.fn().mockResolvedValue([]),
  getIncidentAnalysis: vi.fn().mockResolvedValue(null),
  analyzeIncident: vi.fn(),
}));

const sampleMetric = {
  timestamp: '2026-10-02T12:00:00+00:00',
  hostname: 'test-host',
  cpu_percent: 42.5,
  memory_percent: 61.2,
  disk_percent: 86.8,
  network_bytes_sent: 123456,
  network_bytes_received: 654321,
};

const sampleIncident = {
  incident_id: 'incident-1',
  hostname: 'test-host',
  incident_type: 'HIGH_CPU',
  severity: 'HIGH',
  status: 'OPEN',
};

const sampleAnalysis = {
  analysis_id: 'analysis-1',
  incident_id: 'incident-1',
  generated_at: new Date().toISOString(),
  provider: 'mock',
  summary: 'CPU usage is 95.4%; the configured CPU threshold is 90%.',
  evidence: ['Observed CPU usage: 95.4%.'],
  possible_causes: ['A CPU-intensive process may be running.'],
  recommended_next_steps: ['Inspect top CPU-consuming processes.'],
  confidence: 'HIGH',
  limitations: ['Possible causes are hypotheses, not confirmed root causes.'],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('monitoring dashboard', () => {
  it('shows an initial loading state', () => {
    getHealth.mockReturnValue(new Promise(() => {}));

    render(<App />);

    expect(screen.getByText('Fetching live metrics…')).toBeInTheDocument();
  });

  it('renders live API metric data', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockResolvedValue([{
      log_id: 'log-1',
      timestamp: new Date().toISOString(),
      level: 'ERROR',
      source: 'application',
      message: 'Database connection failed',
    }]);

    render(<App />);

    expect(await screen.findByText('Backend Connected')).toBeInTheDocument();
    expect(screen.getByText('test-host')).toBeInTheDocument();
    expect(screen.getByText('42.5')).toBeInTheDocument();
    expect(screen.getByText('61.2')).toBeInTheDocument();
    expect(screen.getByText('86.8')).toBeInTheDocument();
    expect(screen.getByText('Database connection failed')).toBeInTheDocument();
    expect(screen.getByText('Errors in recent window: 1')).toBeInTheDocument();
  });

  it('identifies server-side demo telemetry', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue({
      ...sampleMetric,
      hostname: 'AIOps-Demo-Server',
      source: 'demo',
    });
    getMetricHistory.mockResolvedValue([]);
    getRecentErrors.mockResolvedValue([]);

    render(<App />);

    expect(await screen.findByText('Demo Server Monitoring')).toBeInTheDocument();
    expect(screen.getByText('AIOps-Demo-Server')).toBeInTheDocument();
  });

  it('shows a separate error state when recent logs cannot be loaded', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockRejectedValue(new Error('logs unavailable'));

    render(<App />);

    expect(await screen.findByText('Unable to load recent errors.')).toBeInTheDocument();
    expect(screen.getByText('42.5')).toBeInTheDocument();
  });

  it('shows a recent-log loading state independently of metrics', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockReturnValue(new Promise(() => {}));

    render(<App />);

    expect(await screen.findByText('42.5')).toBeInTheDocument();
    expect(screen.getByText('Loading recent errors…')).toBeInTheDocument();
  });

  it('shows the disconnected state when the backend cannot be reached', async () => {
    getHealth.mockRejectedValue(new Error('offline'));

    render(<App />);

    expect(await screen.findByText('Backend Disconnected')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Unable to connect to monitoring backend.')).toHaveTextContent(
      'Unable to connect to monitoring backend.',
    ));
  });

  it('shows an empty state when the API has no metrics', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(null);
    getMetricHistory.mockResolvedValue([]);
    getRecentErrors.mockResolvedValue([]);

    render(<App />);

    expect(await screen.findByText('No metrics collected yet')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.getByText('No recent application errors.')).toBeInTheDocument();
  });

  it('shows a no-analysis state for the selected incident', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockResolvedValue([]);
    getIncidents.mockResolvedValue([sampleIncident]);
    getIncidentAnalysis.mockResolvedValue(null);

    render(<App />);

    expect(await screen.findByText('No saved analysis for this incident. Select Analyze Incident to generate one.'))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyze Incident' })).toBeEnabled();
  });

  it('runs analysis and renders the full structured response', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockResolvedValue([]);
    getIncidents.mockResolvedValue([sampleIncident]);
    getIncidentAnalysis.mockResolvedValue(null);
    analyzeIncident.mockResolvedValue(sampleAnalysis);

    render(<App />);
    await screen.findByText('No saved analysis for this incident. Select Analyze Incident to generate one.');
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Incident' }));

    expect(await screen.findByText(sampleAnalysis.summary)).toBeInTheDocument();
    expect(screen.getAllByText('Free Local Analyzer')).toHaveLength(2);
    expect(screen.getByText(sampleAnalysis.possible_causes[0])).toBeInTheDocument();
    expect(screen.getByText(sampleAnalysis.recommended_next_steps[0])).toBeInTheDocument();
    expect(screen.getByText(sampleAnalysis.limitations[0])).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
  });

  it('shows analysis loading state while the provider responds', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockResolvedValue([]);
    getIncidents.mockResolvedValue([sampleIncident]);
    getIncidentAnalysis.mockResolvedValue(null);
    analyzeIncident.mockReturnValue(new Promise(() => {}));

    render(<App />);
    await screen.findByText('No saved analysis for this incident. Select Analyze Incident to generate one.');
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Incident' }));

    expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeDisabled();
    expect(screen.getByText('Loading incident analysis…')).toBeInTheDocument();
  });

  it('shows provider errors without disturbing metric data', async () => {
    getHealth.mockResolvedValue({ status: 'healthy' });
    getLatestMetric.mockResolvedValue(sampleMetric);
    getMetricHistory.mockResolvedValue([sampleMetric]);
    getRecentErrors.mockResolvedValue([]);
    getIncidents.mockResolvedValue([sampleIncident]);
    getIncidentAnalysis.mockResolvedValue(null);
    analyzeIncident.mockRejectedValue(new Error('provider unavailable'));

    render(<App />);
    await screen.findByText('No saved analysis for this incident. Select Analyze Incident to generate one.');
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Incident' }));

    expect(await screen.findByText('Incident analysis could not be completed.')).toBeInTheDocument();
    expect(screen.getByText('42.5')).toBeInTheDocument();
  });
});