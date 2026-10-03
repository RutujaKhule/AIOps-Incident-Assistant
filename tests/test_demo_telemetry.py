import asyncio
import random
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from backend.app import main
from backend.app.main import _safe_error_message
from backend.app.demo_config import _read_bool, _read_positive_float
from backend.app.demo_telemetry import DEMO_HOSTNAME, DemoTelemetryService
from backend.app.detection.service import DetectionService


class DemoConfigurationTests(unittest.TestCase):
    def test_demo_mode_defaults_to_false_and_parses_boolean_values(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_read_bool("DEMO_MODE"))
        with patch.dict("os.environ", {"DEMO_MODE": " YES "}, clear=True):
            self.assertTrue(_read_bool("DEMO_MODE"))
        with patch.dict("os.environ", {"DEMO_MODE": "off"}, clear=True):
            self.assertFalse(_read_bool("DEMO_MODE"))

    def test_demo_configuration_rejects_invalid_values(self):
        with patch.dict("os.environ", {"DEMO_MODE": "sometimes"}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEMO_MODE"):
                _read_bool("DEMO_MODE")
        with patch.dict("os.environ", {"DEMO_SAMPLE_INTERVAL_SECONDS": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                _read_positive_float("DEMO_SAMPLE_INTERVAL_SECONDS", 5)

    def test_database_error_logging_redacts_mongodb_credentials(self):
        message = _safe_error_message(
            RuntimeError(
                "Could not connect to mongodb+srv://demo-user:secret@cluster.example/"
            )
        )

        self.assertNotIn("demo-user", message)
        self.assertNotIn("secret", message)
        self.assertIn("mongodb+srv://[REDACTED]@cluster.example", message)

    def test_demo_sample_interval_uses_configured_value(self):
        with patch.dict("os.environ", {"DEMO_SAMPLE_INTERVAL_SECONDS": "2.5"}, clear=True):
            self.assertEqual(_read_positive_float("DEMO_SAMPLE_INTERVAL_SECONDS", 5), 2.5)


class DemoTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.metrics_writer = Mock()
        self.logs_writer = Mock()
        self.service = DemoTelemetryService(
            metrics_writer=self.metrics_writer,
            logs_writer=self.logs_writer,
            interval_seconds=5,
            rng=random.Random(7),
        )
        self.start_time = datetime(2026, 10, 3, 8, 0, tzinfo=timezone.utc)

    def test_generates_tagged_and_varying_server_metrics_and_scheduled_logs(self):
        metrics = [
            self.service.collect_sample(
                now=self.start_time.replace(second=self.start_time.second + index * 5)
            )
            for index in range(6)
        ]

        self.assertTrue(all(item["hostname"] == DEMO_HOSTNAME for item in metrics))
        self.assertTrue(all(item["source"] == "demo" for item in metrics))
        self.assertTrue(all(0 <= item["memory_percent"] <= 100 for item in metrics))
        self.assertTrue(all(0 <= item["disk_percent"] <= 100 for item in metrics))
        self.assertGreater(metrics[0]["cpu_percent"], 90)
        self.assertNotEqual(metrics[3]["cpu_percent"], metrics[4]["cpu_percent"])
        self.assertTrue(
            all(
                later["network_bytes_sent"] > earlier["network_bytes_sent"]
                for earlier, later in zip(metrics, metrics[1:])
            )
        )

        logs = [call.args[0] for call in self.logs_writer.insert_log.call_args_list]
        self.assertEqual([log["level"] for log in logs], ["INFO", "WARNING", "ERROR", "ERROR", "ERROR"])
        self.assertTrue(all(log["source"] == "demo" for log in logs))
        self.assertEqual(len({log["message"] for log in logs if log["level"] == "ERROR"}), 1)

    def test_metric_persistence_failure_does_not_claim_a_successful_sample(self):
        self.metrics_writer.save_metric.side_effect = RuntimeError("database offline")

        with self.assertRaisesRegex(RuntimeError, "database offline"):
            self.service.collect_sample(now=self.start_time)

        self.assertEqual(self.service.sample_count, 0)
        self.logs_writer.insert_log.assert_not_called()

    def test_demo_source_is_carried_into_existing_detection_pipeline(self):
        latest = {
            "timestamp": self.start_time.isoformat(),
            "hostname": DEMO_HOSTNAME,
            "cpu_percent": 96,
            "memory_percent": 50,
            "disk_percent": 60,
            "network_bytes_sent": 100,
            "network_bytes_received": 200,
            "source": "demo",
            "_id": "demo-sample",
        }
        metrics_reader = Mock()
        metrics_reader.get_latest_metric.return_value = latest
        metrics_reader.get_recent_metrics.return_value = [latest]
        incident_writer = Mock()
        incident_writer.create_incident.side_effect = lambda incident: incident
        detector = DetectionService(
            metrics_reader,
            incident_writer,
            isolation_forest_enabled=False,
        )

        incidents = detector.process_latest_metric()
        detector.process_latest_metric()

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["source"], "demo")
        incident_writer.create_incident.assert_called_once()


class DemoLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_task_starts_and_stops_with_fastapi_lifespan(self):
        async def wait_for_shutdown(stop_event, *_):
            await stop_event.wait()

        with self.assertLogs(main.logger, level="INFO") as captured:
            with (
                patch("backend.app.main.read_demo_mode", return_value=True),
                patch("backend.app.main.read_demo_sample_interval_seconds", return_value=5),
                patch("backend.app.main._run_demo_telemetry_loop", side_effect=wait_for_shutdown) as demo_loop,
                patch("backend.app.main._run_detection_loop", side_effect=wait_for_shutdown),
                patch("backend.app.main._run_log_detection_loop", side_effect=wait_for_shutdown),
                patch("backend.app.main.close_client") as close_client,
            ):
                async with main.lifespan(main.app):
                    await asyncio.sleep(0)

        demo_loop.assert_awaited_once()
        close_client.assert_called_once_with()
        self.assertTrue(
            any("Demo telemetry enabled" in message for message in captured.output)
        )

    async def test_startup_logs_demo_mode_and_producer_start(self):
        stop_event = asyncio.Event()
        stop_event.set()

        with self.assertLogs(main.logger, level="INFO") as captured:
            await main._run_demo_telemetry_loop(stop_event, sample_interval_seconds=1)

        self.assertEqual(main.logger.level, 20)
        self.assertIn(
            "Demo telemetry producer started (sample interval: 1.0 seconds).",
            captured.output[0],
        )

    async def test_detected_demo_incident_uses_existing_local_analyzer(self):
        stop_event = asyncio.Event()
        incident = {
            "incident_id": "demo-incident",
            "source": "demo",
        }

        async def process_in_thread(function, *args):
            result = function(*args)
            stop_event.set()
            return result

        with (
            patch("backend.app.main.read_demo_mode", return_value=True),
            patch(
                "backend.app.main.detection_service.process_latest_metric",
                return_value=[incident],
            ),
            patch("backend.app.main.analyze_incident") as analyze_mock,
            patch("backend.app.main.asyncio.to_thread", side_effect=process_in_thread),
            patch("backend.app.main.DETECTION_POLL_INTERVAL_SECONDS", 1),
        ):
            await main._run_detection_loop(stop_event, demo_mode=True)

        analyze_mock.assert_called_once_with("demo-incident")

    async def test_demo_loop_samples_and_exits_after_shutdown_signal(self):
        class SampleCounter:
            def __init__(self):
                self.count = 0

            def collect_sample(self):
                self.count += 1

        sample_counter = SampleCounter()
        stop_event = asyncio.Event()
        with (
            patch("backend.app.main.demo_telemetry_service", sample_counter),
        ):
            task = asyncio.create_task(
                main._run_demo_telemetry_loop(stop_event, sample_interval_seconds=0.005)
            )
            await asyncio.sleep(0.02)
            stop_event.set()
            await asyncio.wait_for(task, timeout=1)

        self.assertGreaterEqual(sample_counter.count, 2)


if __name__ == "__main__":
    unittest.main()
