from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from backend.app.ai.analyzer import (
    AIAnalysisError,
    IncidentContextError,
    IncidentNotFound,
    LatestAnalysisNotFound,
    analyze_incident,
    get_incident_analysis,
)
from backend.app.models.ai_analysis import IncidentAnalysis
from backend.app.services.ai_analysis_service import AIAnalysisStorageError


router = APIRouter(prefix="/api/incidents", tags=["incident analysis"])


def _database_error():
    return HTTPException(status_code=503, detail="Incident analysis storage is unavailable.")


@router.post("/{incident_id}/analyze", response_model=IncidentAnalysis)
def analyze_incident_endpoint(
    incident_id: Annotated[str, Path(min_length=1, max_length=128)],
):
    try:
        return analyze_incident(incident_id)
    except IncidentNotFound as error:
        raise HTTPException(status_code=404, detail="Incident not found.") from error
    except (IncidentContextError, AIAnalysisStorageError) as error:
        raise _database_error() from error
    except AIAnalysisError as error:
        raise HTTPException(status_code=503, detail="Incident analysis is unavailable.") from error


@router.get("/{incident_id}/analysis", response_model=IncidentAnalysis)
def latest_analysis_endpoint(
    incident_id: Annotated[str, Path(min_length=1, max_length=128)],
):
    try:
        return get_incident_analysis(incident_id)
    except IncidentNotFound as error:
        raise HTTPException(status_code=404, detail="Incident not found.") from error
    except LatestAnalysisNotFound as error:
        raise HTTPException(status_code=404, detail="No analysis exists for this incident.") from error
    except AIAnalysisStorageError as error:
        raise _database_error() from error