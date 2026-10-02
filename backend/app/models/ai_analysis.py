from typing import Literal

from pydantic import BaseModel


class IncidentAnalysis(BaseModel):
    analysis_id: str
    incident_id: str
    generated_at: str
    provider: str
    summary: str
    evidence: list[str]
    possible_causes: list[str]
    recommended_next_steps: list[str]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    limitations: list[str]