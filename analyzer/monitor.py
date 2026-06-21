import os
import sys

# Ensure project root is in the system path for direct script execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import signal
import logging
import queue
import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from analyzer.parser import parse_line
from analyzer.alert_manager import AlertManager
from analyzer import config

class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging HTTP requests to stdout to keep console logs clean
        pass

    def do_GET(self):
        monitor = self.server.monitor_ref
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            worker_alive = monitor.worker_thread is not None and monitor.worker_thread.is_alive()
            health_data = {
                "status": "healthy" if (monitor.running and worker_alive) else "unhealthy",
                "monitor_running": monitor.running,
                "worker_thread_alive": worker_alive,
                "queue_size": monitor.queue.qsize()
            }
            self.wfile.write(json.dumps(health_data).encode("utf-8"))
            
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            
            with monitor.metrics_lock:
                metrics = monitor.metrics.copy()
            qsize = monitor.queue.qsize()
            
            prometheus_lines = [
                f"# HELP logs_processed_total Total count of successfully parsed log lines.",
                f"# TYPE logs_processed_total counter",
                f"logs_processed_total {metrics['logs_processed']}",
                
                f"# HELP alerts_triggered_total Total alerts matching severity thresholds.",
                f"# TYPE alerts_triggered_total counter",
                f"alerts_triggered_total {metrics['alerts_triggered']}",
                
                f"# HELP alerts_sent_total Total alerts successfully dispatched to webhooks.",
                f"# TYPE alerts_sent_total counter",
                f"alerts_sent_total {metrics['alerts_sent']}",
                
                f"# HELP alerts_failed_total Total alerts that failed after retries.",
                f"# TYPE alerts_failed_total counter",
                f"alerts_failed_total {metrics['alerts_failed']}",
                
                f"# HELP alerts_throttled_total Total duplicate alerts suppressed.",
                f"# TYPE alerts_throttled_total counter",
                f"alerts_throttled_total {metrics['alerts_throttled']}",
                
                f"# HELP malformed_logs_total Total log lines failing parsing regex.",
                f"# TYPE malformed_logs_total counter",
                f"malformed_logs_total {metrics['malformed_logs']}",
                
                f"# HELP queue_size Current number of elements in parsing queue.",
                f"# TYPE queue_size gauge",
                f"queue_size {qsize}"
            ]
            self.wfile.write(("\n".join(prometheus_lines) + "\n").encode("utf-8"))
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

# Setup logging for the monitor
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("LogAnalyzer.Monitor")

class LogMonitor:
    def __init__(self):
        self.file_path = config.LOG_FILE_PATH
        self.alert_manager = AlertManager()
        self.running = True
        self.queue = queue.Queue()
        self.worker_thread = None
        self.metrics_lock = threading.Lock()
        self.http_server = None
        self.http_thread = None
        
        # Metrics
        self.metrics = {
            "logs_processed": 0,
            "malformed_logs": 0,
            "alerts_triggered": 0,
            "alerts_sent": 0,
            "alerts_throttled": 0,
            "alerts_failed": 0
        }

    def _worker(self):
        """Worker thread that consumes log lines from the queue, parses them, and fires alerts."""
        logger.info("Alert worker thread started.")
        while True:
            try:
                line = self.queue.get(timeout=1.0)
            except queue.Empty:
                if not self.running:
                    break
                continue
                
            if line is None:
                self.queue.task_done()
                break
                
            try:
                # Parse line
                entry = parse_line(line)
                if not entry:
                    with self.metrics_lock:
                        self.metrics["malformed_logs"] += 1
                    continue
                
                with self.metrics_lock:
                    self.metrics["logs_processed"] += 1
                
                # Compare severity values
                level_val = config.SEVERITY_MAP.get(entry.level, 0)
                if level_val >= config.ALERT_SEVERITY_LEVEL:
                    with self.metrics_lock:
                        self.metrics["alerts_triggered"] += 1
                    success, status = self.alert_manager.send_alert(entry)
                    with self.metrics_lock:
                        if success:
                            self.metrics["alerts_sent"] += 1
                        elif status == "throttled":
                            self.metrics["alerts_throttled"] += 1
                        else:
                            self.metrics["alerts_failed"] += 1
            except Exception as e:
                logger.error(f"Error in alert worker: {e}", exc_info=True)
            finally:
                self.queue.task_done()
                
        logger.info("Alert worker thread shutting down.")

    def stop(self):
        self.running = False

    def print_metrics(self):
        logger.info("--- Execution Summary Metrics ---")
        for k, v in self.metrics.items():
            logger.info(f"{k}: {v}")
        logger.info("---------------------------------")

    def run(self):
        logger.info(f"Starting Log Analyzer Monitor. Target log path: {self.file_path}")
        config.validate_config()
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(self.file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            logger.info(f"Created log directory: {log_dir}")

        # Register signals for graceful shutdown
        def handle_signal(signum, frame):
            logger.info(f"Received shutdown signal ({signum}). Stopping monitor...")
            self.stop()
            
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # Wait for log file to exist (handles container startup delays)
        while self.running and not os.path.exists(self.file_path):
            logger.info(f"Log file '{self.file_path}' does not exist yet. Waiting...")
            time.sleep(2.0)
            
        if not self.running:
            logger.info("Exit requested during startup.")
            return

        # Start Observability HTTP server
        try:
            self.http_server = HTTPServer(("0.0.0.0", 8000), MetricsHandler)
            self.http_server.monitor_ref = self
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
            logger.info("Observability metrics server started at http://0.0.0.0:8000")
        except Exception as e:
            logger.error(f"Failed to start Observability server: {e}")

        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        # Open file and seek to end to avoid reading historical log dump on restart
        try:
            file_handle = open(self.file_path, "r", encoding="utf-8")
            file_handle.seek(0, os.SEEK_END)
            last_ino = os.fstat(file_handle.fileno()).st_ino
            last_size = os.fstat(file_handle.fileno()).st_size
            logger.info(f"Tailing '{self.file_path}' (Inode: {last_ino}, Size: {last_size} bytes)")
        except Exception as e:
            logger.critical(f"Failed to open log file {self.file_path}: {e}")
            # Signal worker thread to stop if file open fails
            self.queue.put(None)
            return

        while self.running:
            try:
                # Handle file disappearance (e.g. log rotation deleting file momentarily)
                if not os.path.exists(self.file_path):
                    logger.warning("Log file disappeared. Waiting for it to reappear...")
                    file_handle.close()
                    while self.running and not os.path.exists(self.file_path):
                        time.sleep(1.0)
                    if not self.running:
                        break
                    file_handle = open(self.file_path, "r", encoding="utf-8")
                    last_ino = os.fstat(file_handle.fileno()).st_ino
                    last_size = os.fstat(file_handle.fileno()).st_size
                    logger.info(f"Log file recreated. Re-opened Inode: {last_ino}")
                    continue

                # Check if file has changed inode (rotation) or size is smaller (truncation)
                stat_info = os.stat(self.file_path)
                curr_ino = stat_info.st_ino
                curr_size = stat_info.st_size
                
                if curr_ino != last_ino or curr_size < last_size:
                    logger.info("Log rotation or truncation event detected. Re-opening log file...")
                    file_handle.close()
                    file_handle = open(self.file_path, "r", encoding="utf-8")
                    last_ino = curr_ino
                    last_size = curr_size
                    continue

                # Read line
                line = file_handle.readline()
                if not line:
                    # Update tracked size to avoid false alarms
                    last_size = file_handle.tell()
                    time.sleep(0.1)  # Sleep briefly to avoid high CPU usage
                    continue
                
                last_size = file_handle.tell()
                
                # Push log line to queue for asynchronous processing
                self.queue.put(line)
                        
            except Exception as e:
                logger.error(f"Error encountered in monitor execution loop: {e}", exc_info=True)
                time.sleep(1.0)

        # Cleanup log file
        try:
            file_handle.close()
        except Exception:
            pass
            
        # Shut down HTTP server
        if self.http_server:
            logger.info("Stopping Observability metrics server...")
            self.http_server.shutdown()
            self.http_server.server_close()
            if self.http_thread:
                self.http_thread.join(timeout=2.0)

        # Signal worker thread to exit and wait for it to join
        logger.info("Signaling worker thread to shutdown...")
        self.queue.put(None)
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
            
        self.print_metrics()
        logger.info("Log Analyzer Monitor shutdown complete.")

if __name__ == "__main__":
    monitor = LogMonitor()
    monitor.run()
