from datetime import datetime, timezone
from uuid import uuid4

from backend.app.detection import config


THRESHOLDS = {
    "cpu_percent": (config.CPU_THRESHOLD_PERCENT, "HIGH_CPU", "CPU"),
    "memory_percent": (config.RAM_THRESHOLD_PERCENT, "HIGH_RAM", "RAM"),
    "disk_percent": (config.DISK_THRESHOLD_PERCENT, "HIGH_DISK", "Disk"),
}


def detect_threshold_violations(metrics, thresholds=None):
    """Return incidents for current metrics that exceed configured limits."""
    configured_thresholds = thresholds if thresholds is not None else THRESHOLDS
    detected_at = datetime.now(timezone.utc).isoformat()
    incidents = []

    for field, (threshold, incident_type, display_name) in configured_thresholds.items():
        value = metrics.get(field)
        if value is None or value <= threshold:
            continue

        incidents.append(
            {
                "incident_id": str(uuid4()),
                "hostname": metrics["hostname"],
                "incident_type": incident_type,
                "severity": config.THRESHOLD_SEVERITY,
                "status": "OPEN",
                "detected_at": detected_at,
                "description": (
                    f"{display_name} usage ({value:.1f}%) exceeded the configured "
                    f"threshold ({threshold:.1f}%)."
                ),
                "metric_snapshot": {field: value},
                "detection_method": "THRESHOLD",
            }
        )

    return incidents