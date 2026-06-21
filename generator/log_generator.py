import os
import sys
import json
import time
import random
import signal
from datetime import datetime

# Ensure project root is in the system path for direct script execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import config

# Standard templates to simulate real production service events
LOG_TEMPLATES = [
    # INFO
    ("INFO", "User login successful", {"user_id": 1001, "ip": "192.168.1.50"}),
    ("INFO", "GET /api/v1/users 200", {"duration_ms": 45, "user_agent": "Mozilla/5.0"}),
    ("INFO", "Payment gateway initialized", {}),
    ("INFO", "Cache refresh completed successfully", {"keys_cleared": 420}),
    ("INFO", "GET /index.html 200", {"ip": "203.0.113.195"}),
    
    # WARNING
    ("WARNING", "High CPU usage detected", {"cpu_percent": 87.5}),
    ("WARNING", "Slow query execution", {"duration_ms": 1240, "query": "SELECT * FROM orders WHERE user_id = 9928;"}),
    ("WARNING", "Disk usage is high on /dev/sda1", {"disk_percent": 81.2}),
    ("WARNING", "Rate limit approaching for user", {"user_id": 4410, "current_rate": 95}),
    
    # ERROR
    ("ERROR", "Database query timeout", {"db_host": "db.local", "timeout_ms": 5000}),
    ("ERROR", "Payment processing failed", {"tx_id": "tx_992384", "gateway": "stripe", "error": "insufficient_funds"}),
    ("ERROR", "External API call returned 502 Bad Gateway", {"url": "https://api.thirdparty.com/data", "attempt": 3}),
    ("ERROR", "User auth failed due to invalid credentials", {"username": "hackerman", "password": "compromised_password_123", "secret_token": "token_abc"}), # Sensitive keys for masking test
    
    # CRITICAL
    ("CRITICAL", "500 Internal Server Error", {"traceback": "Traceback (most recent call last):\n  File 'app.py', line 45...\nZeroDivisionError: division by zero"}),
    ("CRITICAL", "Out of Memory: Killed process 9912 (python)", {"ram_free_mb": 4}),
    ("CRITICAL", "Failed to bind to port 8080: Address already in use", {"port": 8080, "protocol": "tcp"})
]

class LogGenerator:
    def __init__(self):
        self.file_path = config.LOG_FILE_PATH
        self.interval = config.LOG_INTERVAL_SECONDS
        self.running = True
        
    def stop(self):
        self.running = False
        
    def run(self):
        print(f"Starting Log Generator. Writing to: {self.file_path} (Interval: {self.interval}s)")
        
        # Ensure log directory exists
        log_dir = os.path.dirname(self.file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            print(f"Created log directory: {log_dir}")
            
        def handle_signal(signum, frame):
            print(f"\nReceived termination signal ({signum}). Stopping generator...")
            self.stop()
            
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        while self.running:
            # Weighted choose to mimic realistic level spreads
            category = random.choices(
                ["INFO", "WARNING", "ERROR", "CRITICAL"],
                weights=[60, 20, 15, 5],
                k=1
            )[0]
            
            candidates = [tpl for tpl in LOG_TEMPLATES if tpl[0] == category]
            level, msg, metadata = random.choice(candidates)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Format according to user format spec
            if metadata:
                # Append metadata as JSON space-separated at the end
                line = f"{timestamp} {level} {msg} {json.dumps(metadata)}\n"
            else:
                line = f"{timestamp} {level} {msg}\n"
                
            try:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                print(f"Generated: {line.strip()}", flush=True)
            except Exception as e:
                print(f"Error writing to log file: {e}", flush=True)
                
            # Sleep in small fractions to exit promptly upon signal
            slept = 0.0
            while self.running and slept < self.interval:
                time.sleep(0.1)
                slept += 0.1
                
        print("Log Generator shutdown complete.")

if __name__ == "__main__":
    generator = LogGenerator()
    generator.run()
