from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.log import Log, LogLevel
from backend.app.services.log_service import LogStorageError, get_error_logs, get_recent_logs


router = APIRouter(prefix="/api/logs", tags=["logs"])


def _database_error():
    return HTTPException(status_code=503, detail="Log database is unavailable.")


@router.get("", response_model=list[Log])
def list_logs(
    level: LogLevel | None = None,
    hostname: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    try:
        return get_recent_logs(level=level, hostname=hostname, limit=limit)
    except LogStorageError as error:
        raise _database_error() from error


@router.get("/errors", response_model=list[Log])
def list_error_logs(
    hostname: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    try:
        return get_error_logs(hostname=hostname, limit=limit)
    except LogStorageError as error:
        raise _database_error() from error