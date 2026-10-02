import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from backend.app.detection.log_detection import (
    LogDetectionService,
    detect_repeated_log_errors,
)


NOW = datetime.now(timezone.utc)


def make_log(index, level="ERROR", message="Database connection failed", source="application", timestamp=None):
    timestamp = timestamp or (NOW - timedelta(seconds=3 - index)).isoformat()
    return {
        "log_id": f"log-{index}",
        "timestamp": timestamp,
        "hostname": "test-host",
        "level": level,
        "source": source,
        "message": message,
    }


class RepeatedLogDetectionTests(unittest.TestCase):
    def test_fewer_than_repeat_count_creates_no_incident(self):
        incidents = detect_repeated_log_errors(
            [make_log(1), make_log(2)], repeat_count=3, window_seconds=60, now=NOW
        )

        self.assertEqual(incidents, [])

    def test_repeat_threshold_creates_medium_incident(self):
        incidents = detect_repeated_log_errors(
            [make_log(1), make_log(2), make_log(3)],
            repeat_count=3,
            window_seconds=60,
            now=NOW,
        )

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["incident_type"], "REPEATED_LOG_ERROR")
        self.assertEqual(incidents[0]["severity"], "MEDIUM")
        self.assertEqual(incidents[0]["detection_method"], "LOG_PATTERN")
        self.assertEqual(incidents[0]["metric_snapshot"], {})
        self.assertIn("3 times within 60 seconds", incidents[0]["description"])

    def test_repeated_critical_messages_create_high_incident(self):
        incidents = detect_repeated_log_errors(
            [make_log(1, "CRITICAL"), make_log(2, "CRITICAL"), make_log(3, "CRITICAL")],
            repeat_count=3,
            window_seconds=60,
            now=NOW,
        )

        self.assertEqual(incidents[0]["severity"], "HIGH")

    def test_extra_whitespace_is_normalized_but_other_sources_are_not_merged(self):
        logs = [
            make_log(1, message="Database   connection failed"),
            make_log(2, message="Database connection failed"),
            make_log(3, message="Database connection failed", source="worker"),
        ]

        incidents = detect_repeated_log_errors(
            logs,
            repeat_count=2,
            window_seconds=60,
            now=NOW,
        )

        self.assertEqual(len(incidents), 1)
        self.assertIn("2 times", incidents[0]["description"])

    def test_errors_outside_time_window_do_not_repeat(self):
        logs = [make_log(1), make_log(2), make_log(3)]

        incidents = detect_repeated_log_errors(
            logs,
            repeat_count=3,
            window_seconds=1,
            now=NOW,
        )

        self.assertEqual(incidents, [])

    def test_duplicate_poll_does_not_recreate_same_trigger(self):
        logs = [make_log(1), make_log(2), make_log(3)]
        reader = Mock()
        reader.get_error_logs.return_value = logs
        writer = Mock()
        writer.create_incident.side_effect = lambda incident: incident
        detector = LogDetectionService(reader, writer)

        first = detector.process_recent_logs()
        second = detector.process_recent_logs()

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        writer.create_incident.assert_called_once()

    def test_restarted_detector_does_not_replay_previous_trigger(self):
        logs = [make_log(1), make_log(2), make_log(3)]
        reader = Mock()
        reader.get_error_logs.return_value = logs
        writer = Mock()
        writer.get_latest_incident_by_deduplication_key.return_value = {
            "trigger_log_id": "log-3"
        }
        detector = LogDetectionService(reader, writer)

        incidents = detector.process_recent_logs()

        self.assertEqual(incidents, [])
        writer.create_incident.assert_not_called()

    def test_new_repeated_group_can_trigger_again_after_resolution(self):
        first_group = [make_log(1), make_log(2), make_log(3)]
        later_now = datetime.now(timezone.utc)
        next_group = [
            make_log(4, timestamp=(later_now - timedelta(seconds=2)).isoformat()),
            make_log(5, timestamp=(later_now - timedelta(seconds=1)).isoformat()),
            make_log(6, timestamp=later_now.isoformat()),
        ]
        reader = Mock()
        reader.get_error_logs.side_effect = [first_group, first_group + next_group]
        writer = Mock()
        writer.create_incident.side_effect = lambda incident: incident
        detector = LogDetectionService(reader, writer)

        first = detector.process_recent_logs()
        later = detector.process_recent_logs()

        self.assertEqual(len(first), 1)
        self.assertEqual(len(later), 1)
        self.assertNotEqual(first[0]["incident_id"], later[0]["incident_id"])


if __name__ == "__main__":
    unittest.main()