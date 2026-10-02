from fastapi import APIRouter, HTTPException, Query

from backend.app.models.metric import Metric
from backend.app.services.metrics_service import (
    MetricsStorageError,
    get_latest_metric,
    get_metrics_history,
)


router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/latest", response_model=Metric)
def latest_metric():
    try:
        metric = get_latest_metric()
    except MetricsStorageError as error:
        raise HTTPException(
            status_code=503,
            detail="Metrics database is unavailable.",
        ) from error

    if metric is None:
        raise HTTPException(status_code=404, detail="No metrics found.")
    return metric


@router.get("/history", response_model=list[Metric])
def metrics_history(
    minutes: int = Query(default=30, gt=0, le=10080),
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=100, ge=1, le=1000),
):
    try:
        return get_metrics_history(minutes=minutes, hostname=hostname, limit=limit)
    except MetricsStorageError as error:
        raise HTTPException(
            status_code=503,
            detail="Metrics database is unavailable.",
        ) from error