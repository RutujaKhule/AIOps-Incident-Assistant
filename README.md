# AIOps Incident Assistant

A local-first AIOps monitoring project that collects real host telemetry and application logs, detects abnormal conditions, manages incidents, and provides free rule-based incident analysis through a web dashboard.

## 🚀 Live Demo

[View Live Application](https://aiops-incident-assistant-1.onrender.com)
## Features

- Real CPU, memory, disk, and network metrics collected with `psutil`
- MongoDB storage for metrics, logs, incidents, and analyses
- FastAPI REST API with Swagger documentation
- React/Vite monitoring dashboard with real metric charts and recent errors
- Configurable CPU, RAM, and disk threshold detection
- Isolation Forest anomaly detection using historical metrics
- Repeated ERROR/CRITICAL log detection and incident deduplication
- Incident lifecycle: OPEN, ACKNOWLEDGED, RESOLVED
- Free local rule-based incident analysis; no API key required
- Optional server-side demo telemetry for always-on hosted dashboard demonstrations
- Docker Compose deployment and GitHub Actions CI

## Architecture

```text
System
	-> Monitoring Agent
	-> Metrics + Application Logs
	-> MongoDB
	-> Threshold Detection + Isolation Forest + Repeated-Log Detection
	-> Incident Management
	-> Free Local Incident Analyzer
	-> FastAPI
	-> React Dashboard
```

DevOps flow:

```text
GitHub -> GitHub Actions -> Tests + Frontend Build -> Docker Images -> Docker Compose
```

## Monitoring Agent

The Python monitoring agent periodically collects real metrics from the computer it runs on. It reports CPU usage, RAM usage, disk usage for the home drive, network bytes sent and received, the collection timestamp, and the hostname. Each sample is printed in the terminal and saved to MongoDB.

Set `MONITORING_INTERVAL_SECONDS` to change the sampling interval. It defaults to 5 seconds. Configure `MONGODB_URI` and `MONGODB_DATABASE` before starting the agent. The database name defaults to `AIOpsIncidentAssistant`.

On Windows, activate the existing virtual environment, install the project dependencies, and start the agent from the project root:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DATABASE = "AIOpsIncidentAssistant"
python -m agent.collector
```

Example terminal output (metric values vary by machine and over time):

```json
{
	"timestamp": "2026-09-30T12:00:00+00:00",
	"hostname": "your-computer",
	"cpu_percent": 25.4,
	"memory_percent": 48.2,
	"disk_percent": 61.0,
	"network_bytes_sent": 123456,
	"network_bytes_received": 654321
}
```

## MongoDB Storage

The agent requires a reachable MongoDB server. For a local Windows setup, install MongoDB Community Server and choose the option to run it as a Windows service. Start it from an elevated PowerShell session with `Start-Service MongoDB`, or start the MongoDB service from the Windows Services app. Confirm it is reachable with `mongosh "mongodb://localhost:27017"`.

Set `MONGODB_URI` to the server connection URI and `MONGODB_DATABASE` to the database name. The `.env.example` file lists these variables, but the agent reads environment variables directly; the PowerShell commands above set them for the current session. Keep credentials out of source control and use a secret manager or protected environment variables for authenticated servers.

Samples are stored in the `metrics` collection with only the timestamp, hostname, CPU, memory, disk, and network metrics. A compound index on `hostname` and descending `timestamp` supports recent per-host queries. Example document:

```json
{
	"timestamp": "2026-10-02T12:00:00+00:00",
	"hostname": "workstation",
	"cpu_percent": 25.4,
	"memory_percent": 48.2,
	"disk_percent": 61.0,
	"network_bytes_sent": 123456,
	"network_bytes_received": 654321
}
```

If MongoDB is unavailable, the agent prints a MongoDB storage error, keeps printing collected metrics, and continues sampling. Check that the MongoDB service is running, that `MONGODB_URI` is correct, and that the server accepts connections. The agent does not claim a metric was stored when insertion fails.

## FastAPI Backend

The FastAPI backend reads metrics through the existing MongoDB metrics service. Set `MONGODB_URI` and `MONGODB_DATABASE` in the current PowerShell session as shown above, then start the backend from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The service listens at `http://127.0.0.1:8000`. Interactive Swagger documentation is at `http://127.0.0.1:8000/docs`; the OpenAPI schema is at `http://127.0.0.1:8000/openapi.json`.

Available endpoints:

- `GET /health` reports API health.
- `GET /health/ready` checks MongoDB readiness.
- `GET /api/metrics/latest` returns the newest metric or `404` when no metrics exist.
- `GET /api/metrics/history?minutes=30&limit=100` returns recent metrics, newest first. Optional `hostname` filters the results. `minutes` is limited to 1 through 10080 and `limit` to 1 through 1000.
- `GET /api/logs` and `GET /api/logs/errors` list recent application logs.
- `GET /api/incidents` and `GET /api/incidents/open` list incidents.
- `GET /api/incidents/{incident_id}` retrieves an incident.
- `POST /api/incidents/{incident_id}/acknowledge` and `POST /api/incidents/{incident_id}/resolve` update incident status.
- `POST /api/incidents/{incident_id}/analyze` creates an advisory analysis.
- `GET /api/incidents/{incident_id}/analysis` retrieves the latest saved analysis.

Example requests:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/metrics/latest
Invoke-RestMethod "http://127.0.0.1:8000/api/metrics/history?minutes=30&hostname=workstation&limit=100"
```

The API returns `503` with a generic message when MongoDB is unavailable; database connection details are not sent to clients.

### Hosted Demo Telemetry

The local monitoring agent remains the source of real machine metrics when `DEMO_MODE` is disabled (the default). For a hosted demonstration, configure these environment variables on the backend service:

```text
DEMO_MODE=true
DEMO_SAMPLE_INTERVAL_SECONDS=5
```

In demo mode, one lightweight FastAPI lifespan task writes explicitly tagged (`source=demo`) synthetic metrics and occasional INFO/WARNING/ERROR logs to the existing MongoDB collections. The host is always `AIOps-Demo-Server`; these values do not represent an interviewer's computer. The existing detection loops process the generated data and use the existing incident service and free local analyzer. Active incidents are deduplicated as usual, and demo metrics/logs older than 24 hours are periodically pruned without touching local or untagged records. MongoDB outages are logged and retried on the next interval; health and API requests continue to be served.

Keep `DEMO_MODE=false` for local development when using the existing collector. The public React dashboard labels tagged samples as **Demo Server Monitoring**. This mode requires the same MongoDB configuration as the rest of the backend and does not require a separate collector process or AI credentials.

## React Dashboard

The React and Vite dashboard reads live values and recent metric history only through the FastAPI API. It refreshes every five seconds and does not connect directly to MongoDB. Presentation-only warning thresholds can be adjusted with the `VITE_CPU_*`, `VITE_RAM_*`, and `VITE_DISK_*` variables in `frontend/.env.example`.

With the backend and MongoDB running, open a second PowerShell session, then install and start the frontend from the `frontend` directory:

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the dashboard at `http://localhost:5173`. The backend defaults to `http://127.0.0.1:8000`. To point the dashboard at another API, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to the FastAPI base URL before starting Vite.

The current data flow is:

```text
Python Monitoring Agent -> MongoDB -> FastAPI -> React Dashboard
```

## Anomaly Detection and Incidents

The FastAPI process polls recent MongoDB metrics every five seconds. Detection runs separately from the collector: the collector continues saving metrics, while the detection service reads each new sample and creates incident documents in the separate `incidents` collection.

### Detection Methods

**Threshold detection**: Detects known conditions using predefined limits. CPU, RAM, and disk default to greater than 90% and create HIGH severity incidents. Configure `CPU_THRESHOLD_PERCENT`, `RAM_THRESHOLD_PERCENT`, `DISK_THRESHOLD_PERCENT`, and `THRESHOLD_INCIDENT_SEVERITY` using environment variables.

**Isolation Forest**: Detects unusual patterns relative to historical metric behaviour. It uses CPU, memory, disk, and the cumulative network byte counters. By default, it requires **50 historical samples plus the current sample** before training and scoring. `ISOLATION_FOREST_MIN_SAMPLES`, `ISOLATION_FOREST_CONTAMINATION` (default `0.05`), and `ISOLATION_FOREST_RANDOM_STATE` (default `42`) configure the model. Set `ISOLATION_FOREST_ENABLED=false` to disable it. An Isolation Forest result identifies a statistical outlier; it does not prove a root cause.

The two methods complement one another: thresholds detect known, explicitly defined conditions, while Isolation Forest can flag combinations that do not cross a fixed threshold. Both can produce false positives; network counters are cumulative and are not network rates.

### Incident Lifecycle

Incidents have `OPEN`, `ACKNOWLEDGED`, or `RESOLVED` status and `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` severity. Threshold incidents default to `HIGH`; Isolation Forest incidents default to `MEDIUM`. An active incident (OPEN or ACKNOWLEDGED) is deduplicated by hostname and incident type. Resolving it allows a later new sample to create a new incident.

Incident endpoints:

- `GET /api/incidents` lists recent incidents; optional `hostname`, `status`, `severity`, and `limit` filters are supported.
- `GET /api/incidents/open` lists OPEN incidents.
- `GET /api/incidents/{incident_id}` retrieves one incident.
- `POST /api/incidents/{incident_id}/acknowledge` acknowledges an OPEN incident.
- `POST /api/incidents/{incident_id}/resolve` resolves an OPEN or ACKNOWLEDGED incident.

### Manual CPU Test

To manually generate CPU load for a short detection test, start the monitoring agent and backend first, then run this from the project root:

```powershell
.\.venv\Scripts\python.exe simulator\cpu_spike.py
```

This CPU-only test utility runs only when started, makes no permanent system changes, and stops its worker processes with Ctrl+C. It uses all logical processors by default; use `--workers 1` for a lighter test. Stop it as soon as enough test metrics have been recorded.

## Log Monitoring

The log collector tails `LOG_FILE_PATH` and stores parsed entries in the MongoDB `logs` collection through the shared database client. For safety, the configured file must resolve under the project `demo_service/` directory. The format is `YYYY-MM-DD HH:MM:SS LEVEL source message`; timestamps without a zone are interpreted as UTC. Malformed entries are reported and skipped.

The detection service checks ERROR and CRITICAL logs every five seconds by default. It normalizes repeated whitespace, then groups by hostname, source, and message. At least `LOG_REPEAT_COUNT=3` matching entries within `LOG_REPEAT_WINDOW_SECONDS=60` create a `REPEATED_LOG_ERROR` incident. Repeated ERROR messages are MEDIUM severity; a group containing CRITICAL is HIGH. An active incident for the same normalized message is deduplicated; after resolution, a later matching log can trigger a new incident. This simple pattern detector only flags repetition and does not diagnose a root cause.

Start FastAPI and MongoDB, then run the collector from the project root in a separate terminal:

```powershell
$env:LOG_FILE_PATH = "demo_service/sample_app.log"
.\.venv\Scripts\python.exe -m agent.log_collector --from-start
```

The collector reads existing lines and continues following new ones until Ctrl+C. In another terminal, append three matching errors to demonstrate detection:

```powershell
.\.venv\Scripts\python.exe -m simulator.log_generator --errors 3
```

It also supports finite `--info`, `--warnings`, and `--critical` counts (maximum 100 lines per run). Recent log endpoints are `GET /api/logs` and `GET /api/logs/errors`. The dashboard’s Recent Errors section displays ERROR/CRITICAL entries from the last 30 minutes. The file reader is intentionally limited to the demo directory; this is not a Windows Event Log or arbitrary system-file collector.

## Step 8: AI Incident Analysis

Incident analysis is completely free by default and requires no API key or internet connection. Configure `AI_PROVIDER=mock`; the deterministic local rule-based analyzer uses relevant incident fields, a bounded number of recent metrics, and recent ERROR/CRITICAL logs. Defaults are `AI_MAX_METRICS=30`, `AI_MAX_LOGS=10`, and `AI_MAX_CONTEXT_CHARS=12000`. Context excludes environment variables and redacts common credential patterns. Log messages are untrusted evidence, never instructions.

The analyzer provides a summary, evidence, possible causes, recommended next steps, qualitative confidence, and limitations. Possible causes are hypotheses, not confirmed root causes. Analysis is advisory only: it does not execute commands, restart services, alter files, or remediate incidents. The default is a local rule-based mock, not an LLM.

With the existing MongoDB and FastAPI backend running, analyze an incident from PowerShell:

```powershell
$env:AI_PROVIDER = "mock"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/incidents/<incident_id>/analyze"
Invoke-RestMethod "http://127.0.0.1:8000/api/incidents/<incident_id>/analysis"
```

Analyses are stored separately in MongoDB’s `ai_analyses` collection. The dashboard lets you select an incident, load its latest analysis, and generate a new one using the **Analyze Incident** button. “Free Local Analyzer” identifies the mock provider. No paid or external AI service is configured.

## Docker Compose

Docker Compose runs MongoDB, the FastAPI backend, and the production React/Nginx frontend. Copy `.env.example` to `.env` if you want to customize local settings; the Compose backend uses the internal MongoDB service name, while MongoDB is published only on the loopback interface for local collector access.

```powershell
docker compose up --build
```

Open the dashboard at `http://localhost:5173`, the backend at `http://localhost:8000`, and API docs at `http://localhost:8000/docs`. To stop the services:

```powershell
docker compose down
```

The named `mongodb_data` volume persists database contents when containers stop or are recreated. The existing monitoring and log collectors can run from the project `.venv` on the host; configure their `MONGODB_URI` as `mongodb://127.0.0.1:27017` while Compose is running. No collector service or cloud resource is created by Compose.

## Continuous Integration

`.github/workflows/ci.yml` runs on pushes and pull requests. It installs Python requirements, runs the full unittest suite, installs frontend packages with `npm ci`, runs Vitest, and builds the Vite production bundle. Tests use mocks and do not require MongoDB, cloud credentials, or AI API keys.

Run the same checks locally:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm ci
npm test
npm run build
```

### Verification Status

At Step 9 finalization, the complete Python suite passed **87 tests**, the frontend suite passed **10 tests**, and the production frontend build succeeded. Pylance/workspace diagnostics reported no issues. Docker and Docker Compose were not installed in the verification environment, so container builds and health checks were not run; the Compose and workflow YAML files were syntax-validated locally. GitHub Actions was not run remotely.

## Production Notes

Docker Compose is a local deployment baseline, not a hardened public production environment. Before exposing services beyond localhost, add appropriate authentication, TLS, MongoDB access controls, secret management, backups, and network policy. Thresholds require environment-specific tuning; Isolation Forest needs sufficient history; and the default analyzer is deterministic rules, not a generative LLM. No accuracy or performance claims are made.
