import unittest
from datetime import datetime

from agent.collector import collect_metrics


class CollectMetricsTests(unittest.TestCase):
    def test_metrics_include_required_fields(self):
        metrics = collect_metrics()

        self.assertIn("timestamp", metrics)
        self.assertIsInstance(metrics["timestamp"], str)
        datetime.fromisoformat(metrics["timestamp"])

        self.assertIn("hostname", metrics)
        self.assertTrue(metrics["hostname"])

        for field in (
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "network_bytes_sent",
            "network_bytes_received",
        ):
            with self.subTest(field=field):
                self.assertIn(field, metrics)
                self.assertIsInstance(metrics[field], (int, float))


if __name__ == "__main__":
    unittest.main()