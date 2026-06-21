import unittest
from analyzer.parser import parse_line, LogEntry, mask_sensitive_data

class TestLogParser(unittest.TestCase):
    def test_parse_info_no_metadata(self):
        line = "2025-06-01 10:20:15 INFO User login successful"
        entry = parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.timestamp, "2025-06-01 10:20:15")
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "User login successful")
        self.assertIsNone(entry.metadata)

    def test_parse_error_with_metadata(self):
        line = '2025-06-01 10:20:30 ERROR Database query timeout {"db_host": "db.local", "timeout_ms": 5000}'
        entry = parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.timestamp, "2025-06-01 10:20:30")
        self.assertEqual(entry.level, "ERROR")
        self.assertEqual(entry.message, "Database query timeout")
        self.assertDictEqual(entry.metadata, {"db_host": "db.local", "timeout_ms": 5000})

    def test_credential_masking(self):
        line = '2025-06-01 10:20:30 ERROR Auth failure {"user": "admin", "password": "supersecret123", "secret_token": "token_abc"}'
        entry = parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.metadata["password"], "********")
        self.assertEqual(entry.metadata["secret_token"], "********")
        self.assertEqual(entry.metadata["user"], "admin")

    def test_nested_credential_masking(self):
        line = '2025-06-01 10:20:30 ERROR API Error {"request": {"headers": {"Authorization-Key": "key123"}}, "status": 401}'
        entry = parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.metadata["request"]["headers"]["Authorization-Key"], "********")
        self.assertEqual(entry.metadata["status"], 401)

    def test_invalid_json_metadata_fallback(self):
        # Invalid JSON should fall back to treating the trailing part as raw message
        line = '2025-06-01 10:20:30 ERROR Database query timeout {"db_host": "db.local", "broken_json": '
        entry = parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.message, 'Database query timeout {"db_host": "db.local", "broken_json":')
        self.assertIsNone(entry.metadata)

    def test_malformed_logs(self):
        # Empty line
        self.assertIsNone(parse_line(""))
        self.assertIsNone(parse_line("   "))
        # Invalid timestamp format
        self.assertIsNone(parse_line("2025-6-1 10:20:15 INFO Message"))
        # Invalid log level
        self.assertIsNone(parse_line("2025-06-01 10:20:15 OKAY Message"))
        # Non-matching freeform text
        self.assertIsNone(parse_line("Some random app traceback line"))

if __name__ == "__main__":
    unittest.main()
