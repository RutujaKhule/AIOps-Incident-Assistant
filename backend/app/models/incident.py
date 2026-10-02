from typing import Literal

from pydantic import BaseModel


IncidentStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
IncidentSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class Incident(BaseModel):
    incident_id: str
    hostname: str
    incident_type: str
    severity: IncidentSeverity
    status: IncidentStatus
    detected_at: str
    description: str
    metric_snapshot: dict[str, float | int]
    detection_method: Literal["THRESHOLD", "ISOLATION_FOREST", "LOG_PATTERN"]