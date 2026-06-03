from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

import app.main as main
from app.main import build_supplier_quality_snapshot, create_manual_job, read_job_evidence_payload, upload_job
from app.models import Client, Job, now_utc
from app.schemas import ManualJobCreate


class ApiGuardTests(unittest.TestCase):
    def test_manual_job_rejects_empty_no_input_job_before_db_access(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            create_manual_job(ManualJobCreate(telegram_id="123"), db=object())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Upload a document", str(raised.exception.detail))

    def test_read_job_evidence_payload_reads_json_inside_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "jobs" / "job-1" / "output" / "evidence.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(json.dumps({"status": "failed", "ai_required": True}), encoding="utf-8")

            payload = read_job_evidence_payload(SimpleNamespace(evidence_path=str(evidence_path)), storage_root=root)

        self.assertEqual(payload["status"], "failed")
        self.assertTrue(payload["ai_required"])

    def test_read_job_evidence_payload_rejects_paths_outside_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as root_tmp, tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "evidence.json"
            outside.write_text("{}", encoding="utf-8")

            with self.assertRaises(HTTPException) as raised:
                read_job_evidence_payload(SimpleNamespace(evidence_path=str(outside)), storage_root=Path(root_tmp))

        self.assertEqual(raised.exception.status_code, 404)

    def test_supplier_quality_snapshot_reads_provider_statuses_and_ai_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "jobs" / "job-1" / "output" / "evidence.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(
                json.dumps(
                    {
                        "ai_required": True,
                        "stage": "supplier_search",
                        "search": {
                            "reports": [
                                {"provider": "yandex", "status": "ok"},
                                {"provider": "google", "status": "empty"},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            created_at = now_utc() - timedelta(seconds=90)
            jobs = [
                SimpleNamespace(
                    id="job-1",
                    mode="supplier_search",
                    title="failure",
                    status="failed",
                    verified_count=0,
                    target_suppliers=2,
                    error="AI failed",
                    evidence_path=str(evidence_path),
                    created_at=created_at,
                    completed_at=now_utc(),
                )
            ]

            snapshot = build_supplier_quality_snapshot(jobs, storage_root=root)

        self.assertEqual(snapshot["window_size"], 1)
        self.assertEqual(snapshot["status_counts"], {"failed": 1})
        self.assertEqual(snapshot["ai_required_failures"], 1)
        self.assertEqual(snapshot["provider_status_counts"]["yandex"], {"ok": 1})
        self.assertEqual(snapshot["provider_status_counts"]["google"], {"empty": 1})
        self.assertEqual(snapshot["recent_failures"][0]["stage"], "supplier_search")
        self.assertIn("ai_required_failures", {alert["code"] for alert in snapshot["alerts"]})
        self.assertIn("search_provider_no_ok", {alert["code"] for alert in snapshot["alerts"]})


class ApiAsyncGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_empty_file_list_before_db_access(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await upload_job(telegram_id="123", files=[], db=object())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("at least one document", str(raised.exception.detail))

    async def test_upload_rejects_supplier_search_source_url_without_tz_file(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await upload_job(
                telegram_id="123",
                mode="supplier_search",
                files=[],
                source_urls="https://etp.example.ru/procedure/123",
                db=object(),
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("technical assignment file", str(raised.exception.detail))

    async def test_upload_accepts_report_source_url_without_files(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_create_job = main.create_job
        original_enqueue_job = main.enqueue_job
        captured: dict = {}

        def fake_create_job(*args, **kwargs):
            captured.update(kwargs)
            return Job(id="job-1", client_id="client-1", mode=kwargs["mode"], title=kwargs["title"], target_suppliers=kwargs["target_suppliers"])

        try:
            db.add(Client(id="client-1", telegram_id="123", allowed_procurement_report=True))
            db.commit()
            main.create_job = fake_create_job
            main.enqueue_job = lambda _job_id: None

            result = await upload_job(
                telegram_id="123",
                mode="procurement_report",
                files=[],
                source_urls="https://etp.example.ru/procedure/123",
                db=db,
            )
        finally:
            main.create_job = original_create_job
            main.enqueue_job = original_enqueue_job
            db.close()

        self.assertEqual(result["id"], "job-1")
        self.assertEqual(captured["files"], [])
        self.assertEqual(captured["sources"][0]["value"], "https://etp.example.ru/procedure/123")

    async def test_upload_supplier_search_multiple_files_creates_separate_jobs(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        class FakeUpload:
            def __init__(self, filename: str, content: bytes) -> None:
                self.filename = filename
                self._content = content

            async def read(self) -> bytes:
                return self._content

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_create_job = main.create_job
        original_enqueue_job = main.enqueue_job
        captured: list[dict] = []
        enqueued: list[str] = []

        def fake_create_job(*args, **kwargs):
            captured.append(kwargs)
            return Job(
                id=f"job-{len(captured)}",
                client_id="client-1",
                mode=kwargs["mode"],
                title=kwargs["title"],
                target_suppliers=kwargs["target_suppliers"],
                file_count=len(kwargs["files"]),
            )

        try:
            db.add(Client(id="client-1", telegram_id="123", allowed_supplier_search=True))
            db.commit()
            main.create_job = fake_create_job
            main.enqueue_job = lambda job_id: enqueued.append(job_id)

            result = await upload_job(
                telegram_id="123",
                mode="supplier_search",
                files=[
                    FakeUpload("ТЗ насос.docx", b"pump"),
                    FakeUpload("ТЗ вентиляция.docx", b"vent"),
                ],
                db=db,
            )
        finally:
            main.create_job = original_create_job
            main.enqueue_job = original_enqueue_job
            db.close()

        self.assertTrue(result["batch"])
        self.assertEqual(result["count"], 2)
        self.assertEqual([item["id"] for item in result["jobs"]], ["job-1", "job-2"])
        self.assertEqual(enqueued, ["job-1", "job-2"])
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0]["title"], "ТЗ насос")
        self.assertEqual(captured[0]["files"], [("ТЗ насос.docx", b"pump")])
        self.assertEqual(captured[1]["title"], "ТЗ вентиляция")
        self.assertEqual(captured[1]["files"], [("ТЗ вентиляция.docx", b"vent")])
        self.assertEqual(captured[0]["sources"], [])


if __name__ == "__main__":
    unittest.main()
