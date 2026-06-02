from __future__ import annotations

import unittest
from datetime import timedelta

from app.jobs import should_requeue_stale_job
from app.models import now_utc


class JobRecoveryTests(unittest.TestCase):
    def test_should_requeue_only_stale_running_jobs(self) -> None:
        now = now_utc()
        stale_after = timedelta(minutes=30)

        self.assertTrue(should_requeue_stale_job("running", now - timedelta(minutes=31), now, stale_after))
        self.assertFalse(should_requeue_stale_job("running", now - timedelta(minutes=5), now, stale_after))
        self.assertFalse(should_requeue_stale_job("pending", now - timedelta(hours=2), now, stale_after))
        self.assertFalse(should_requeue_stale_job("completed", now - timedelta(hours=2), now, stale_after))


if __name__ == "__main__":
    unittest.main()
