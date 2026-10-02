function readThreshold(name, fallback) {
  const value = Number(import.meta.env[name]);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
}

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '');

export const REFRESH_INTERVAL_MS = 5000;

export const METRIC_THRESHOLDS = {
  cpu: {
    warning: readThreshold('VITE_CPU_WARNING_THRESHOLD', 70),
    critical: readThreshold('VITE_CPU_CRITICAL_THRESHOLD', 90),
  },
  ram: {
    warning: readThreshold('VITE_RAM_WARNING_THRESHOLD', 75),
    critical: readThreshold('VITE_RAM_CRITICAL_THRESHOLD', 90),
  },
  disk: {
    warning: readThreshold('VITE_DISK_WARNING_THRESHOLD', 80),
    critical: readThreshold('VITE_DISK_CRITICAL_THRESHOLD', 95),
  },
};