import os


def _read_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a number.") from error


def _read_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error


CPU_THRESHOLD_PERCENT = _read_float("CPU_THRESHOLD_PERCENT", 90)
RAM_THRESHOLD_PERCENT = _read_float("RAM_THRESHOLD_PERCENT", 90)
DISK_THRESHOLD_PERCENT = _read_float("DISK_THRESHOLD_PERCENT", 90)
THRESHOLD_SEVERITY = os.getenv("THRESHOLD_INCIDENT_SEVERITY", "HIGH").upper()
ISOLATION_FOREST_SEVERITY = os.getenv("ISOLATION_FOREST_SEVERITY", "MEDIUM").upper()
ISOLATION_FOREST_MIN_SAMPLES = _read_int("ISOLATION_FOREST_MIN_SAMPLES", 50)
ISOLATION_FOREST_CONTAMINATION = _read_float("ISOLATION_FOREST_CONTAMINATION", 0.05)
ISOLATION_FOREST_RANDOM_STATE = _read_int("ISOLATION_FOREST_RANDOM_STATE", 42)
ISOLATION_FOREST_ENABLED = os.getenv("ISOLATION_FOREST_ENABLED", "true").lower() in {
    "1", "true", "yes", "on"
}
DETECTION_POLL_INTERVAL_SECONDS = _read_float("DETECTION_POLL_INTERVAL_SECONDS", 5)
LOG_REPEAT_COUNT = _read_int("LOG_REPEAT_COUNT", 3)
LOG_REPEAT_WINDOW_SECONDS = _read_int("LOG_REPEAT_WINDOW_SECONDS", 60)

VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
if THRESHOLD_SEVERITY not in VALID_SEVERITIES:
    raise ValueError("THRESHOLD_INCIDENT_SEVERITY must be LOW, MEDIUM, HIGH, or CRITICAL.")
if ISOLATION_FOREST_SEVERITY not in VALID_SEVERITIES:
    raise ValueError("ISOLATION_FOREST_SEVERITY must be LOW, MEDIUM, HIGH, or CRITICAL.")
if min(CPU_THRESHOLD_PERCENT, RAM_THRESHOLD_PERCENT, DISK_THRESHOLD_PERCENT) < 0:
    raise ValueError("Metric thresholds must be zero or greater.")
if ISOLATION_FOREST_MIN_SAMPLES < 2:
    raise ValueError("ISOLATION_FOREST_MIN_SAMPLES must be at least 2.")
if not 0 < ISOLATION_FOREST_CONTAMINATION <= 0.5:
    raise ValueError("ISOLATION_FOREST_CONTAMINATION must be greater than 0 and at most 0.5.")
if DETECTION_POLL_INTERVAL_SECONDS <= 0:
    raise ValueError("DETECTION_POLL_INTERVAL_SECONDS must be greater than zero.")
if LOG_REPEAT_COUNT < 2:
    raise ValueError("LOG_REPEAT_COUNT must be at least 2.")
if LOG_REPEAT_WINDOW_SECONDS <= 0:
    raise ValueError("LOG_REPEAT_WINDOW_SECONDS must be greater than zero.")