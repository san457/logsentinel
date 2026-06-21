import time
import json
import logging
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from typing import Dict, Any, Tuple
from analyzer.parser import LogEntry
from analyzer import config

logger = logging.getLogger("LogAnalyzer.AlertManager")

class AlertManager:
    def __init__(self):
        self.discord_url = config.DISCORD_WEBHOOK_URL
        self.slack_url = config.SLACK_WEBHOOK_URL
        self.throttle_window = config.THROTTLE_WINDOW_SECONDS
        
        # In-memory store for rate limiting: {key_hash: last_alert_time}
        self.alert_history: Dict[str, float] = {}
        # In-memory store for suppressed alert counts: {key_hash: count}
        self.suppressed_counts: Dict[str, int] = {}
        
        # Setup session with exponential backoff retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # Waits 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _generate_alert_key(self, entry: LogEntry) -> str:
        """Generates a key for deduplicating alerts based on level and message content."""
        # Normalize the message slightly (e.g. collapse multiple spaces) to make matching robust
        normalized_msg = " ".join(entry.message.strip().split())
        raw_key = f"{entry.level}:{normalized_msg}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    def _should_throttle(self, key: str) -> bool:
        """Determines if the alert should be throttled based on time window."""
        now = time.time()
        if key in self.alert_history:
            elapsed = now - self.alert_history[key]
            if elapsed < self.throttle_window:
                self.suppressed_counts[key] = self.suppressed_counts.get(key, 0) + 1
                return True
        
        # Update last alert time and reset suppression count
        self.alert_history[key] = now
        self.suppressed_counts[key] = 0
        return False

    def _get_color_decimal(self, level: str) -> int:
        """Returns decimal color code for Discord embeds based on log level."""
        if level == "CRITICAL":
            return 16515843  # Vibrant Red (#FC1903)
        elif level == "ERROR":
            return 16744192  # Vibrant Orange (#FFA200)
        elif level == "WARNING":
            return 16771840  # Yellow (#FFE600)
        return 3447003  # Blue for others

    def _format_discord_payload(self, entry: LogEntry, suppressed: int = 0) -> Dict[str, Any]:
        """Formats the log entry as a Discord Rich Embed."""
        color = self.get_color_decimal(entry.level) if hasattr(self, 'get_color_decimal') else self._get_color_decimal(entry.level)
        
        embed = {
            "title": f"🚨 Production Alert: {entry.level}",
            "description": f"**Message:** {entry.message}",
            "color": color,
            "fields": [
                {"name": "Timestamp", "value": f"`{entry.timestamp}`", "inline": True},
                {"name": "Severity", "value": f"`{entry.level}`", "inline": True}
            ],
            "footer": {
                "text": "Automated Log Analyzer System"
            }
        }

        if suppressed > 0:
            embed["fields"].append({
                "name": "Throttling Active",
                "value": f"⚠️ Suppressed `{suppressed}` similar alerts in the last {self.throttle_window}s.",
                "inline": False
            })

        if entry.metadata:
            metadata_str = json.dumps(entry.metadata, indent=2)
            embed["fields"].append({
                "name": "Metadata JSON",
                "value": f"```json\n{metadata_str}\n```",
                "inline": False
            })

        return {"embeds": [embed]}

    def _format_slack_payload(self, entry: LogEntry, suppressed: int = 0) -> Dict[str, Any]:
        """Formats the log entry as a Slack Block Kit payload."""
        emoji = "🔴" if entry.level == "CRITICAL" else "🟠" if entry.level == "ERROR" else "🟡"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Production Alert - {entry.level}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n>{entry.message}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n`{entry.timestamp}`"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n`{entry.level}`"}
                ]
            }
        ]

        if suppressed > 0:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⚠️ *Throttling active:* Suppressed `{suppressed}` duplicate alerts in the last {self.throttle_window} seconds."
                    }
                ]
            })

        if entry.metadata:
            metadata_str = json.dumps(entry.metadata, indent=2)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Metadata JSON:*\n```json\n{metadata_str}\n```"
                }
            })

        return {"blocks": blocks}

    def send_alert(self, entry: LogEntry) -> Tuple[bool, str]:
        """Orchestrates validation, rate limiting, and dispatches requests to Slack/Discord."""
        key = self._generate_alert_key(entry)
        
        # Check throttling
        if self._should_throttle(key):
            logger.info(f"Throttling alert for duplicate pattern: [{entry.level}] {entry.message}")
            return False, "throttled"

        # Fetch active suppression count to report in webhook embed
        suppressed = self.suppressed_counts.get(key, 0)
        
        discord_payload = self._format_discord_payload(entry, suppressed)
        slack_payload = self._format_slack_payload(entry, suppressed)
        
        dispatched_any = False
        errors = []

        # Send to Discord
        if self.discord_url:
            try:
                response = self.session.post(
                    self.discord_url,
                    json=discord_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5.0
                )
                if response.status_code in [200, 204]:
                    logger.info("Successfully sent alert to Discord webhook.")
                    dispatched_any = True
                else:
                    err_msg = f"Discord returned status {response.status_code}: {response.text}"
                    logger.error(err_msg)
                    errors.append(err_msg)
            except Exception as e:
                err_msg = f"Discord connection failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)
        else:
            print("\n=== SIMULATED DISCORD WEBHOOK ALERT ===")
            print(json.dumps(discord_payload, indent=2))
            print("=======================================\n")
            dispatched_any = True

        # Send to Slack
        if self.slack_url:
            try:
                response = self.session.post(
                    self.slack_url,
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5.0
                )
                if response.status_code == 200:
                    logger.info("Successfully sent alert to Slack webhook.")
                    dispatched_any = True
                else:
                    err_msg = f"Slack returned status {response.status_code}: {response.text}"
                    logger.error(err_msg)
                    errors.append(err_msg)
            except Exception as e:
                err_msg = f"Slack connection failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)
        else:
            print("\n=== SIMULATED SLACK WEBHOOK ALERT ===")
            print(json.dumps(slack_payload, indent=2))
            print("=====================================\n")
            dispatched_any = True

        if errors and not dispatched_any:
            return False, "; ".join(errors)
        return True, "success"
