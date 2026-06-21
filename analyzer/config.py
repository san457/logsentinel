import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Logger levels mapping
SEVERITY_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Config variables
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/server.log")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()

ALERT_SEVERITY_LEVEL_STR = os.getenv("ALERT_SEVERITY_LEVEL", "ERROR").upper()
ALERT_SEVERITY_LEVEL = SEVERITY_MAP.get(ALERT_SEVERITY_LEVEL_STR, logging.ERROR)

try:
    THROTTLE_WINDOW_SECONDS = int(os.getenv("THROTTLE_WINDOW_SECONDS", "60"))
except ValueError:
    THROTTLE_WINDOW_SECONDS = 60

try:
    LOG_INTERVAL_SECONDS = float(os.getenv("LOG_INTERVAL_SECONDS", "2.0"))
except ValueError:
    LOG_INTERVAL_SECONDS = 2.0

def validate_config():
    """Validates basic configurations and logs loaded values."""
    print("--- Loaded Configuration ---")
    print(f"Log File Path: {LOG_FILE_PATH}")
    print(f"Alert Severity Level: {ALERT_SEVERITY_LEVEL_STR} ({ALERT_SEVERITY_LEVEL})")
    print(f"Discord Alerting: {'Enabled' if DISCORD_WEBHOOK_URL else 'Disabled (will print to stdout)'}")
    print(f"Slack Alerting: {'Enabled' if SLACK_WEBHOOK_URL else 'Disabled (will print to stdout)'}")
    print(f"Throttle Window: {THROTTLE_WINDOW_SECONDS}s")
    print("----------------------------")

if __name__ == "__main__":
    validate_config()
