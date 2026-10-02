from pymongo import DESCENDING

from backend.app.database import mongodb


ANALYSIS_FIELDS = (
    "analysis_id",
    "incident_id",
    "hostname",
    "generated_at",
    "provider",
    "result",
)


class AIAnalysisStorageError(Exception):
    """Raised when incident analysis cannot be read from or written to MongoDB."""


def save_analysis(analysis, collection=None):
    missing_fields = [field for field in ANALYSIS_FIELDS if field not in analysis]
    if missing_fields:
        raise ValueError(f"Analysis is missing required fields: {', '.join(missing_fields)}")
    document = {field: analysis[field] for field in ANALYSIS_FIELDS}

    try:
        target = collection if collection is not None else mongodb.get_ai_analyses_collection()
        target.insert_one(document)
        return document
    except Exception as error:
        raise AIAnalysisStorageError("Could not store incident analysis.") from error


def get_latest_analysis(incident_id, collection=None):
    try:
        target = collection if collection is not None else mongodb.get_ai_analyses_collection()
        document = target.find_one(
            {"incident_id": incident_id},
            sort=[("generated_at", DESCENDING)],
        )
        return document.get("result") if document else None
    except Exception as error:
        raise AIAnalysisStorageError("Could not retrieve incident analysis.") from error