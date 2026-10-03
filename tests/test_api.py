import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ai.analyzer import AIAnalysisError, LatestAnalysisNotFound
from backend.app.ai.context_builder import IncidentNotFound
from backend.app.services.incident_service import IncidentServiceError
from backend.app.services.ai_analysis_service import AIAnalysisStorageError
from backend.app.services.log_service import LogStorageError
from backend.app.services.metrics_service import MetricsStorageError


SAMPLE_METRIC = {
    "timestamp": "2026-10-02T12:00:00+00:00",
    "hostname": "test-host",
    "cpu_percent": 25.4,
    "memory_percent": 48.2,
    "disk_percent": 61.0,
    "network_bytes_sent": 123456,
    "network_bytes_received": 654321,
}

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

SAMPLE_LOG = {
    "log_id": "log-1",
    "timestamp": "2026-10-02T10:20:08+00:00",
    "hostname": "test-host",
    "level": "ERROR",
    "source": "application",
    "message": "Database connection failed",
}

SAMPLE_ANALYSIS = {
    "analysis_id": "analysis-1",
    "incident_id": "incident-1",
    "generated_at": "2026-10-02T12:00:00+00:00",
    "provider": "mock",
    "summary": "CPU usage is 95.4%; the configured CPU threshold is 90%.",
    "evidence": ["Incident metric snapshot cpu_percent: 95.4."],
    "possible_causes": ["A CPU-intensive process may be running."],
    "recommended_next_steps": ["Inspect top CPU-consuming processes."],
    "confidence": "HIGH",
    "limitations": ["Possible causes are hypotheses, not confirmed root causes."],
}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "service": "AIOps Incident Assistant"},
        )

    @patch("backend.app.main.check_connection")
    def test_readiness_checks_mongodb(self, check_connection_mock):
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        check_connection_mock.assert_called_once_with()

    @patch("backend.app.main.check_connection", side_effect=RuntimeError("database offline"))
    def test_readiness_returns_service_unavailable_when_mongodb_is_down(self, check_connection_mock):
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Required database is unavailable.")
        check_connection_mock.assert_called_once_with()

    def test_docs_are_available(self):
        response = self.client.get("/docs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("swagger-ui", response.text)

    @patch(
        "backend.app.api.metrics.get_latest_metric",
        return_value={**SAMPLE_METRIC, "_id": "mongo-internal-id"},
    )
    def test_latest_metric(self, get_latest_metric):
        response = self.client.get("/api/metrics/latest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), SAMPLE_METRIC)
        self.assertNotIn("_id", response.json())
        get_latest_metric.assert_called_once_with()

    @patch("backend.app.api.metrics.get_latest_metric", return_value=None)
    def test_latest_metric_returns_not_found_when_empty(self, get_latest_metric):
        response = self.client.get("/api/metrics/latest")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No metrics found.")
        get_latest_metric.assert_called_once_with()

    @patch("backend.app.api.metrics.get_metrics_history", return_value=[SAMPLE_METRIC])
    def test_metrics_history(self, get_metrics_history):
        response = self.client.get(
            "/api/metrics/history?minutes=30&hostname=test-host&limit=5"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [SAMPLE_METRIC])
        get_metrics_history.assert_called_once_with(
            minutes=30,
            hostname="test-host",
            limit=5,
        )

    @patch(
        "backend.app.api.metrics.get_metrics_history",
        return_value=[
            {**SAMPLE_METRIC, "hostname": "AIOps-Demo-Server", "source": "demo"},
            {
                **SAMPLE_METRIC,
                "timestamp": "2026-10-02T12:00:05+00:00",
                "hostname": "AIOps-Demo-Server",
                "source": "demo",
            },
        ],
    )
    def test_metrics_history_returns_multiple_tagged_demo_samples(self, get_metrics_history):
        response = self.client.get("/api/metrics/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        self.assertTrue(all(item["source"] == "demo" for item in response.json()))
        self.assertTrue(all(item["hostname"] == "AIOps-Demo-Server" for item in response.json()))
        get_metrics_history.assert_called_once_with(
            minutes=30,
            hostname=None,
            limit=100,
        )

    def test_history_rejects_invalid_query_parameters(self):
        response = self.client.get("/api/metrics/history?minutes=0&limit=1001")

        self.assertEqual(response.status_code, 422)

    @patch(
        "backend.app.api.metrics.get_metrics_history",
        side_effect=MetricsStorageError("credentials must not be exposed"),
    )
    def test_database_error_returns_generic_service_unavailable(self, get_metrics_history):
        response = self.client.get("/api/metrics/history")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Metrics database is unavailable.")
        self.assertNotIn("credentials", response.text)
        get_metrics_history.assert_called_once_with(
            minutes=30,
            hostname=None,
            limit=100,
        )

    @patch(
        "backend.app.api.incidents.list_incidents",
        return_value=[{**SAMPLE_INCIDENT, "_id": "mongo-id"}],
    )
    def test_list_incidents_with_filters(self, list_incidents_mock):
        response = self.client.get(
            "/api/incidents?hostname=test-host&status=OPEN&severity=HIGH&limit=5"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [SAMPLE_INCIDENT])
        self.assertNotIn("_id", response.json()[0])
        list_incidents_mock.assert_called_once_with(
            hostname="test-host",
            status="OPEN",
            severity="HIGH",
            limit=5,
        )

    @patch("backend.app.api.incidents.get_incident", return_value=SAMPLE_INCIDENT)
    def test_get_incident_by_id(self, get_incident_mock):
        response = self.client.get("/api/incidents/incident-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), SAMPLE_INCIDENT)
        get_incident_mock.assert_called_once_with("incident-1")

    @patch(
        "backend.app.api.incidents.update_incident_status",
        return_value={**SAMPLE_INCIDENT, "status": "ACKNOWLEDGED"},
    )
    def test_acknowledge_incident(self, update_status_mock):
        response = self.client.post("/api/incidents/incident-1/acknowledge")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ACKNOWLEDGED")
        update_status_mock.assert_called_once_with("incident-1", "ACKNOWLEDGED")

    @patch(
        "backend.app.api.incidents.update_incident_status",
        return_value={**SAMPLE_INCIDENT, "status": "RESOLVED"},
    )
    def test_resolve_incident(self, update_status_mock):
        response = self.client.post("/api/incidents/incident-1/resolve")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "RESOLVED")
        update_status_mock.assert_called_once_with("incident-1", "RESOLVED")

    @patch("backend.app.api.incidents.list_incidents", return_value=[SAMPLE_INCIDENT])
    def test_list_open_incidents(self, list_incidents_mock):
        response = self.client.get("/api/incidents/open")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [SAMPLE_INCIDENT])
        list_incidents_mock.assert_called_once_with(
            hostname=None,
            status="OPEN",
            severity=None,
            limit=100,
        )

    @patch("backend.app.api.incidents.get_incident", return_value=None)
    def test_missing_incident_returns_not_found(self, get_incident_mock):
        response = self.client.get("/api/incidents/missing")

        self.assertEqual(response.status_code, 404)
        get_incident_mock.assert_called_once_with("missing")

    def test_incidents_reject_invalid_filters(self):
        response = self.client.get("/api/incidents?status=INVALID&limit=501")

        self.assertEqual(response.status_code, 422)

    @patch(
        "backend.app.api.incidents.list_incidents",
        side_effect=IncidentServiceError("database internals"),
    )
    def test_incident_database_error_is_not_exposed(self, list_incidents_mock):
        response = self.client.get("/api/incidents")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Incident database is unavailable.")
        self.assertNotIn("database internals", response.text)
        list_incidents_mock.assert_called_once_with(
            hostname=None,
            status=None,
            severity=None,
            limit=100,
        )

    @patch(
        "backend.app.api.logs.get_recent_logs",
        return_value=[{**SAMPLE_LOG, "_id": "mongo-id"}],
    )
    def test_list_logs_with_filters(self, get_recent_logs_mock):
        response = self.client.get("/api/logs?level=ERROR&hostname=test-host&limit=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [SAMPLE_LOG])
        self.assertNotIn("_id", response.json()[0])
        get_recent_logs_mock.assert_called_once_with(
            level="ERROR",
            hostname="test-host",
            limit=5,
        )

    @patch("backend.app.api.logs.get_error_logs", return_value=[SAMPLE_LOG])
    def test_error_logs_endpoint(self, get_error_logs_mock):
        response = self.client.get("/api/logs/errors?hostname=test-host&limit=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [SAMPLE_LOG])
        get_error_logs_mock.assert_called_once_with(hostname="test-host", limit=10)

    def test_logs_reject_invalid_level_or_limit(self):
        response = self.client.get("/api/logs?level=DEBUG&limit=1001")

        self.assertEqual(response.status_code, 422)

    @patch(
        "backend.app.api.logs.get_recent_logs",
        side_effect=LogStorageError("database credentials hidden"),
    )
    def test_logs_database_error_returns_service_unavailable(self, get_recent_logs_mock):
        response = self.client.get("/api/logs")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Log database is unavailable.")
        self.assertNotIn("credentials", response.text)
        get_recent_logs_mock.assert_called_once_with(level=None, hostname=None, limit=100)

    @patch(
        "backend.app.api.logs.get_error_logs",
        side_effect=LogStorageError("database unavailable"),
    )
    def test_error_logs_database_error_returns_service_unavailable(self, get_error_logs_mock):
        response = self.client.get("/api/logs/errors")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Log database is unavailable.")
        get_error_logs_mock.assert_called_once_with(hostname=None, limit=100)

    @patch("backend.app.api.ai_analysis.analyze_incident", return_value=SAMPLE_ANALYSIS)
    def test_analyze_incident(self, analyze_incident_mock):
        response = self.client.post("/api/incidents/incident-1/analyze")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), SAMPLE_ANALYSIS)
        self.assertEqual(response.json()["provider"], "mock")
        analyze_incident_mock.assert_called_once_with("incident-1")

    @patch("backend.app.api.ai_analysis.get_incident_analysis", return_value=SAMPLE_ANALYSIS)
    def test_get_latest_incident_analysis(self, get_analysis_mock):
        response = self.client.get("/api/incidents/incident-1/analysis")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), SAMPLE_ANALYSIS)
        get_analysis_mock.assert_called_once_with("incident-1")

    @patch(
        "backend.app.api.ai_analysis.analyze_incident",
        side_effect=IncidentNotFound("missing"),
    )
    def test_analyze_missing_incident(self, analyze_incident_mock):
        response = self.client.post("/api/incidents/missing/analyze")

        self.assertEqual(response.status_code, 404)
        analyze_incident_mock.assert_called_once_with("missing")

    @patch(
        "backend.app.api.ai_analysis.get_incident_analysis",
        side_effect=LatestAnalysisNotFound("incident-1"),
    )
    def test_get_analysis_when_none_exists(self, get_analysis_mock):
        response = self.client.get("/api/incidents/incident-1/analysis")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No analysis exists for this incident.")
        get_analysis_mock.assert_called_once_with("incident-1")

    def test_analysis_rejects_invalid_incident_id_length(self):
        response = self.client.post(f"/api/incidents/{'x' * 129}/analyze")

        self.assertEqual(response.status_code, 422)

    @patch(
        "backend.app.api.ai_analysis.analyze_incident",
        side_effect=AIAnalysisStorageError("database unavailable"),
    )
    def test_analysis_database_failure_is_controlled(self, analyze_incident_mock):
        response = self.client.post("/api/incidents/incident-1/analyze")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Incident analysis storage is unavailable.")
        analyze_incident_mock.assert_called_once_with("incident-1")

    @patch(
        "backend.app.api.ai_analysis.analyze_incident",
        side_effect=AIAnalysisError("provider failed"),
    )
    def test_analysis_provider_failure_is_controlled(self, analyze_incident_mock):
        response = self.client.post("/api/incidents/incident-1/analyze")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Incident analysis is unavailable.")
        analyze_incident_mock.assert_called_once_with("incident-1")

    @patch(
        "backend.app.api.ai_analysis.get_incident_analysis",
        side_effect=AIAnalysisStorageError("mongo unavailable"),
    )
    def test_get_analysis_database_failure_is_controlled(self, get_analysis_mock):
        response = self.client.get("/api/incidents/incident-1/analysis")

        self.assertEqual(response.status_code, 503)
        get_analysis_mock.assert_called_once_with("incident-1")


if __name__ == "__main__":
    unittest.main()