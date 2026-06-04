from __future__ import annotations

import unittest
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.jobs as jobs
from app.db import Base
from app.jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_SUPPLIER_SEARCH,
    VALID_JOB_MODES,
    _result_stem,
    _process_analysis_and_suppliers,
    _supplier_count_message,
    build_failure_evidence,
    claim_next_job,
    package_job_output_files,
    should_requeue_stale_job,
)
from app.models import Job, SupplierResult, now_utc
from app.procurement_report import ReportGenerationResult


class JobRecoveryTests(unittest.TestCase):
    def test_supplier_count_message_hides_internal_target_when_underfilled(self) -> None:
        message = _supplier_count_message("Частично готово", 8, 15)

        self.assertEqual(message, "Частично готово: найдено и проверено 8")
        self.assertNotIn("8/15", message)

    def test_should_requeue_only_stale_running_jobs(self) -> None:
        now = now_utc()
        stale_after = timedelta(minutes=30)

        self.assertTrue(should_requeue_stale_job("running", now - timedelta(minutes=31), now, stale_after))
        self.assertFalse(should_requeue_stale_job("running", now - timedelta(minutes=5), now, stale_after))
        self.assertFalse(should_requeue_stale_job("pending", now - timedelta(hours=2), now, stale_after))
        self.assertFalse(should_requeue_stale_job("completed", now - timedelta(hours=2), now, stale_after))

    def test_failure_evidence_preserves_ai_required_supplier_contract(self) -> None:
        evidence = build_failure_evidence(
            SimpleNamespace(mode="supplier_search"),
            RuntimeError("AI candidate reranking failed"),
            stage="supplier_search",
        )

        self.assertEqual(evidence["mode"], "supplier_search")
        self.assertEqual(evidence["stage"], "supplier_search")
        self.assertTrue(evidence["ai_required"])
        self.assertFalse(evidence["report_generated"])
        self.assertFalse(evidence["xlsx_generated"])
        self.assertIn("AI-required supplier search failed", evidence["contract"])
        self.assertEqual(evidence["error"]["type"], "RuntimeError")

    def test_combined_mode_is_valid_and_ai_required(self) -> None:
        evidence = build_failure_evidence(
            SimpleNamespace(mode=MODE_ANALYSIS_AND_SUPPLIERS),
            RuntimeError("AI unavailable"),
            stage=MODE_ANALYSIS_AND_SUPPLIERS,
        )

        self.assertIn(MODE_SUPPLIER_SEARCH, VALID_JOB_MODES)
        self.assertIn(MODE_ANALYSIS_AND_SUPPLIERS, VALID_JOB_MODES)
        self.assertTrue(evidence["ai_required"])

    def test_result_stem_uses_subject_without_parenthesis_artifacts(self) -> None:
        job = Job(mode=MODE_SUPPLIER_SEARCH, status="completed", title="Техническое задание 1")

        stem = _result_stem(job, "Средство для очистки поверхностей (кислотный концентрат)")

        self.assertIn("Техническое задание 1 - Средство для очистки поверхностей кислотный концентрат", stem)
        self.assertNotIn("_кислотный", stem)

    def test_result_stem_keeps_cyrillic_output_filename_under_filesystem_limit(self) -> None:
        long_title = "Техническое задание " + "канат стальной оцинкованный " * 12
        long_subject = "поставка канатов грузовых и такелажной продукции " * 10
        job = Job(mode=MODE_SUPPLIER_SEARCH, status="completed", title=long_title)

        stem = _result_stem(job, long_subject)
        filename = f"{stem}_поставщики_12345678.xlsx"

        self.assertLessEqual(len(filename.encode("utf-8")), 255)
        self.assertTrue(stem)

    def test_combined_mode_writes_analysis_and_supplier_files(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_report = jobs.generate_procurement_report
        original_suppliers = jobs.discover_suppliers
        original_supplier_context = jobs.extract_supplier_search_context
        original_job_dir = jobs.job_dir

        async def fake_report(_settings, _context: str) -> ReportGenerationResult:
            return ReportGenerationResult(report="# Анализ\nПредмет закупки: Сварочный полуавтомат", ai_used=True, ai_model="test")

        async def fake_supplier_context(_settings, context: str) -> str:
            self.assertEqual(context, "context")
            return "ТЗ: сварочный полуавтомат MIG/MAG"

        async def fake_suppliers(_settings, _context: str, _target: int, *, progress_callback=None):
            self.assertEqual(_context, "ТЗ: сварочный полуавтомат MIG/MAG")
            if progress_callback:
                await progress_callback(50, "Проверяю сайты и контакты")
            return (
                [
                    {
                        "company_name": "Поставщик",
                        "site": "https://supplier.example",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.example",
                        "comments": "ИИ подтвердил.",
                        "evidence_status": "verified",
                        "match_level": "exact",
                        "product_fit": "exact",
                        "product": "Сварочный полуавтомат",
                    }
                ],
                {
                    "ai_used": True,
                    "procurement_profile": {
                        "items": [{"id": "item-1", "name": "Сварочный полуавтомат"}],
                    },
                },
            )

        with tempfile.TemporaryDirectory() as tmp:
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.generate_procurement_report = fake_report
            jobs.extract_supplier_search_context = fake_supplier_context
            jobs.discover_suppliers = fake_suppliers
            try:
                job = Job(mode=MODE_ANALYSIS_AND_SUPPLIERS, status="running", title="ТЗ сварка", target_suppliers=1)
                db.add(job)
                db.commit()
                db.refresh(job)

                _process_analysis_and_suppliers(db, job, SimpleNamespace(), "context")
                db.refresh(job)
                outputs = package_job_output_files(job)
                supplier_count = db.query(SupplierResult).filter(SupplierResult.job_id == job.id).count()
            finally:
                jobs.generate_procurement_report = original_report
                jobs.discover_suppliers = original_suppliers
                jobs.extract_supplier_search_context = original_supplier_context
                jobs.job_dir = original_job_dir
                db.close()

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.verified_count, 1)
        self.assertEqual(supplier_count, 1)
        self.assertEqual([path.suffix for path in outputs], [".docx", ".xlsx"])
        self.assertEqual(Path(job.result_path).suffix, ".zip")

    def test_claim_next_job_marks_pending_job_running_with_user_facing_message(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            job = Job(mode="supplier_search", status="pending", title="queued")
            db.add(job)
            db.commit()
            job_id = job.id

            claimed = claim_next_job(db, worker_id="test-worker")
            db.refresh(job)

            self.assertEqual(claimed, job_id)
            self.assertEqual(job.status, "running")
            self.assertEqual(job.message, "Задача взята в обработку")
        finally:
            db.close()

    def test_claim_next_job_can_claim_100_pending_jobs_without_duplicates(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            jobs_to_add = [Job(mode="supplier_search", status="pending", title=f"queued-{index}") for index in range(100)]
            db.add_all(jobs_to_add)
            db.commit()

            claimed = [claim_next_job(db, worker_id=f"worker-{index}") for index in range(100)]
            extra_claim = claim_next_job(db, worker_id="worker-extra")

            self.assertEqual(len([item for item in claimed if item]), 100)
            self.assertEqual(len(set(claimed)), 100)
            self.assertIsNone(extra_claim)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
