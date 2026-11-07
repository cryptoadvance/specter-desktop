"""JSON recovery tests; runnable with unittest without starting a Specter app."""

import contextlib
import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

from cryptoadvance.specter.persistence import read_json_file


class ReadJsonFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "config.json"
        self.backup = Path(str(self.path) + ".bkp")
        self.output = io.StringIO()
        self.stderr = io.StringIO()
        logger = logging.getLogger("cryptoadvance.specter.persistence")
        old_state = logger.handlers[:], logger.level, logger.propagate
        old_raise_exceptions = logging.raiseExceptions
        handler = logging.StreamHandler(self.output)
        logger.handlers = [handler]
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        logging.raiseExceptions = True

        def restore_logging():
            logger.handlers, logger.level, logger.propagate = old_state
            logging.raiseExceptions = old_raise_exceptions
            handler.close()

        self.addCleanup(restore_logging)
        redirect = contextlib.redirect_stderr(self.stderr)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def assert_original_error_logged(self, exception_name):
        self.assertEqual(self.stderr.getvalue(), "")
        output = self.output.getvalue()
        self.assertEqual(output.count("Reading from backup"), 1)
        self.assertIn(str(self.path), output)
        self.assertIn("Traceback (most recent call last):", output)
        self.assertIn(exception_name, output)

    def test_valid_primary_leaves_backup_untouched(self):
        self.path.write_text('{"value": "primary"}')
        self.backup.write_text('{"value": "backup"}')
        self.assertEqual(read_json_file(str(self.path)), {"value": "primary"})
        self.assertEqual(json.loads(self.path.read_text()), {"value": "primary"})
        self.assertEqual(json.loads(self.backup.read_text()), {"value": "backup"})
        self.assertEqual(self.output.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "")

    def test_invalid_primary_recovers_backup_and_logs_traceback(self):
        self.path.write_text("invalid json")
        self.backup.write_text('{"value": "backup"}')
        self.assertEqual(read_json_file(str(self.path)), {"value": "backup"})
        self.assertEqual(json.loads(self.path.read_text()), {"value": "backup"})
        self.assertFalse(self.backup.exists())
        self.assert_original_error_logged("JSONDecodeError")
        self.assertIn("recovered from backup", self.output.getvalue())

    def test_invalid_primary_without_backup_preserves_error(self):
        self.path.write_text("invalid json")
        with self.assertRaises(json.JSONDecodeError) as raised:
            read_json_file(str(self.path))
        self.assertEqual(raised.exception.doc, "invalid json")
        self.assertEqual(self.path.read_text(), "invalid json")
        self.assert_original_error_logged("JSONDecodeError")
        self.assertNotIn("recovered from backup", self.output.getvalue())

    def test_percent_in_path_is_logged_literally(self):
        self.path = Path(self.directory.name) / "config %s.json"
        self.test_invalid_primary_without_backup_preserves_error()

    def test_invalid_backup_is_not_reported_as_recovery(self):
        self.path.write_text("invalid primary")
        self.backup.write_text("invalid backup")
        with self.assertRaises(json.JSONDecodeError) as raised:
            read_json_file(str(self.path))
        self.assertEqual(raised.exception.doc, "invalid backup")
        self.assertEqual(self.path.read_text(), "invalid primary")
        self.assertEqual(self.backup.read_text(), "invalid backup")
        self.assert_original_error_logged("JSONDecodeError")
        self.assertNotIn("recovered from backup", self.output.getvalue())

    def test_missing_primary_recovers_backup(self):
        self.backup.write_text('{"value": "backup"}')
        self.assertEqual(read_json_file(str(self.path)), {"value": "backup"})
        self.assertEqual(json.loads(self.path.read_text()), {"value": "backup"})
        self.assertFalse(self.backup.exists())
        self.assert_original_error_logged("FileNotFoundError")

    def test_missing_primary_without_backup_preserves_error(self):
        with self.assertRaises(FileNotFoundError) as raised:
            read_json_file(str(self.path))
        self.assertEqual(raised.exception.filename, str(self.path))
        self.assertFalse(self.path.exists())
        self.assertFalse(self.backup.exists())
        self.assert_original_error_logged("FileNotFoundError")
        self.assertNotIn("recovered from backup", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
