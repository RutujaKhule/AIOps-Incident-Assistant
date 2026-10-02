from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from backend.app.detection import config
from backend.app.services import incident_service, log_service


def normalize_message(message):
    """Collapse whitespace without merging messages that differ in wording."""
    return " ".join(message.split())


def detect_repeated_log_errors(
    logs,
    repeat_count=config.LOG_REPEAT_COUNT,
    window_seconds=config.LOG_REPEAT_WINDOW_SECONDS,
    now=None,
):
    """Return one incident candidate per repeated host/source/message group."""
    if repeat_count < 2:
        raise ValueError("repeat_count must be at least 2")
    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than zero")

    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(seconds=window_seconds)
    groups = {}

    for log in logs:
        if log.get("level") not in {"ERROR", "CRITICAL"}:
            continue
        try:
            timestamp = datetime.fromisoformat(log["timestamp"])
        except (KeyError, TypeError, ValueError):
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if timestamp < cutoff or timestamp > current_time:
            continue

        normalized = normalize_message(log.get("message", ""))
        if not normalized:
            continue
        key = (log.get("hostname", ""), log.get("source", ""), normalized)
        groups.setdefault(key, []).append((timestamp, log))

    incidents = []
    for (hostname, source, normalized), entries in groups.items():
        entries.sort(key=lambda entry: entry[0])
        newest_timestamp, newest_log = entries[-1]
        matching_entries = [
            entry for entry in entries
            if newest_timestamp - entry[0] <= timedelta(seconds=window_seconds)
        ]
        if len(matching_entries) < repeat_count:
            continue

        critical_repeated = any(log["level"] == "CRITICAL" for _, log in matching_entries)
        severity = "HIGH" if critical_repeated else "MEDIUM"
        repeat_total = len(matching_entries)
        original_message = newest_log["message"].strip()
        deduplication_key = sha256(
            f"{hostname}\0{source}\0{normalized}".encode("utf-8")
        ).hexdigest()

        incidents.append(
            {
                "incident_id": str(uuid4()),
                "hostname": hostname,
                "incident_type": "REPEATED_LOG_ERROR",
                "severity": severity,
                "status": "OPEN",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "description": (
                    f"{newest_log['level']} log message '{original_message}' from {source} "
                    f"occurred {repeat_total} times within {window_seconds} seconds."
                ),
                "metric_snapshot": {},
                "detection_method": "LOG_PATTERN",
                "deduplication_key": deduplication_key,
                "_trigger_log_id": newest_log.get("log_id", newest_timestamp.isoformat()),
            }
        )

    return incidents


class LogDetectionService:
    """Poll stored logs and create deduplicated repeated-error incidents."""

    def __init__(self, log_reader=log_service, incident_writer=incident_service):
        self.log_reader = log_reader
        self.incident_writer = incident_writer
        self._last_trigger_log_ids = {}

    def process_recent_logs(self):
        logs = self.log_reader.get_error_logs(limit=1000)
        candidates = detect_repeated_log_errors(logs)
        created = []

        for candidate in candidates:
            deduplication_key = candidate["deduplication_key"]
            trigger_log_id = candidate.pop("_trigger_log_id")
            if self._last_trigger_log_ids.get(deduplication_key) == trigger_log_id:
                continue

            previous_incident = self.incident_writer.get_latest_incident_by_deduplication_key(
                deduplication_key
            )
            if previous_incident and previous_incident.get("trigger_log_id") == trigger_log_id:
                self._last_trigger_log_ids[deduplication_key] = trigger_log_id
                continue

            candidate["trigger_log_id"] = trigger_log_id

            incident = self.incident_writer.create_incident(candidate)
            self._last_trigger_log_ids[deduplication_key] = trigger_log_id
            if incident is not None:
                created.append(incident)

        return created


log_detection_service = LogDetectionService()