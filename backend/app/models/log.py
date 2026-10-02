from typing import Literal

from pydantic import BaseModel


LogLevel = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class Log(BaseModel):
    log_id: str
    timestamp: str
    hostname: str
    level: LogLevel
    source: str
    message: str