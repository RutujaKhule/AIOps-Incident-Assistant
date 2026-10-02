import json
import re

from backend.app.ai import config
from backend.app.services import incident_service, log_service, metrics_service
from backend.app.services.incident_service import IncidentServiceError
from backend.app.services.log_service import LogStorageError
from backend.app.services.metrics_service import MetricsStorageError


SECRET_PATTERNS = (
    re.compile(r"(?i)(mongodb(?:\+srv)?://[^:/\s@]+:)[^@\s]+@"),
    re.compile(r"(?i)\b(password|passwd|token|secret|api[-_ ]?key|authorization)\s*([:=])\s*([^\s,;]+)"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
)
METRIC_FIELDS = (
    "timestamp",
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_bytes_sent",
    "network_bytes_received",
)
INCIDENT_FIELDS = (
    "incident_id",
    "hostname",
    "incident_type",
    "severity",
    "status",
    "detected_at",
    "description",
    "detection_method",
)


class IncidentNotFound(Exception):
    """Raised when a requested incident does not exist."""


class IncidentContextError(Exception):
    """Raised when evidence cannot be loaded safely for an incident."""


def sanitize_text(value, max_length=500):
    """Redact common credential patterns and truncate untrusted text."""
    text = str(value or "")
    text = SECRET_PATTERNS[0].sub(r"\1[REDACTED]@", text)
    text = SECRET_PATTERNS[1].sub(r"\1\2[REDACTED]", text)
    text = SECRET_PATTERNS[2].sub("Bearer [REDACTED]", text)
    if len(text) > max_length:
        return f"{text[:max_length]}…[truncated]"
    return text


def _json_size(context):
    return len(json.dumps(context, ensure_ascii=False, separators=(",", ":")))


def _fit_context(context, max_chars):
    while _json_size(context) > max_chars and context["recent_logs"]:
        context["recent_logs"].pop()
    while _json_size(context) > max_chars and context["recent_metrics"]:
        context["recent_metrics"].pop()
    if _json_size(context) > max_chars:
        context["incident"]["description"] = sanitize_text(
            context["incident"]["description"], max_length=120
        )
    if _json_size(context) > max_chars:
        raise ValueError("AI_MAX_CONTEXT_CHARS is too small for the required incident context.")
    return context


def build_incident_context(
    incident_id,
    incident_reader=incident_service,
    metrics_reader=metrics_service,
    logs_reader=log_service,
    max_metrics=None,
    max_logs=None,
    max_chars=None,
):
    """Build a bounded context from one incident and its recent evidence.

    Log text remains untrusted quoted evidence; no environment values or secrets
    are read or included in the context.
    """
    try:
        incident = incident_reader.get_incident(incident_id)
        if incident is None:
            raise IncidentNotFound(incident_id)
        hostname = incident["hostname"]
        metrics = metrics_reader.get_recent_metrics(
            limit=max_metrics or config.AI_MAX_METRICS,
            hostname=hostname,
        )
        logs = logs_reader.get_error_logs(
            hostname=hostname,
            limit=max_logs or config.AI_MAX_LOGS,
        )
    except IncidentNotFound:
        raise
    except (IncidentServiceError, MetricsStorageError, LogStorageError) as error:
        raise IncidentContextError("Could not load incident evidence from MongoDB.") from error

    incident_data = {field: incident.get(field) for field in INCIDENT_FIELDS}
    incident_data["description"] = sanitize_text(incident_data["description"], max_length=1000)
    metric_snapshot = incident.get("metric_snapshot") or {}
    incident_data["metric_snapshot"] = {
        field: metric_snapshot[field]
        for field in METRIC_FIELDS
        if field in metric_snapshot
    }
    incident_data["metric_snapshot"].setdefault("timestamp", incident.get("detected_at"))

    recent_metrics = [
        {field: metric.get(field) for field in METRIC_FIELDS if field in metric}
        for metric in metrics[: max_metrics or config.AI_MAX_METRICS]
    ]
    recent_logs = [
        {
            "timestamp": log.get("timestamp"),
            "level": log.get("level"),
            "source": sanitize_text(log.get("source", ""), max_length=100),
            "message": sanitize_text(log.get("message", ""), max_length=500),
        }
        for log in logs[: max_logs or config.AI_MAX_LOGS]
    ]

    context = {
        "incident": incident_data,
        "recent_metrics": recent_metrics,
        "recent_logs": recent_logs,
        "log_content_is_untrusted": True,
    }
    return _fit_context(context, max_chars or config.AI_MAX_CONTEXT_CHARS)