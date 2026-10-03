from datetime import datetime, timezone
from uuid import uuid4

from backend.app.detection import config, isolation_forest
from backend.app.detection.threshold_detection import detect_threshold_violations
from backend.app.services import incident_service, metrics_service


class DetectionService:
    """Coordinate metric reads, detection rules, and incident creation."""

    def __init__(
        self,
        metrics_reader=metrics_service,
        incident_writer=incident_service,
        isolation_forest_enabled=None,
        minimum_samples=None,
        contamination=None,
        random_state=None,
    ):
        self.metrics_reader = metrics_reader
        self.incident_writer = incident_writer
        self.isolation_forest_enabled = (
            config.ISOLATION_FOREST_ENABLED
            if isolation_forest_enabled is None
            else isolation_forest_enabled
        )
        self.minimum_samples = minimum_samples or config.ISOLATION_FOREST_MIN_SAMPLES
        self.contamination = contamination or config.ISOLATION_FOREST_CONTAMINATION
        self.random_state = random_state if random_state is not None else config.ISOLATION_FOREST_RANDOM_STATE
        self._last_processed_key = None

    def process_latest_metric(self):
        """Process the newest unprocessed metric and return created incidents."""
        latest = self.metrics_reader.get_latest_metric()
        if latest is None:
            return []

        sample_key = self._sample_key(latest)
        if sample_key == self._last_processed_key:
            return []

        history = self.metrics_reader.get_recent_metrics(
            limit=max(100, self.minimum_samples + 1),
            hostname=latest["hostname"],
        )
        if not any(self._sample_key(sample) == sample_key for sample in history):
            history.append(latest)

        candidates = detect_threshold_violations(latest)
        if latest.get("source"):
            for candidate in candidates:
                candidate["source"] = latest["source"]
        if self.isolation_forest_enabled and isolation_forest.is_anomalous(
            history,
            minimum_samples=self.minimum_samples,
            contamination=self.contamination,
            random_state=self.random_state,
        ):
            candidates.append(
                {
                    "incident_id": str(uuid4()),
                    "hostname": latest["hostname"],
                    "incident_type": "ISOLATION_FOREST_ANOMALY",
                    "severity": config.ISOLATION_FOREST_SEVERITY,
                    "status": "OPEN",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "description": (
                        "Metric combination was unusual relative to recent history; "
                        "this is not a confirmed root cause."
                    ),
                    "metric_snapshot": {
                        field: latest[field] for field in isolation_forest.FEATURES
                    },
                    "detection_method": "ISOLATION_FOREST",
                }
            )
            if latest.get("source"):
                candidates[-1]["source"] = latest["source"]

        created = []
        for candidate in candidates:
            incident = self.incident_writer.create_incident(candidate)
            if incident is not None:
                created.append(incident)

        self._last_processed_key = sample_key
        return created

    @staticmethod
    def _sample_key(metric):
        metric_id = metric.get("_id")
        if metric_id is not None:
            return str(metric_id)
        return f"{metric.get('hostname', '')}:{metric.get('timestamp', '')}"


detection_service = DetectionService()