import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from pathlib import Path

from pymongo.errors import PyMongoError

from agent.log_collector import (
    SAFE_LOG_DIRECTORY,
    collect_new_lines,
    get_log_file_path,
    parse_log_line,
)
from backend.app.services.log_service import (
    LogStorageError,
    get_error_logs,
    get_recent_logs,
    insert_log,
)


INFO_LOG = {
    "log_id": "log-1",
    "timestamp": "2026-10-02T10:20:01+00:00",
    "hostname": "test-host",
    "level": "INFO",
    "source": "application",
    "message": "Started successfully",
}
ERROR_LOG = {
    **INFO_LOG,
    "log_id": "log-2",
    "level": "ERROR",
    "message": "Database connection failed",
}


class LogParserTests(unittest.TestCase):
    def test_parse_valid_log_line(self):
        parsed = parse_log_line(
            "2026-10-02 10:20:08 ERROR application Database connection failed"
        )

        self.assertEqual(parsed["timestamp"], "2026-10-02T10:20:08+00:00")
        self.assertEqual(parsed["level"], "ERROR")
        self.assertEqual(parsed["source"], "application")
        self.assertEqual(parsed["message"], "Database connection failed")

    def test_malformed_line_is_skipped(self):
        self.assertIsNone(parse_log_line("not a valid application log"))
        self.assertIsNone(parse_log_line("2026-99-02 10:20:08 ERROR app Bad date"))

    def test_log_path_is_confined_to_demo_service(self):
        path = get_log_file_path("demo_service/sample_app.log")
        self.assertTrue(path.name == "sample_app.log")
        with self.assertRaises(ValueError):
            get_log_file_path("C:/Windows/system.ini")

    def test_collector_reads_valid_entries_from_project_sample(self):
        writer = Mock()
        with TemporaryDirectory(dir=SAFE_LOG_DIRECTORY) as directory:
            path = Path(directory) / "test.log"
            path.write_text(
                "2026-10-02 10:20:01 INFO app Started\n"
                "2026-10-02 10:20:05 WARNING app Slow\n"
                "2026-10-02 10:20:08 ERROR app Failed\n",
                encoding="utf-8",
            )

            offset, inserted_count = collect_new_lines(path, log_writer=writer)

            self.assertEqual(inserted_count, 3)
            self.assertEqual(offset, path.stat().st_size)
        self.assertEqual(writer.call_count, 3)

    def test_collector_keeps_cursor_when_storage_fails(self):
        writer = Mock(side_effect=LogStorageError("database unavailable"))
        path = get_log_file_path("demo_service/sample_app.log")

        offset, inserted_count = collect_new_lines(path, log_writer=writer)

        self.assertEqual(offset, 0)
        self.assertEqual(inserted_count, 0)
        writer.assert_called_once()


class LogStorageTests(unittest.TestCase):
    def test_insert_info_log(self):
        collection = Mock()

        inserted = insert_log(INFO_LOG, collection=collection)

        self.assertEqual(inserted["level"], "INFO")
        collection.insert_one.assert_called_once_with(INFO_LOG)

    def test_insert_error_log(self):
        collection = Mock()

        inserted = insert_log(ERROR_LOG, collection=collection)

        self.assertEqual(inserted["level"], "ERROR")
        collection.insert_one.assert_called_once_with(ERROR_LOG)

    def test_get_recent_logs_filters_and_orders(self):
        collection = Mock()
        cursor = collection.find.return_value
        cursor.sort.return_value.limit.return_value = [INFO_LOG]

        result = get_recent_logs(level="INFO", hostname="test-host", limit=5, collection=collection)

        self.assertEqual(result, [INFO_LOG])
        collection.find.assert_called_once_with({"level": "INFO", "hostname": "test-host"})
        cursor.sort.assert_called_once_with("timestamp", -1)
        cursor.sort.return_value.limit.assert_called_once_with(5)

    def test_get_error_logs_filters_error_and_critical(self):
        collection = Mock()
        cursor = collection.find.return_value
        cursor.sort.return_value.limit.return_value = [ERROR_LOG]

        result = get_error_logs(hostname="test-host", collection=collection)

        self.assertEqual(result, [ERROR_LOG])
        collection.find.assert_called_once_with(
            {"level": {"$in": ["ERROR", "CRITICAL"]}, "hostname": "test-host"}
        )

    def test_insert_database_error_is_wrapped(self):
        collection = Mock()
        collection.insert_one.side_effect = PyMongoError("mongo unavailable")

        with self.assertRaisesRegex(LogStorageError, "mongo unavailable"):
            insert_log(ERROR_LOG, collection=collection)


if __name__ == "__main__":
    unittest.main()