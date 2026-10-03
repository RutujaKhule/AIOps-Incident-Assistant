from pydantic import BaseModel


class Metric(BaseModel):
    timestamp: str
    hostname: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_bytes_sent: int
    network_bytes_received: int
    source: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str