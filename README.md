# Automated Production Log Analyzer & Discord/Slack Alerter

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://www.docker.com/)
[![Observability](https://img.shields.io/badge/observability-Prometheus%20%7C%20JSON%20Health-green.svg)](#health-and-metrics-endpoints)
[![Build Status](https://img.shields.io/badge/tests-6%20passed-success.svg)](#testing-and-validation-results)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An industry-grade, highly resilient DevOps/SRE telemetry agent that tails system log streams, processes events asynchronously via a multi-threaded **Producer-Consumer** architecture, redacts sensitive credentials, and dispatches real-time alerts to Slack and Discord.

---

## 📖 1. Executive Overview

This project simulates a real-world production monitoring, log auditing, and incident alerting system. Designed from an SRE perspective, the application decouples high-performance log ingestion from network-bound alerting APIs using a thread-safe Queue buffer. 

It tails live log files, detects active file system rotations, parses unstructured text into standard objects using regular expressions, dynamically masks sensitive variables (such as tokens or passwords) inside JSON payloads, and dispatches rich alerts. Furthermore, it exposes a built-in HTTP server to serve JSON health states and Prometheus metrics to scraping tools.

---

## ⚠️ 2. Problem Statement

In cloud-scale environments, log telemetry pipelines suffer from four critical operational challenges:
1. **Network Ingestion Stalls**: Synchronous HTTP calls to third-party endpoints (like Discord or Slack Webhooks) block log monitors, leading to file read backpressure and data loss during log floods.
2. **Log Rotation Failures**: Log shippers often crash or lose file handles when log rotation utilities archive, rename, or truncate active logs.
3. **Alert Fatigue**: Incident cascades (e.g., database outages) generate hundreds of identical errors per second, spamming messaging channels and triggering API rate limits.
4. **Credential Leakage**: Modern microservices sometimes log sensitive payload metadata (e.g., passwords or tokens), exposing PII to destination chat channels.

---

## 🏗️ 3. Solution Architecture

The system resolves these issues using a multi-threaded design:
*   **Producer-Consumer Separation**: The main thread (Producer) continuously reads log streams and enqueues lines instantly. A background worker thread (Consumer) dequeues lines, parses them, and manages webhook alerts.
*   **Volatile Queue Protection**: The queue buffers log spikes, ensuring high I/O throughput even if remote notification targets slow down or experience outages.
*   **Observability Thread**: A separate background HTTP thread serves metrics and health states without interfering with the ingestion loop.

---

## 🎨 4. Architecture Diagram

```
                              [ Log Generator Container ]
                                           │
                                           ▼ (Appends Raw Logs)
                                    [ server.log ]
                                           │
      ┌───────────────────────────── Log Monitor ─────────────────────────────┐
      │                                    │ (Tails File)                     │
      │                                    ▼                                  │
      │                       [ Monitor/Producer Thread ]                     │
      │                                    │                                  │
      │                                    ▼ (Enqueues Lines)                 │
      │                             [ queue.Queue ]                           │
      │                                    │                                  │
      │                                    ▼ (Pulls Lines)                    │
      │                      [ Alert Worker/Consumer Thread ]                 │
      │                                    │                                  │
      │                                    ├──────► [ parser.py ]             │
      │                                    │        (Regex Match & PII Mask)  │
      │                                    │                                  │
      │                                    └──────► [ alert_manager.py ]      │
      │                                             (Throttling & Backoff)    │
      │                                                        │              │
      └────────────────────────────────────────────────────────┼──────────────┘
                                                               ▼
                                                      [ Webhook Targets ]
                                                      (Slack / Discord)
```

*(Refer to the [Screenshots](#screenshots-section) section for the visual Draw.io rendering).*

---

## ✨ 5. Key Features

*   **Continuous Log Tailing**: Simulates `tail -f` behavior with low-overhead file system polling.
*   **Log Rotation Resilience**: Monitors inode mappings and file size to recover from rotation and truncation.
*   **Queue-Based Decoupling**: Thread-safe `queue.Queue` buffers incoming events from the network alerts loop.
*   **Optimized Regex Matching**: Extracts timestamps, log levels, and messages from space-separated formats.
*   **PII & Credential Redaction**: Recursively strips secret tokens, passwords, and keys inside JSON log metadata.
*   **Slack Block Kit Integration**: Formats webhook payloads into visual Slack structural components.
*   **Discord Rich Embeds**: Maps severities to color codes (Red for CRITICAL, Orange for ERROR).
*   **Alert Deduplication / Throttling**: Suppresses duplicate alerts within a sliding window to prevent webhook spam.
*   **Robust Network Retry**: Retries failing webhooks (HTTP 429, 5xx) using exponential backoff and jitter.
*   **Prometheus Metrics Endpoint**: Exposes SRE telemetry gauges and counters on port `8000`.
*   **Liveness Check Endpoint**: Exposes a `/health` endpoint to monitor consumer threads and queue depth.
*   **Signal Hook Interceptor**: Catches `SIGINT`/`SIGTERM` to perform graceful thread and socket shutdowns.
*   **Dockerized Dev Environment**: Multi-service compose file simulating log generation and analysis in isolated boundaries.
*   **Unit Test Suite**: Checks regex correctness, JSON fallback, and PII masking.

---

## 💻 6. Technology Stack

| Technology | Version / Type | Role |
| :--- | :--- | :--- |
| **Python** | `3.11` | Application Runtime Environment |
| **Docker** | `24.0+` | Containerization and deployment isolation |
| **Docker Compose** | `v2.20+` | Multi-service orchestration |
| **Regex (`re`)** | Built-in | Text search, pattern matching, log parsing |
| **Requests** | `2.31.0` | HTTP Client for Discord & Slack webhook delivery |
| **Thread/Queue** | Built-in | Multithreading concurrency and queue management |
| **HTTPServer** | Built-in | Serving `/metrics` and `/health` observability data |
| **Pytest** | `7.4.0` | Test runner and validation environment |

---

## 📁 7. Project Structure

```text
log_analyser/
│
├── analyzer/
│   ├── __init__.py
│   ├── config.py           # Configuration parser (env variables loader)
│   ├── parser.py           # Regex parser and PII credential masking
│   ├── alert_manager.py    # Webhook formatting, throttling, and retry logic
│   └── monitor.py          # Log tailer, queue orchestrator, HTTP metrics server
│
├── generator/
│   ├── __init__.py
│   └── log_generator.py    # Mock log event generator
│
├── logs/
│   └── server.log          # Target log file shared between containers
│
├── tests/
│   └── test_parser.py      # Unit testing suite for parser and PII masking
│
├── .env.example            # Environment variables template
├── .env                    # Active local environment variables (Git ignored)
├── Dockerfile              # Multi-purpose Docker image configuration
├── docker-compose.yml      # Orchestrates generator and analyzer containers
├── requirements.txt        # Third-party package dependencies
└── README.md               # Main project documentation
```

---

## ⚙️ 8. Detailed Component Explanation

### 1. `log_generator.py`
Simulates application traffic. It generates log lines with varying severities (60% INFO, 20% WARNING, 15% ERROR, 5% CRITICAL) and appends JSON metadata (such as SQL statements or user locations) to recreate typical API activity.

### 2. `monitor.py`
The orchestration entrypoint. It starts the Producer thread to watch the log file, initiates the Consumer thread to process alerts, and runs the standard library HTTP server. It handles file system signals to close file handlers and sockets on exit.

### 3. `parser.py`
Converts unstructured log text into structured `LogEntry` dataclasses. It dynamically scans the message payload for embedded JSON strings. If found, it parses them and recursively sanitizes sensitive keys to prevent credential leaks.

### 4. `alert_manager.py`
Formats alert notifications for Slack and Discord. It features:
*   **Throttling**: Computes MD5 hashes of error messages to suppress identical alerts within a sliding window.
*   **Retries**: Mounts a session adapter that retries failed requests (due to 429 rate limits or 5xx server issues) using exponential backoff.

### 5. `config.py`
Loads environment variables using `python-dotenv`, parses severity thresholds, and maps level names to integers.

---

## 🔄 9. Data Flow Explanation

1.  **Generation**: `log_generator.py` writes a structured event line to `logs/server.log`.
2.  **Tailing**: The Producer thread in `monitor.py` reads the new line and pushes the string onto a thread-safe `queue.Queue`.
3.  **Consumption**: The Consumer thread dequeues the line, passing it to `parser.py`.
4.  **Parsing & Masking**: The parser extracts log fields via Regex, parses any trailing JSON metadata, and redacts sensitive data (e.g., passwords).
5.  **Filtering**: The Consumer checks if the log level meets the alerting threshold defined by `ALERT_SEVERITY_LEVEL`.
6.  **Deduplication**: `alert_manager.py` evaluates the message hash. If duplicate alerts are sent within the throttle window, the event is suppressed and counted.
7.  **Dispatch**: If allowed, the manager posts payloads to Slack (Block Kit) and Discord (Embeds) concurrently.

---

## 🧵 10. Producer-Consumer Design Explanation

```
[File Ingestion] 
       │ (Tailing)
       ▼
 [Producer Thread] ──( queue.put() )──► [ queue.Queue ] ──( queue.get() )──► [Consumer Thread] ──► [Webhooks]
```

### Why this design?
Network requests are inherently slow (often taking between 100ms and 2 seconds). Tailing a file synchronously would block log reads during network latency spikes or destination outages, causing ingestion lag.

By using a **thread-safe queue**, the Producer thread reads log files as fast as the OS allows, immediately dropping lines into memory and returning to tail the file. The Consumer thread processes items from the queue independently. If the alerts loop slows down, the queue absorbs the backpressure, ensuring the log file continues to be read.

---

## 🔒 11. Security Features

*   **Recursive Credential Masking**: Scans metadata JSON structures. If key patterns match substring variables (`password`, `token`, `secret`, `key`, `auth`, `ssn`, `credit_card`), the values are replaced with `********`.
*   **Environment Isolation**: Sensitive webhook targets are loaded from a `.env` file that is ignored by Git, preventing credentials from leaking into source code repositories.
*   **Markdown Escaping**: Standardizes text formats to prevent markdown injection payloads (e.g., `@everyone` mentions) inside alerts.

---

## 🛡️ 12. Reliability and Fault Tolerance Features

1.  **Log Rotation Auto-Recovery**: If a log rotation occurs, the Producer detects the inode change or file truncation, re-opens the file path, and continues tailing.
2.  **Transient Network Resilience**: Leverages `urllib3`'s retry mechanisms to automatically handle transient network errors (HTTP 429, 500, 502, 503, 504) with backoff and jitter.
3.  **Worker Thread Safeguards**: Wrap parsing and API dispatch actions in try-catch statements, preventing the worker thread from crashing when handling malformed logs or network failures.
4.  **Graceful Thread Teardown**: Intercepts termination signals, inserts a sentinel object (`None`) into the queue, and joins the threads to finish processing pending items before shutting down the HTTP socket.

---

## ⚙️ 13. Setup Instructions

### Prerequisites
*   Python 3.11+
*   Docker & Docker Compose

### Clone and Setup Configuration
1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/log_analyser.git
    cd log_analyser
    ```
2.  **Copy the environment file**:
    ```bash
    cp .env.example .env
    ```
3.  **Insert Webhook URLs**: Open the `.env` file and set your Discord and Slack webhooks:
    ```env
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456/abcdef
    SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/XXXX
    ```

---

## 🚀 14. Execution Instructions

### Local Execution (No Docker)
1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run the generator**:
    ```bash
    python generator/log_generator.py
    ```
3.  **Run the analyzer** (in a separate terminal window):
    ```bash
    python analyzer/monitor.py
    ```

### Docker Compose Deployment (Recommended)
Docker Compose will orchestrate both services and configure a shared volume for the log directory automatically.

1.  **Build and run containers**:
    ```bash
    docker-compose up --build
    ```
2.  **Run in the background (detached mode)**:
    ```bash
    docker-compose up -d
    ```
3.  **Inspect container logs**:
    ```bash
    docker-compose logs -f
    ```

---

## 📝 15. Environment Variables Table

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/...` | Discord webhook URL (leaves empty to simulate to stdout) |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/...` | Slack webhook URL (leaves empty to simulate to stdout) |
| `ALERT_SEVERITY_LEVEL` | `ERROR` | Filtering threshold level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `LOG_FILE_PATH` | `logs/server.log` | Target file location for the log tailer |
| `THROTTLE_WINDOW_SECONDS`| `60` | Time window (seconds) to suppress duplicate alerts |
| `LOG_INTERVAL_SECONDS` | `2` | Interval (seconds) between generated mock log entries |

---

## 🪵 16. Example Log Entries

Logs are written to `server.log` in a space-separated format: `<timestamp> <level> <message> [<metadata_json>]`.

```text
2026-06-21 02:16:18 INFO Payment gateway initialized
2026-06-21 02:16:22 ERROR User auth failed due to invalid credentials {"username": "hackerman", "password": "compromised_password_123", "secret_token": "token_abc"}
2026-06-21 02:16:30 CRITICAL Failed to bind to port 8080: Address already in use {"port": 8080, "protocol": "tcp"}
```

---

## ✉️ 17. Example Alert Payloads

### Discord Rich Embed Format
```json
{
  "embeds": [
    {
      "title": "🚨 Production Alert: CRITICAL",
      "description": "**Message:** Failed to bind to port 8080: Address already in use",
      "color": 16515843,
      "fields": [
        {"name": "Timestamp", "value": "`2026-06-21 02:16:30`", "inline": true},
        {"name": "Severity", "value": "`CRITICAL`", "inline": true},
        {
          "name": "Metadata JSON",
          "value": "```json\n{\n  \"port\": 8080,\n  \"protocol\": \"tcp\"\n}\n```",
          "inline": false
        }
      ],
      "footer": {"text": "Automated Log Analyzer System"}
    }
  ]
}
```

### Slack Block Kit Format
```json
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "🔴 Production Alert - CRITICAL",
        "emoji": true
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Message:*\n>Failed to bind to port 8080: Address already in use"
      }
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Timestamp:*\n`2026-06-21 02:16:30`"},
        {"type": "mrkdwn", "text": "*Severity:*\n`CRITICAL`"}
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Metadata JSON:*\n```json\n{\n  \"port\": 8080,\n  \"protocol\": \"tcp\"\n}\n```"
      }
    }
  ]
}
```

---

## 📊 18. Health and Metrics Endpoints

Observability endpoints run on port `8000`.

### Health Check Endpoint (`GET /health`)
```json
{
  "status": "healthy",
  "monitor_running": true,
  "worker_thread_alive": true,
  "queue_size": 0
}
```

### Prometheus Telemetry Endpoint (`GET /metrics`)
```text
# HELP logs_processed_total Total count of successfully parsed log lines.
# TYPE logs_processed_total counter
logs_processed_total 85

# HELP alerts_triggered_total Total alerts matching severity thresholds.
# TYPE alerts_triggered_total counter
alerts_triggered_total 12

# HELP alerts_sent_total Total alerts successfully dispatched to webhooks.
# TYPE alerts_sent_total counter
alerts_sent_total 8

# HELP alerts_failed_total Total alerts that failed after retries.
# TYPE alerts_failed_total counter
alerts_failed_total 0

# HELP alerts_throttled_total Total duplicate alerts suppressed.
# TYPE alerts_throttled_total counter
alerts_throttled_total 4

# HELP malformed_logs_total Total log lines failing parsing regex.
# TYPE malformed_logs_total counter
malformed_logs_total 0

# HELP queue_size Current number of elements in parsing queue.
# TYPE queue_size gauge
queue_size 0
```

---

## 🧪 19. Testing and Validation Results

Unit tests are implemented in `tests/test_parser.py` using Python's standard `unittest` framework:

```bash
python3 -m unittest tests/test_parser.py
```

### Execution Output:
```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
```

The tests cover:
*   Parser correctness for standard log formats.
*   Metadata extraction and JSON decoding.
*   PII and credential masking.
*   Malformed log validation.
*   Fallback behavior when parsing invalid JSON.

---

## 🚀 20. Future Improvements

*   **Distributed Rate Limiting**: Migrate the in-memory deduplication cache to a shared Redis store to sync rate limits across multi-node analyzer clusters.
*   **Bounded Queue and Drop Policies**: Set size bounds on the Queue buffer to trigger message compaction and prevent OOM issues during severe log floods.
*   **Kubernetes Manifests & Helm Charts**: Package the generator and analyzer services for Kubernetes, mapping log directories to persistent volume claims.

---

## 💼 21. Resume Impact / Skills Demonstrated

*   **Concurrency & Multithreading**: Designed a Producer-Consumer thread pipeline using Python's `threading` and thread-safe queues.
*   **Security Engineering**: Developed dynamic sanitization mechanisms to prevent PII and credential leaks in system logs.
*   **Systems Observability**: Programmed Prometheus-style metrics scraping and health endpoints using standard library HTTP APIs.
*   **DevOps Orchestration**: Standardized development environments using Docker Compose host-volume sharing and multi-stage container builds.

---

## 💡 22. Lessons Learned

*   **Python Thread Join Deadlocks**: Discovered that worker threads checking `while self.running` can hang during shutdown if blocked on a queue read. Solved this by setting a timeout on `queue.get(timeout=1.0)` and using a sentinel (`None`) value to trigger an exit.
*   **try-finally Continue Bug**: Solved a bug where calling `task_done()` inside a `try` block and subsequently triggering a `continue` caused the `finally` block to call `task_done()` a second time, raising a `ValueError`. The fix was to delegate all task completions to the `finally` block.

---

## 🖼️ 23. Screenshots Section

### Discord Rich Embed Alerts — ERROR & CRITICAL Events
![Discord Alerts Part 1](assets/discord_alerts_1.png)

### Discord Rich Embed Alerts — CRITICAL Cascade with Deduplication
![Discord Alerts Part 2](assets/discord_alerts_2.png)

### Docker Desktop — Live Container Log Stream
![Docker Desktop Console Logs](assets/docker_desktop.png)

### Local Terminal — Monitor Console Output (Throttling, Rotation & Webhook Status)
![Terminal Execution Logs](assets/terminal_logs.png)

### Docker Compose — Generator & Analyzer Live Execution
![Docker Compose Terminal Logs](assets/docker_compose_logs.png)

---

## 📄 24. License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 👤 25. Author

*   **Dhananjay Masih**
*   [GitHub Profile](https://github.com/dhananjaymasih)
*   [LinkedIn Profile](https://linkedin.com/in/dhananjaymasih)
