from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import db


class DatabaseConfigTests(unittest.TestCase):
    def test_sqlite_connection_uses_wal_and_busy_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            connection = sqlite3.connect(Path(tmp) / "queue.db")
            try:
                db._configure_sqlite_connection(connection)

                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
                synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(journal_mode, "wal")
        self.assertEqual(busy_timeout, db.SQLITE_BUSY_TIMEOUT_MS)
        self.assertEqual(synchronous, 1)

    def test_sqlite_connect_args_include_timeout(self) -> None:
        self.assertEqual(
            db._sqlite_connect_args("sqlite:////tmp/app.db"),
            {"check_same_thread": False, "timeout": 30.0},
        )
        self.assertEqual(db._sqlite_connect_args("postgresql://example"), {})


if __name__ == "__main__":
    unittest.main()
