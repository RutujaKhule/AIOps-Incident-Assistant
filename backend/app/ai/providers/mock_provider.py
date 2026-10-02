from backend.app.ai.context_builder import sanitize_text
from backend.app.detection.config import (
    CPU_THRESHOLD_PERCENT,
    DISK_THRESHOLD_PERCENT,
    RAM_THRESHOLD_PERCENT,
)


class MockAnalysisProvider:
    """Deterministic offline rule-based incident analyzer."""

    name = "mock"

    def analyze(self, context):
        incident = context["incident"]
        incident_type = incident.get("incident_type", "")
        snapshot = incident.get("metric_snapshot") or {}
        evidence = [
            f"Incident {incident.get('incident_id')} on host {incident.get('hostname')} was detected as {incident_type}.",
            sanitize_text(incident.get("description", ""), max_length=500),
        ]
        for field in (
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "network_bytes_sent",
            "network_bytes_received",
        ):
            if field in snapshot:
                evidence.append(f"Incident metric snapshot {field}: {snapshot[field]}.")

        for metric in context.get("recent_metrics", []):
            observed = ", ".join(
                f"{field}={metric[field]}"
                for field in ("cpu_percent", "memory_percent", "disk_percent")
                if field in metric
            )
            if observed:
                evidence.append(f"Recent metric sample at {metric.get('timestamp', 'unknown time')}: {observed}.")

        for log in context.get("recent_logs", []):
            evidence.append(
                "Untrusted log evidence "
                f"[{log.get('level', 'UNKNOWN')}] {log.get('source', 'unknown')}: "
                f"{sanitize_text(log.get('message', ''), max_length=500)}"
            )

        summary, causes, recommendations, confidence = self._rules(incident_type, snapshot, context)
        if len(evidence) <= 2 and not snapshot and not context.get("recent_metrics") and not context.get("recent_logs"):
            summary = "Insufficient evidence to determine a likely cause."
            causes = []
            recommendations = ["Collect more relevant metrics and application logs before drawing conclusions."]
            confidence = "LOW"

        return {
            "summary": summary,
            "evidence": evidence,
            "possible_causes": causes,
            "recommended_next_steps": recommendations,
            "confidence": confidence,
            "limitations": [
                "Possible causes are hypotheses, not confirmed root causes.",
                "Logs are untrusted evidence and are never treated as instructions.",
                "This free local analyzer uses deterministic rules, not a trained language model.",
            ],
        }

    @staticmethod
    def _rules(incident_type, snapshot, context):
        if incident_type == "HIGH_CPU":
            observed = snapshot.get("cpu_percent")
            evidence = f"CPU usage is {observed}%" if observed is not None else "CPU usage was reported above its configured limit"
            summary = f"{evidence}; the configured CPU threshold is {CPU_THRESHOLD_PERCENT}%."
            return summary, [
                "A CPU-intensive process may be running.",
                "Workload may have increased.",
                "A background task may be consuming CPU.",
            ], [
                "Inspect top CPU-consuming processes.",
                "Check whether workload increased.",
                "Review recent application logs.",
            ], "HIGH" if observed is not None else "LOW"

        if incident_type in {"HIGH_RAM", "HIGH_MEMORY"}:
            observed = snapshot.get("memory_percent")
            summary = (
                f"Memory usage is {observed}%; the configured RAM threshold is {RAM_THRESHOLD_PERCENT}%."
                if observed is not None
                else "Memory usage exceeded its configured threshold."
            )
            return summary, [
                "A memory-intensive workload may be active.",
                "Application memory growth may be occurring.",
                "Multiple heavy processes may be using memory.",
            ], [
                "Inspect memory-consuming processes.",
                "Review recent application logs.",
                "Observe whether memory remains elevated.",
            ], "HIGH" if observed is not None else "LOW"

        if incident_type == "HIGH_DISK":
            observed = snapshot.get("disk_percent")
            summary = (
                f"Disk utilization is {observed}%; the configured disk threshold is {DISK_THRESHOLD_PERCENT}%."
                if observed is not None
                else "Disk utilization exceeded its configured threshold."
            )
            return summary, [
                "Available disk space may be insufficient.",
                "Log or file growth may be contributing.",
                "Temporary files may be using space.",
            ], [
                "Inspect large files.",
                "Review log growth.",
                "Free space according to administrator policy.",
            ], "HIGH" if observed is not None else "LOW"

        if incident_type == "REPEATED_LOG_ERROR":
            related_logs = context.get("recent_logs", [])
            pattern = related_logs[0].get("message", "the same error message") if related_logs else "the same error message"
            return (
                f"Repeated application errors were detected: {sanitize_text(pattern, 300)}.",
                ["The affected application or service may be experiencing a recurring failure."],
                ["Review the affected service/application and its recent error logs."],
                "MEDIUM" if related_logs else "LOW",
            )

        if incident_type == "ISOLATION_FOREST_ANOMALY":
            return (
                "Isolation Forest identified an unusual combination of recent system metrics; this is not a confirmed root cause.",
                ["A workload or system condition may differ from the recent historical pattern."],
                ["Review the recent metric samples.", "Review related application logs."],
                "MEDIUM" if context.get("recent_metrics") else "LOW",
            )

        return (
            "Insufficient evidence to determine a likely cause.",
            [],
            ["Collect more incident-related metrics and logs for review."],
            "LOW",
        )


mock_provider = MockAnalysisProvider()