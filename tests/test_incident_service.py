import unittest
from unittest.mock import Mock

from backend.app.services.incident_service import (
    InvalidIncidentTransition,
    create_incident,
    update_incident_status,
)


SAMPLE_INCIDENT = {
    "incident_id": "incident-1",
    "hostname": "test-host",
    "incident_type": "HIGH_CPU",
    "severity": "HIGH",
    "status": "OPEN",
    "detected_at": "2026-10-02T12:00:00+00:00",
    "description": "CPU usage exceeded threshold.",
    "metric_snapshot": {"cpu_percent": 95.4},
    "detection_method": "THRESHOLD",
}


class IncidentServiceTests(unittest.TestCase):
    def test_create_incident_inserts_the_document(self):
        collection = Mock()
        collection.find_one.return_value = None

        created = create_incident(SAMPLE_INCIDENT, collection=collection)

        self.assertEqual(created, SAMPLE_INCIDENT)
        collection.insert_one.assert_called_once_with(SAMPLE_INCIDENT)

    def test_active_incident_is_not_duplicated(self):
        collection = Mock()
        collection.find_one.side_effect = [None, SAMPLE_INCIDENT]

        first = create_incident(SAMPLE_INCIDENT, collection=collection)
        second = create_incident(SAMPLE_INCIDENT, collection=collection)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        collection.insert_one.assert_called_once()

    def test_log_deduplication_key_is_persisted_and_used_for_lookup(self):
        log_incident = {
            **SAMPLE_INCIDENT,
            "incident_type": "REPEATED_LOG_ERROR",
            "severity": "MEDIUM",
            "metric_snapshot": {},
            "detection_method": "LOG_PATTERN",
            "deduplication_key": "error-key-a",
        }
        collection = Mock()
        collection.find_one.return_value = None

        created = create_incident(log_incident, collection=collection)

        self.assertEqual(created["deduplication_key"], "error-key-a")
        self.assertEqual(collection.find_one.call_args.args[0]["deduplication_key"], "error-key-a")
        collection.insert_one.assert_called_once_with(created)

    def test_different_log_messages_do_not_share_deduplication_key(self):
        collection = Mock()
        collection.find_one.return_value = None
        first = {**SAMPLE_INCIDENT, "deduplication_key": "error-key-a"}
        second = {**SAMPLE_INCIDENT, "deduplication_key": "error-key-b"}

        create_incident(first, collection=collection)
        create_incident(second, collection=collection)

        self.assertEqual(collection.find_one.call_count, 2)
        self.assertEqual(
            [call.args[0]["deduplication_key"] for call in collection.find_one.call_args_list],
            ["error-key-a", "error-key-b"],
        )

    def test_active_log_incident_with_same_key_is_not_duplicated(self):
        log_incident = {
            **SAMPLE_INCIDENT,
            "incident_type": "REPEATED_LOG_ERROR",
            "severity": "MEDIUM",
            "metric_snapshot": {},
            "detection_method": "LOG_PATTERN",
            "deduplication_key": "same-log-error",
        }
        collection = Mock()
        collection.find_one.side_effect = [None, log_incident]

        first = create_incident(log_incident, collection=collection)
        second = create_incident(log_incident, collection=collection)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        collection.insert_one.assert_called_once()

    def test_active_log_dedup_advances_trigger_checkpoint(self):
        existing = {
            **SAMPLE_INCIDENT,
            "incident_type": "REPEATED_LOG_ERROR",
            "deduplication_key": "same-log-error",
            "trigger_log_id": "old-log-id",
        }
        candidate = {
            **existing,
            "incident_id": "incident-2",
            "trigger_log_id": "new-log-id",
        }
        collection = Mock()
        collection.find_one.return_value = existing

        result = create_incident(candidate, collection=collection)

        self.assertIsNone(result)
        collection.update_one.assert_called_once_with(
            {"incident_id": existing["incident_id"]},
            {"$set": {"trigger_log_id": "new-log-id"}},
        )
        collection.insert_one.assert_not_called()

    def test_resolved_log_incident_allows_new_incident(self):
        log_incident = {
            **SAMPLE_INCIDENT,
            "incident_type": "REPEATED_LOG_ERROR",
            "severity": "MEDIUM",
            "metric_snapshot": {},
            "detection_method": "LOG_PATTERN",
            "deduplication_key": "resolved-log-error",
        }
        collection = Mock()
        collection.find_one.side_effect = [None, None]

        first = create_incident(log_incident, collection=collection)
        second = create_incident(log_incident, collection=collection)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(collection.insert_one.call_count, 2)

    def test_status_update_acknowledges_incident(self):
        collection = Mock()
        collection.find_one.return_value = SAMPLE_INCIDENT
        updated = {**SAMPLE_INCIDENT, "status": "ACKNOWLEDGED"}
        collection.find_one_and_update.return_value = updated

        result = update_incident_status("incident-1", "ACKNOWLEDGED", collection=collection)

        self.assertEqual(result["status"], "ACKNOWLEDGED")

    def test_resolved_incident_cannot_be_acknowledged(self):
        collection = Mock()
        collection.find_one.return_value = {**SAMPLE_INCIDENT, "status": "RESOLVED"}

        with self.assertRaises(InvalidIncidentTransition):
            update_incident_status("incident-1", "ACKNOWLEDGED", collection=collection)


if __name__ == "__main__":
    unittest.main()