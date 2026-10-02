import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from agent.config import MONITORING_INTERVAL_SECONDS
from backend.app.services.metrics_service import MetricsStorageError, save_metric


def collect_metrics():
    """Collect current system metrics from the machine running this agent."""
    network = psutil.net_io_counters()
    if network is None:
        raise RuntimeError("Network counters are unavailable.")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage(Path.home().anchor).percent,
        "network_bytes_sent": network.bytes_sent,
        "network_bytes_received": network.bytes_recv,
    }


def main():
    print(
        f"Monitoring started. Sampling every {MONITORING_INTERVAL_SECONDS:g} seconds. "
        "Press Ctrl+C to stop."
    )

    try:
        while True:
            cycle_started = time.monotonic()
            try:
                metrics = collect_metrics()
            except Exception as error:
                print(
                    f"Metric collection failed ({type(error).__name__}): {error}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(json.dumps(metrics, indent=2), flush=True)
                try:
                    save_metric(metrics)
                except MetricsStorageError as error:
                    print(f"MongoDB storage error: {error}", file=sys.stderr, flush=True)
                else:
                    print("Metric stored in MongoDB.", flush=True)

            elapsed = time.monotonic() - cycle_started
            time.sleep(max(0, MONITORING_INTERVAL_SECONDS - elapsed))
    except KeyboardInterrupt:
        print("\nMonitoring stopped.", flush=True)


if __name__ == "__main__":
    main()