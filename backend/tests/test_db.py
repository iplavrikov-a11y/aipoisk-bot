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

    def test_job_number_assigned_and_incremented(self) -> None:
        from app.models import Job
        from app.jobs import create_job

        session = db.SessionLocal()
        try:
            job = create_job(session, client_id=None, mode="supplier_search", title="Test Job Number", target_suppliers=5, files=[])
            self.assertIsNotNone(job.job_number)
            self.assertGreaterEqual(job.job_number, 1)

            job2 = create_job(session, client_id=None, mode="supplier_search", title="Test Job Number 2", target_suppliers=5, files=[])
            self.assertEqual(job2.job_number, job.job_number + 1)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
