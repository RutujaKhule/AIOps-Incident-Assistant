import { API_BASE_URL } from '../config.js';

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { Accept: 'application/json' },
    });
  } catch {
    throw new Error('Unable to connect to monitoring backend.');
  }

  if (!response.ok) {
    let message = `Monitoring backend returned ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export function getHealth() {
  return request('/health');
}

export async function getLatestMetric() {
  try {
    return await request('/api/metrics/latest');
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

export function getMetricHistory({ minutes = 30, limit = 100 } = {}) {
  const query = new URLSearchParams({ minutes: String(minutes), limit: String(limit) });
  return request(`/api/metrics/history?${query.toString()}`);
}

export function getRecentErrors({ limit = 100 } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  return request(`/api/logs/errors?${query.toString()}`);
}

export function getIncidents({ limit = 100 } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  return request(`/api/incidents?${query.toString()}`);
}

export async function getIncidentAnalysis(incidentId) {
  try {
    return await request(`/api/incidents/${encodeURIComponent(incidentId)}/analysis`);
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

export function analyzeIncident(incidentId) {
  return request(`/api/incidents/${encodeURIComponent(incidentId)}/analyze`, {
    method: 'POST',
  });
}