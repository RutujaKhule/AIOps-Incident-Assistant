import os

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError


DEFAULT_DATABASE_NAME = "AIOpsIncidentAssistant"
_mongo_client = None
_metrics_collection = None
_incidents_collection = None
_logs_collection = None
_ai_analyses_collection = None


def get_client():
    """Create the MongoDB client once and reuse it for later calls."""
    global _mongo_client

    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not set; configure it before starting the agent.")

    if _mongo_client is None:
        _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    return _mongo_client


def get_database():
    """Return the configured MongoDB database."""
    database_name = os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE_NAME)
    return get_client()[database_name]


def get_metrics_collection():
    """Return the metrics collection and ensure its query index exists."""
    global _metrics_collection

    if _metrics_collection is None:
        collection = get_database()["metrics"]
        collection.create_index(
            [("hostname", ASCENDING), ("timestamp", DESCENDING)],
            name="hostname_timestamp",
        )
        _metrics_collection = collection
    return _metrics_collection


def get_incidents_collection():
    """Return the incidents collection and ensure its query index exists."""
    global _incidents_collection

    if _incidents_collection is None:
        collection = get_database()["incidents"]
        collection.create_index(
            [
                ("hostname", ASCENDING),
                ("status", ASCENDING),
                ("detected_at", DESCENDING),
            ],
            name="hostname_status_detected_at",
        )
        _incidents_collection = collection
    return _incidents_collection


def get_logs_collection():
    """Return the logs collection and ensure its query indexes exist."""
    global _logs_collection

    if _logs_collection is None:
        collection = get_database()["logs"]
        collection.create_index(
            [("hostname", ASCENDING), ("timestamp", DESCENDING), ("level", ASCENDING)],
            name="hostname_timestamp_level",
        )
        collection.create_index(
            [("level", ASCENDING), ("timestamp", DESCENDING)],
            name="level_timestamp",
        )
        _logs_collection = collection
    return _logs_collection


def get_ai_analyses_collection():
    """Return the analysis collection and ensure its lookup index exists."""
    global _ai_analyses_collection

    if _ai_analyses_collection is None:
        collection = get_database()["ai_analyses"]
        collection.create_index(
            [("incident_id", ASCENDING), ("generated_at", DESCENDING)],
            name="incident_generated_at",
        )
        _ai_analyses_collection = collection
    return _ai_analyses_collection


def check_connection():
    """Ping MongoDB and raise a clear error if the server cannot be reached."""
    try:
        get_client().admin.command("ping")
    except PyMongoError as error:
        raise RuntimeError(f"MongoDB connection failed: {error}") from error


def close_client():
    """Close the shared MongoDB client when an application shuts down."""
    global _mongo_client, _metrics_collection, _incidents_collection, _logs_collection
    global _ai_analyses_collection

    if _mongo_client is not None:
        _mongo_client.close()
    _mongo_client = None
    _metrics_collection = None
    _incidents_collection = None
    _logs_collection = None
    _ai_analyses_collection = None