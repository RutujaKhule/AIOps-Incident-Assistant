from typing import Protocol


class AnalysisProvider(Protocol):
    """Interface for advisory providers that return structured analysis data."""

    name: str

    def analyze(self, context: dict) -> dict:
        """Analyze sanitized incident evidence without performing actions."""
        ...