import os


DEFAULT_MONITORING_INTERVAL_SECONDS = 5

try:
    MONITORING_INTERVAL_SECONDS = float(
        os.getenv(
            "MONITORING_INTERVAL_SECONDS",
            str(DEFAULT_MONITORING_INTERVAL_SECONDS),
        )
    )
except ValueError as error:
    raise ValueError("MONITORING_INTERVAL_SECONDS must be a number.") from error

if MONITORING_INTERVAL_SECONDS <= 0:
    raise ValueError("MONITORING_INTERVAL_SECONDS must be greater than zero.")