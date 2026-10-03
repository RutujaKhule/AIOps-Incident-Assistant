import math
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app.database import mongodb
from backend.app.demo_config import DEMO_SAMPLE_INTERVAL_SECONDS
from backend.app.services import log_service, metrics_service


DEMO_HOSTNAME = "AIOps-Demo-Server"
DEMO_RETENTION = timedelta(hours=24)
DEMO_CYCLE_SECONDS = 30 * 60


class DemoTelemetryService:
    """Generate clearly tagged telemetry for a server-side dashboard demo."""

    def __init__(
        self,
        metrics_writer=metrics_service,
        logs_writer=log_service,
        interval_seconds=5,
        rng=None,
        hostname=DEMO_HOSTNAME,
    ):
        self.metrics_writer = metrics_writer
        self.logs_writer = logs_writer
        self.interval_seconds = interval_seconds
        self.samples_per_demo_cycle = max(
            3,
            round(DEMO_CYCLE_SECONDS / interval_seconds),
        )
        self.rng = rng or random.Random()
        self.hostname = hostname
        self.sample_count = 0
        self.network_bytes_sent = 0
        self.network_bytes_received = 0

    def set_interval_seconds(self, interval_seconds):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero.")
        self.interval_seconds = interval_seconds
        self.samples_per_demo_cycle = max(
            3,
            round(DEMO_CYCLE_SECONDS / interval_seconds),
        )

    def generate_metric(self, now=None):
        """Create a bounded, smoothly varying sample with an occasional CPU spike."""
        current_time = now or datetime.now(timezone.utc)
        sample_index = self.sample_count
        elapsed = sample_index * self.interval_seconds

        cpu_percent = 30 + 8 * math.sin(elapsed / 37) + self.rng.uniform(-2, 2)
        memory_percent = 56 + 3 * math.sin(elapsed / 180) + self.rng.uniform(-0.8, 0.8)
        disk_percent = 62 + 1.5 * math.sin(elapsed / 900) + self.rng.uniform(-0.2, 0.2)
        if sample_index < 3 or sample_index % self.samples_per_demo_cycle < 3:
            cpu_percent = 96 + self.rng.uniform(-1, 1)

        self.network_bytes_sent += self.rng.randint(12_000, 90_000)
        self.network_bytes_received += self.rng.randint(24_000, 180_000)

        return {
            "timestamp": current_time.isoformat(),
            "hostname": self.hostname,
            "cpu_percent": round(min(max(cpu_percent, 0), 100), 1),
            "memory_percent": round(min(max(memory_percent, 0), 100), 1),
            "disk_percent": round(min(max(disk_percent, 0), 100), 1),
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_received": self.network_bytes_received,
            "source": "demo",
        }

    def collect_sample(self, now=None):
        """Persist one sample and any scheduled demo log through existing services."""
        current_time = now or datetime.now(timezone.utc)
        sample_index = self.sample_count
        metric = self.generate_metric(now=current_time)
        self.metrics_writer.save_metric(metric)
        self.sample_count += 1

        self._write_scheduled_log(sample_index, current_time)
        if self.sample_count % self.samples_per_demo_cycle == 0:
            self._prune_old_demo_records(current_time)
        return metric

    def _write_scheduled_log(self, sample_index, timestamp):
        if sample_index == 0:
            level = "INFO"
            message = "Demo server telemetry producer started."
        elif sample_index == 1:
            level = "WARNING"
            message = "Demo application queue depth is elevated."
        elif (
            2 <= sample_index <= 4
            or sample_index % self.samples_per_demo_cycle in {0, 1, 2}
        ):
            level = "ERROR"
            message = "Demo application dependency timed out; retry succeeded."
        elif sample_index % 60 == 0:
            level = "WARNING"
            message = "Demo application response latency briefly increased."
        elif sample_index % 12 == 0:
            level = "INFO"
            message = "Demo application request completed successfully."
        else:
            return

        self.logs_writer.insert_log(
            {
                "log_id": str(uuid4()),
                "timestamp": timestamp.isoformat(),
                "hostname": self.hostname,
                "level": level,
                "source": "demo",
                "message": message,
            }
        )

    @staticmethod
    def _prune_old_demo_records(now):
        cutoff = (now - DEMO_RETENTION).isoformat()
        mongodb.get_metrics_collection().delete_many(
            {"source": "demo", "timestamp": {"$lt": cutoff}}
        )
        mongodb.get_logs_collection().delete_many(
            {"source": "demo", "timestamp": {"$lt": cutoff}}
        )


demo_telemetry_service = DemoTelemetryService(
    interval_seconds=DEMO_SAMPLE_INTERVAL_SECONDS,
)
