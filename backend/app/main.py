import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.ai_analysis import router as ai_analysis_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.logs import router as logs_router
from backend.app.api.metrics import router as metrics_router
from backend.app.database.mongodb import check_connection, close_client
from backend.app.detection.config import DETECTION_POLL_INTERVAL_SECONDS
from backend.app.detection.log_detection import log_detection_service
from backend.app.detection.service import detection_service
from backend.app.models.metric import HealthResponse


logger = logging.getLogger(__name__)


async def _run_detection_loop(stop_event):
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(detection_service.process_latest_metric)
        except Exception:
            logger.exception("Incident detection poll failed.")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=DETECTION_POLL_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            pass


async def _run_log_detection_loop(stop_event):
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(log_detection_service.process_recent_logs)
        except Exception:
            logger.exception("Repeated log error detection poll failed.")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=DETECTION_POLL_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = asyncio.Event()
    detection_task = asyncio.create_task(_run_detection_loop(stop_event))
    log_detection_task = asyncio.create_task(_run_log_detection_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await detection_task
        await log_detection_task
        close_client()


app = FastAPI(
    title="AIOps Incident Assistant",
    description="API for system monitoring metrics.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://aiops-incident-assistant-1.onrender.com",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(incidents_router)
app.include_router(logs_router)
app.include_router(ai_analysis_router)


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy", "service": "AIOps Incident Assistant"}


@app.get("/health/ready")
def readiness():
    try:
        check_connection()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Required database is unavailable.") from error
    return {"status": "ready", "service": "AIOps Incident Assistant"}