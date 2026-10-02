from datetime import datetime, timedelta, timezone

from pymongo import DESCENDING

from backend.app.database import mongodb


METRIC_FIELDS = (
    "timestamp",
    "hostname",
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_bytes_sent",
    "network_bytes_received",
)


class MetricsStorageError(Exception):
    """Raised when a metric cannot be read from or written to MongoDB."""


def create_metric_document(metrics):
    """Keep only the expected monitoring fields in a stored document."""
    missing_fields = [field for field in METRIC_FIELDS if field not in metrics]
    if missing_fields:
        raise ValueError(f"Metric is missing required fields: {', '.join(missing_fields)}")
    return {field: metrics[field] for field in METRIC_FIELDS}


def save_metric(metrics, collection=None):
    """Save one monitoring sample and return MongoDB's inserted document ID."""
    document = create_metric_document(metrics)
    try:
        target = collection if collection is not None else mongodb.get_metrics_collection()
        result = target.insert_one(document)
        return result.inserted_id
    except Exception as error:
        raise MetricsStorageError(f"Could not store metric in MongoDB: {error}") from error


def get_recent_metrics(limit=100, hostname=None, collection=None):
    """Return the newest metrics, optionally limited to one host."""
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    query = {"hostname": hostname} if hostname else {}
    try:
        target = collection if collection is not None else mongodb.get_metrics_collection()
        return list(target.find(query).sort("timestamp", DESCENDING).limit(limit))
    except Exception as error:
        raise MetricsStorageError(f"Could not retrieve metrics from MongoDB: {error}") from error


def get_latest_metric():
    """Return the newest metric, or None when there are no stored metrics."""
    metrics = get_recent_metrics(limit=1)
    return metrics[0] if metrics else None


def get_metrics_history(minutes=30, hostname=None, limit=100, collection=None):
    """Return recent metrics within a time window, newest first."""
    if minutes <= 0:
        raise ValueError("minutes must be greater than zero")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    query = {"timestamp": {"$gte": cutoff}}
    if hostname:
        query["hostname"] = hostname

    try:
        target = collection if collection is not None else mongodb.get_metrics_collection()
        return list(target.find(query).sort("timestamp", DESCENDING).limit(limit))
    except Exception as error:
        raise MetricsStorageError(f"Could not retrieve metrics from MongoDB: {error}") from error