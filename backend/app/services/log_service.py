from uuid import uuid4

from pymongo import DESCENDING

from backend.app.database import mongodb


LOG_FIELDS = ("log_id", "timestamp", "hostname", "level", "source", "message")
VALID_LEVELS = {"INFO", "WARNING", "ERROR", "CRITICAL"}


class LogStorageError(Exception):
    """Raised when a log cannot be read from or written to MongoDB."""


def _validate_limit(limit):
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")


def insert_log(log, collection=None):
    """Insert one structured log entry and return its document."""
    missing_fields = [field for field in LOG_FIELDS if field not in log]
    if missing_fields:
        raise ValueError(f"Log is missing required fields: {', '.join(missing_fields)}")
    if log["level"] not in VALID_LEVELS:
        raise ValueError("level must be INFO, WARNING, ERROR, or CRITICAL")

    document = {field: log[field] for field in LOG_FIELDS}
    if not document["log_id"]:
        document["log_id"] = str(uuid4())

    try:
        target = collection if collection is not None else mongodb.get_logs_collection()
        target.insert_one(document)
        return document
    except Exception as error:
        raise LogStorageError(f"Could not store log entry: {error}") from error


def get_recent_logs(level=None, hostname=None, limit=100, collection=None):
    """Return newest logs with optional level and hostname filters."""
    _validate_limit(limit)
    if level is not None and level not in VALID_LEVELS:
        raise ValueError("level must be INFO, WARNING, ERROR, or CRITICAL")

    query = {}
    if level:
        query["level"] = level
    if hostname:
        query["hostname"] = hostname

    try:
        target = collection if collection is not None else mongodb.get_logs_collection()
        return list(target.find(query).sort("timestamp", DESCENDING).limit(limit))
    except Exception as error:
        raise LogStorageError(f"Could not retrieve log entries: {error}") from error


def get_error_logs(hostname=None, limit=100, collection=None):
    """Return newest ERROR and CRITICAL logs."""
    _validate_limit(limit)
    query = {"level": {"$in": ["ERROR", "CRITICAL"]}}
    if hostname:
        query["hostname"] = hostname

    try:
        target = collection if collection is not None else mongodb.get_logs_collection()
        return list(target.find(query).sort("timestamp", DESCENDING).limit(limit))
    except Exception as error:
        raise LogStorageError(f"Could not retrieve error logs: {error}") from error