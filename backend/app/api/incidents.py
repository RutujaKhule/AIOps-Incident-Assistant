from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.incident import Incident, IncidentSeverity, IncidentStatus
from backend.app.services.incident_service import (
    IncidentServiceError,
    InvalidIncidentTransition,
    get_incident,
    list_incidents,
    update_incident_status,
)


router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _database_error():
    return HTTPException(
        status_code=503,
        detail="Incident database is unavailable.",
    )


@router.get("", response_model=list[Incident], response_model_exclude_none=True)
def get_incidents(
    hostname: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    try:
        return list_incidents(hostname=hostname, status=status, severity=severity, limit=limit)
    except IncidentServiceError as error:
        raise _database_error() from error


@router.get("/open", response_model=list[Incident], response_model_exclude_none=True)
def get_open_incidents(
    hostname: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    severity: IncidentSeverity | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    try:
        return list_incidents(
            hostname=hostname,
            status="OPEN",
            severity=severity,
            limit=limit,
        )
    except IncidentServiceError as error:
        raise _database_error() from error


@router.get("/{incident_id}", response_model=Incident, response_model_exclude_none=True)
def get_incident_by_id(incident_id: str):
    try:
        incident = get_incident(incident_id)
    except IncidentServiceError as error:
        raise _database_error() from error
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident


def _change_status(incident_id, new_status):
    try:
        incident = update_incident_status(incident_id, new_status)
    except InvalidIncidentTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IncidentServiceError as error:
        raise _database_error() from error
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident


@router.post(
    "/{incident_id}/acknowledge",
    response_model=Incident,
    response_model_exclude_none=True,
)
def acknowledge_incident(incident_id: str):
    return _change_status(incident_id, "ACKNOWLEDGED")


@router.post(
    "/{incident_id}/resolve",
    response_model=Incident,
    response_model_exclude_none=True,
)
def resolve_incident(incident_id: str):
    return _change_status(incident_id, "RESOLVED")