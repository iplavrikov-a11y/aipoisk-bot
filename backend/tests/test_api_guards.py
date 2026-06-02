from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.main import create_manual_job, upload_job
from app.schemas import ManualJobCreate


class ApiGuardTests(unittest.TestCase):
    def test_manual_job_rejects_empty_no_input_job_before_db_access(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            create_manual_job(ManualJobCreate(telegram_id="123"), db=object())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Upload a document", str(raised.exception.detail))


class ApiAsyncGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_empty_file_list_before_db_access(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await upload_job(telegram_id="123", files=[], db=object())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("at least one document", str(raised.exception.detail))


if __name__ == "__main__":
    unittest.main()
