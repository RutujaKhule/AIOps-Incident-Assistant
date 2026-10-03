import unittest
from unittest.mock import Mock

from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from backend.app.services.metrics_service import (
    METRIC_FIELDS,
    MetricsStorageError,
    create_metric_document,
    get_recent_metrics,
    get_metrics_history,
    save_metric,
)


SAMPLE_METRICS = {
    "timestamp": "2026-10-02T12:00:00+00:00",
    "hostname": "test-host",
    "cpu_percent": 25.4,
    "memory_percent": 48.2,
    "disk_percent": 61.0,
    "network_bytes_sent": 123456,
    "network_bytes_received": 654321,
}


class MetricsServiceTests(unittest.TestCase):
    def test_metric_document_contains_only_required_fields(self):
        metrics = {**SAMPLE_METRICS, "unneeded": "value"}

        document = create_metric_document(metrics)

        self.assertEqual(tuple(document), METRIC_FIELDS)
        self.assertNotIn("unneeded", document)

    def test_metric_document_preserves_optional_demo_source(self):
        document = create_metric_document({**SAMPLE_METRICS, "source": "demo"})

        self.assertEqual(document["source"], "demo")
        self.assertEqual(
            {field: document[field] for field in METRIC_FIELDS},
            SAMPLE_METRICS,
        )

    def test_save_metric_inserts_document(self):
        collection = Mock()
        collection.insert_one.return_value.inserted_id = "inserted-id"

        inserted_id = save_metric(SAMPLE_METRICS, collection=collection)

        self.assertEqual(inserted_id, "inserted-id")
        collection.insert_one.assert_called_once_with(SAMPLE_METRICS)

    def test_save_metric_wraps_database_errors(self):
        collection = Mock()
        collection.insert_one.side_effect = PyMongoError("server unavailable")

        with self.assertRaisesRegex(MetricsStorageError, "server unavailable"):
            save_metric(SAMPLE_METRICS, collection=collection)

    def test_get_recent_metrics_sorts_and_filters_by_hostname(self):
        collection = Mock()
        cursor = collection.find.return_value
        cursor.sort.return_value.limit.return_value = [SAMPLE_METRICS]

        result = get_recent_metrics(limit=5, hostname="test-host", collection=collection)

        self.assertEqual(result, [SAMPLE_METRICS])
        collection.find.assert_called_once_with({"hostname": "test-host"})
        cursor.sort.assert_called_once_with("timestamp", DESCENDING)
        cursor.sort.return_value.limit.assert_called_once_with(5)

    def test_get_metrics_history_filters_and_orders_results(self):
        collection = Mock()
        cursor = collection.find.return_value
        cursor.sort.return_value.limit.return_value = [SAMPLE_METRICS]

        result = get_metrics_history(
            minutes=30,
            hostname="test-host",
            limit=5,
            collection=collection,
        )

        self.assertEqual(result, [SAMPLE_METRICS])
        query = collection.find.call_args.args[0]
        self.assertEqual(query["hostname"], "test-host")
        self.assertIn("$gte", query["timestamp"])
        cursor.sort.assert_called_once_with("timestamp", DESCENDING)
        cursor.sort.return_value.limit.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()