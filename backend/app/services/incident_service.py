from pymongo import DESCENDING, ReturnDocument

from backend.app.database import mongodb


ACTIVE_STATUSES = ("OPEN", "ACKNOWLEDGED")
INCIDENT_FIELDS = (
    "incident_id",
    "hostname",
    "incident_type",
    "severity",
    "status",
    "detected_at",
    "description",
    "metric_snapshot",
    "detection_method",
)


class IncidentServiceError(Exception):
    """Raised when an incident cannot be read from or written to MongoDB."""


class InvalidIncidentTransition(Exception):
    """Raised when an incident status change is not allowed."""


def create_incident(incident, collection=None):
    """Insert an incident unless an active incident of the same kind exists."""
    missing_fields = [field for field in INCIDENT_FIELDS if field not in incident]
    if missing_fields:
        raise ValueError(f"Incident is missing required fields: {', '.join(missing_fields)}")

    document = {field: incident[field] for field in INCIDENT_FIELDS}
    if incident.get("deduplication_key"):
        document["deduplication_key"] = incident["deduplication_key"]
        document["trigger_log_id"] = incident.get("trigger_log_id")
    query = {
        "hostname": document["hostname"],
        "incident_type": document["incident_type"],
        "status": {"$in": ACTIVE_STATUSES},
    }
    query["deduplication_key"] = document.get("deduplication_key", {"$exists": False})
    try:
        target = collection if collection is not None else mongodb.get_incidents_collection()
        existing = target.find_one(query)
        if existing:
            trigger_log_id = document.get("trigger_log_id")
            if trigger_log_id and existing.get("trigger_log_id") != trigger_log_id:
                target.update_one(
                    {"incident_id": existing["incident_id"]},
                    {"$set": {"trigger_log_id": trigger_log_id}},
                )
            return None
        target.insert_one(document)
        return document
    except Exception as error:
        raise IncidentServiceError(f"Could not create incident: {error}") from error


def list_incidents(hostname=None, status=None, severity=None, limit=100, collection=None):
    """Return recent incidents matching the supplied filters."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    query = {}
    if hostname:
        query["hostname"] = hostname
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    try:
        target = collection if collection is not None else mongodb.get_incidents_collection()
        return list(target.find(query).sort("detected_at", DESCENDING).limit(limit))
    except Exception as error:
        raise IncidentServiceError(f"Could not retrieve incidents: {error}") from error


def get_incident(incident_id, collection=None):
    """Find a single incident by its public incident ID."""
    try:
        target = collection if collection is not None else mongodb.get_incidents_collection()
        return target.find_one({"incident_id": incident_id})
    except Exception as error:
        raise IncidentServiceError(f"Could not retrieve incident: {error}") from error


def get_latest_incident_by_deduplication_key(deduplication_key, collection=None):
    """Return the newest incident for a log fingerprint, regardless of status."""
    try:
        target = collection if collection is not None else mongodb.get_incidents_collection()
        return target.find_one(
            {"deduplication_key": deduplication_key},
            sort=[("detected_at", DESCENDING)],
        )
    except Exception as error:
        raise IncidentServiceError(f"Could not retrieve incident: {error}") from error


def update_incident_status(incident_id, new_status, collection=None):
    """Acknowledge or resolve an incident without allowing it to be reopened."""
    if new_status not in {"ACKNOWLEDGED", "RESOLVED"}:
        raise ValueError("new_status must be ACKNOWLEDGED or RESOLVED")

    try:
        target = collection if collection is not None else mongodb.get_incidents_collection()
        current = target.find_one({"incident_id": incident_id})
        if current is None:
            return None
        if current["status"] == new_status:
            return current
        if current["status"] == "RESOLVED":
            raise InvalidIncidentTransition("Resolved incidents cannot be changed.")
        if new_status == "ACKNOWLEDGED" and current["status"] != "OPEN":
            raise InvalidIncidentTransition("Only open incidents can be acknowledged.")

        return target.find_one_and_update(
            {"incident_id": incident_id},
            {"$set": {"status": new_status}},
            return_document=ReturnDocument.AFTER,
        )
    except InvalidIncidentTransition:
        raise
    except Exception as error:
        raise IncidentServiceError(f"Could not update incident: {error}") from error