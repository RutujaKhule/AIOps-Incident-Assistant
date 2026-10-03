import math
import os


def _read_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean.")


def _read_positive_float(name, default):
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a number.") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def read_demo_mode():
    """Read demo mode when the application lifespan starts."""
    return _read_bool("DEMO_MODE")


def read_demo_sample_interval_seconds():
    """Read the telemetry interval when the application lifespan starts."""
    return _read_positive_float("DEMO_SAMPLE_INTERVAL_SECONDS", 5)


DEMO_MODE = read_demo_mode()
DEMO_SAMPLE_INTERVAL_SECONDS = read_demo_sample_interval_seconds()
