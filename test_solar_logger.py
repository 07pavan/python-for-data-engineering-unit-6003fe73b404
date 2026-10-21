import contextlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import solar_logger


class FakeSolarHandler(BaseHTTPRequestHandler):
    """A tiny stand-in for the solar API, running on this computer."""

    body = {"date": "2025-04-08", "energy_kwh": 12.5}
    status = 200

    def do_GET(self):
        payload = json.dumps(self.body).encode("utf-8")
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass  # keep the test output clean


class SolarLoggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeSolarHandler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/solar?date=today"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeSolarHandler.body = {"date": "2025-04-08", "energy_kwh": 12.5}
        FakeSolarHandler.status = 200
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "solar.db")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self):
        out = io.StringIO()
        with mock.patch.object(solar_logger, "DB_PATH", self.db_path):
            with contextlib.redirect_stdout(out):
                code = solar_logger.main(["solar_logger.py", self.url])
        return code, out.getvalue()

    def test_fetch_today_reads_date_and_energy(self):
        self.assertEqual(solar_logger.fetch_today(self.url), ("2025-04-08", 12.5))

    def test_fetch_today_raises_on_http_error(self):
        FakeSolarHandler.status = 500
        with self.assertRaises(solar_logger.requests.HTTPError):
            solar_logger.fetch_today(self.url)

    def test_save_creates_table_with_expected_columns(self):
        solar_logger.save_output(self.db_path, "2025-04-08", 12.5)
        conn = sqlite3.connect(self.db_path)
        try:
            columns = conn.execute("PRAGMA table_info(daily_output)").fetchall()
        finally:
            conn.close()
        self.assertEqual([(c[1], c[2]) for c in columns],
                         [("date", "TEXT"), ("energy_kwh", "REAL")])

    def test_save_same_date_twice_updates_instead_of_duplicating(self):
        solar_logger.save_output(self.db_path, "2025-04-08", 12.5)
        solar_logger.save_output(self.db_path, "2025-04-08", 14.0)
        self.assertEqual(solar_logger.get_all_rows(self.db_path),
                         [("2025-04-08", 14.0)])

    def test_different_dates_are_kept_in_date_order(self):
        solar_logger.save_output(self.db_path, "2025-04-09", 9.75)
        solar_logger.save_output(self.db_path, "2025-04-08", 12.5)
        self.assertEqual(solar_logger.get_all_rows(self.db_path),
                         [("2025-04-08", 12.5), ("2025-04-09", 9.75)])

    def test_format_row(self):
        self.assertEqual(solar_logger.format_row("2025-04-08", 12.5),
                         "2025-04-08: 12.5 kWh")

    def test_main_prints_saved_row(self):
        code, output = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(output, "2025-04-08: 12.5 kWh\n")

    def test_main_twice_updates_rather_than_duplicates(self):
        self.run_main()
        FakeSolarHandler.body = {"date": "2025-04-08", "energy_kwh": 13.2}
        code, output = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(output, "2025-04-08: 13.2 kWh\n")

    def test_main_reports_unreachable_api(self):
        out = io.StringIO()
        with mock.patch.object(solar_logger, "DB_PATH", self.db_path):
            with contextlib.redirect_stdout(out):
                code = solar_logger.main(["solar_logger.py", "http://127.0.0.1:1/solar"])
        self.assertEqual(code, 1)
        self.assertTrue(out.getvalue().startswith("Could not fetch solar data:"))
        self.assertFalse(os.path.exists(self.db_path))


if __name__ == "__main__":
    unittest.main()