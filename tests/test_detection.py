import unittest
from unittest.mock import Mock, patch

from backend.app.detection.isolation_forest import FEATURES, is_anomalous
from backend.app.detection.service import DetectionService
from backend.app.detection.threshold_detection import detect_threshold_violations


def metric(**overrides):
    value = {
        "timestamp": "2026-10-02T12:00:00+00:00",
        "hostname": "test-host",
        "cpu_percent": 25.0,
        "memory_percent": 40.0,
        "disk_percent": 50.0,
        "network_bytes_sent": 100000,
        "network_bytes_received": 200000,
    }
    value.update(overrides)
    return value


class ThresholdDetectionTests(unittest.TestCase):
    def test_cpu_below_threshold_creates_no_incident(self):
        self.assertEqual(detect_threshold_violations(metric(cpu_percent=90)), [])

    def test_cpu_above_threshold_creates_high_incident(self):
        incidents = detect_threshold_violations(metric(cpu_percent=95.4))

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["incident_type"], "HIGH_CPU")
        self.assertEqual(incidents[0]["severity"], "HIGH")
        self.assertEqual(incidents[0]["metric_snapshot"], {"cpu_percent": 95.4})
        self.assertEqual(incidents[0]["detection_method"], "THRESHOLD")

    def test_ram_and_disk_thresholds_create_incidents(self):
        incidents = detect_threshold_violations(
            metric(memory_percent=91, disk_percent=92)
        )

        self.assertEqual({item["incident_type"] for item in incidents}, {"HIGH_RAM", "HIGH_DISK"})

    def test_custom_thresholds_are_used(self):
        incidents = detect_threshold_violations(
            metric(cpu_percent=75),
            thresholds={"cpu_percent": (70, "HIGH_CPU", "CPU")},
        )

        self.assertEqual(len(incidents), 1)


class IsolationForestTests(unittest.TestCase):
    def test_insufficient_history_does_not_train_model(self):
        history = [metric() for _ in range(5)]

        self.assertFalse(is_anomalous(history, minimum_samples=5))

    def test_model_runs_with_sufficient_history_and_flags_controlled_outlier(self):
        history = [
            metric(
                timestamp=f"2026-10-02T12:{index // 60:02d}:{index % 60:02d}+00:00",
                cpu_percent=20 + index % 3,
                memory_percent=40 + index % 2,
                disk_percent=50,
                network_bytes_sent=100000 + index * 100,
                network_bytes_received=200000 + index * 120,
            )
            for index in range(60)
        ]
        history.append(
            metric(
                timestamp="2026-10-02T13:01:00+00:00",
                cpu_percent=2,
                memory_percent=99,
                disk_percent=99,
                network_bytes_sent=9000000,
                network_bytes_received=12000000,
            )
        )

        self.assertTrue(is_anomalous(history, minimum_samples=50, random_state=42))
        self.assertEqual(len(FEATURES), 5)


class DetectionServiceTests(unittest.TestCase):
    def test_repeated_sample_is_processed_only_once(self):
        latest = metric(_id="sample-1", cpu_percent=95)
        metrics_reader = Mock()
        metrics_reader.get_latest_metric.return_value = latest
        metrics_reader.get_recent_metrics.return_value = [latest]
        incident_writer = Mock()
        detector = DetectionService(metrics_reader, incident_writer, isolation_forest_enabled=False)

        detector.process_latest_metric()
        detector.process_latest_metric()

        incident_writer.create_incident.assert_called_once()

    @patch("backend.app.detection.service.isolation_forest.is_anomalous", return_value=True)
    def test_isolation_forest_result_creates_anomaly_incident(self, is_anomalous_mock):
        latest = metric(_id="sample-2")
        metrics_reader = Mock()
        metrics_reader.get_latest_metric.return_value = latest
        metrics_reader.get_recent_metrics.return_value = [latest]
        incident_writer = Mock()
        incident_writer.create_incident.side_effect = lambda incident: incident
        detector = DetectionService(
            metrics_reader,
            incident_writer,
            isolation_forest_enabled=True,
            minimum_samples=2,
        )

        incidents = detector.process_latest_metric()

        isolation_incident = next(
            incident for incident in incidents
            if incident["detection_method"] == "ISOLATION_FOREST"
        )
        self.assertEqual(isolation_incident["incident_type"], "ISOLATION_FOREST_ANOMALY")
        self.assertEqual(isolation_incident["severity"], "MEDIUM")
        is_anomalous_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()