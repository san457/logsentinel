import re
import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger("LogAnalyzer.Parser")

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    raw_line: str = ""

# Regex pattern for: YYYY-MM-DD HH:MM:SS LEVEL MESSAGE
# e.g., 2025-06-01 10:20:15 INFO User login successful
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(?P<rest>.*)$"
)

def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively masks sensitive keys (passwords, keys, tokens, etc.) to prevent leakages."""
    sensitive_substrings = {"password", "token", "secret", "key", "auth", "ssn", "credit_card"}
    masked = {}
    for k, v in data.items():
        if any(sub in k.lower() for sub in sensitive_substrings):
            masked[k] = "********"
        elif isinstance(v, dict):
            masked[k] = mask_sensitive_data(v)
        elif isinstance(v, list):
            masked[k] = [
                mask_sensitive_data(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            masked[k] = v
    return masked

def parse_line(line: str) -> Optional[LogEntry]:
    """Parses a raw log line, extracts metadata JSON if present, and returns a LogEntry."""
    line = line.strip()
    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        logger.debug(f"Log line did not match standard pattern: {line}")
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    rest = match.group("rest").strip()

    message = rest
    metadata = None

    # Check if the message ends with a JSON block
    if rest.endswith("}"):
        start_idx = rest.find("{")
        while start_idx != -1:
            potential_json = rest[start_idx:]
            try:
                parsed_json = json.loads(potential_json)
                if isinstance(parsed_json, dict):
                    metadata = mask_sensitive_data(parsed_json)
                    message = rest[:start_idx].strip()
                    break
            except json.JSONDecodeError:
                pass
            # Try the next '{' in case of embedded braces earlier in the message
            start_idx = rest.find("{", start_idx + 1)

    return LogEntry(
        timestamp=timestamp,
        level=level,
        message=message,
        metadata=metadata,
        raw_line=line
    )
