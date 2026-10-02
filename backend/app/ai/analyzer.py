from datetime import datetime, timezone
from uuid import uuid4

from backend.app.ai import config
from backend.app.ai.context_builder import (
    IncidentContextError,
    IncidentNotFound,
    build_incident_context,
)
from backend.app.ai.providers.mock_provider import mock_provider
from backend.app.services import ai_analysis_service, incident_service
from backend.app.services.ai_analysis_service import AIAnalysisStorageError
from backend.app.services.incident_service import IncidentServiceError


class AIAnalysisError(Exception):
    """Raised when configured incident analysis cannot be completed."""


class LatestAnalysisNotFound(Exception):
    """Raised when no saved analysis exists for an incident."""


PROVIDERS = {"mock": mock_provider}


def analyze_incident(incident_id, provider_map=None):
    providers = provider_map or PROVIDERS
    provider = providers.get(config.AI_PROVIDER)
    if provider is None:
        raise AIAnalysisError("Configured incident analysis provider is unavailable.")

    context = build_incident_context(incident_id)
    try:
        result = provider.analyze(context)
    except Exception as error:
        raise AIAnalysisError("Incident analysis provider failed.") from error

    generated_at = datetime.now(timezone.utc).isoformat()
    analysis = {
        "analysis_id": str(uuid4()),
        "incident_id": incident_id,
        "hostname": context["incident"]["hostname"],
        "generated_at": generated_at,
        "provider": provider.name,
        **result,
    }
    try:
        ai_analysis_service.save_analysis(
            {
                "analysis_id": analysis["analysis_id"],
                "incident_id": incident_id,
                "hostname": context["incident"]["hostname"],
                "generated_at": generated_at,
                "provider": provider.name,
                "result": analysis,
            }
        )
    except AIAnalysisStorageError:
        raise
    return analysis


def get_incident_analysis(incident_id):
    try:
        incident = incident_service.get_incident(incident_id)
    except IncidentServiceError as error:
        raise AIAnalysisStorageError("Could not verify incident for analysis retrieval.") from error
    if incident is None:
        raise IncidentNotFound(incident_id)

    try:
        analysis = ai_analysis_service.get_latest_analysis(incident_id)
    except AIAnalysisStorageError:
        raise
    if analysis is None:
        raise LatestAnalysisNotFound(incident_id)
    return analysis


__all__ = [
    "AIAnalysisError",
    "IncidentContextError",
    "IncidentNotFound",
    "LatestAnalysisNotFound",
    "analyze_incident",
    "get_incident_analysis",
]