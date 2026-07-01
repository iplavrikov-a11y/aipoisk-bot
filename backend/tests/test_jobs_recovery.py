from __future__ import annotations

import asyncio
import json
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
    JobCancelledError,
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    VALID_JOB_MODES,
    _analysis_report_title,
    _fill_worker_slots,
    _normalized_worker_concurrency,
    _process_procurement_report,
    _result_filename,
    _result_stem,
    _process_analysis_and_suppliers,
    _process_supplier_search,
    _set_job,
    _supplier_count_message,
    _update_job_title_from_source_context,
    build_failure_evidence,
    claim_next_job,
    package_job_output_files,
    should_requeue_stale_job,
)
from app.models import Job, JobFile, SupplierResult, now_utc
from app.procurement_report import ReportGenerationResult
from app.procurement_sources import SOURCE_KIND_OFFICIAL, SourceFetchResult
from app.tenderplan import TenderplanDownloadedFile


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

    def test_worker_progress_update_does_not_overwrite_db_cancelled_status(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        worker_db = Session()
        cancel_db = Session()
        try:
            job = Job(id="job-cancel-race", mode=MODE_SUPPLIER_SEARCH, status="running", progress=40, title="ТЗ")
            worker_db.add(job)
            worker_db.commit()
            worker_job = worker_db.get(Job, job.id)

            cancel_job = cancel_db.get(Job, job.id)
            cancel_job.status = "cancelled"
            cancel_job.progress = 100
            cancel_job.message = "Задача отменена клиентом"
            cancel_job.updated_at = now_utc()
            cancel_db.commit()

            with self.assertRaises(JobCancelledError):
                _set_job(worker_db, worker_job, status="running", progress=80, message="Проверяю сайты")

            worker_db.expire_all()
            refreshed = worker_db.get(Job, job.id)
            self.assertEqual(refreshed.status, "cancelled")
            self.assertEqual(refreshed.progress, 100)
            self.assertEqual(refreshed.message, "Задача отменена клиентом")
        finally:
            worker_db.close()
            cancel_db.close()

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

        self.assertEqual(stem, "Средство для очистки поверхностей кислотный концентрат")
        self.assertNotIn("_кислотный", stem)

    def test_result_stem_strips_generated_file_suffixes_and_compacts_positions(self) -> None:
        job = Job(mode=MODE_PROCUREMENT_REPORT, status="completed", title="Канат_стальной_Д_7_6_ГОСТ_2688_80_и_ещё_5_позиции_запрос_кп")

        stem = _result_stem(job, "")

        self.assertEqual(stem, "Канат стальной Д 7,6 ГОСТ 2688-80 и ещё 5 поз")
        self.assertEqual(_result_filename("analysis", stem, ".docx"), "Анализ - Канат стальной Д 7,6 ГОСТ 2688-80 и ещё 5 поз.docx")
        self.assertEqual(_result_filename("quote_request", stem, ".docx"), "Запрос КП - Канат стальной Д 7,6 ГОСТ 2688-80 и ещё 5 поз.docx")

    def test_source_only_procurement_title_uses_customer_facing_subject(self) -> None:
        job = Job(mode="procurement_report", status="running", title="Tenderplan / номер извещения")

        _update_job_title_from_source_context(
            job,
            "Карточка закупки:\n- Наименование: Поставка каната стального оцинкованного\n",
        )

        self.assertEqual(job.title, "Поставка каната стального оцинкованного")
        self.assertEqual(
            _analysis_report_title(job, "Поставка каната стального оцинкованного"),
            "Анализ документации: Поставка каната стального оцинкованного",
        )
        self.assertEqual(_result_stem(job, "Поставка каната стального оцинкованного"), "Поставка каната стального оцинкованного")

    def test_source_only_url_title_uses_customer_facing_subject(self) -> None:
        job = Job(mode="procurement_report", status="running", title="ЕИС / zakupki.gov.ru")

        _update_job_title_from_source_context(
            job,
            "Карточка закупки:\n- Наименование: Поставка насосного оборудования\n",
        )

        self.assertEqual(job.title, "Поставка насосного оборудования")

    def test_process_job_stores_downloaded_files_from_official_source_fallback(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_session = jobs.SessionLocal
        original_job_dir = jobs.job_dir
        original_settings = jobs.get_or_create_settings
        original_fetch = jobs.fetch_source_context_sync
        original_extract_text = jobs.document_parser.extract_text
        original_process_report = jobs._process_procurement_report

        def fake_fetch(_kind: str, _value: str) -> SourceFetchResult:
            return SourceFetchResult(
                ok=True,
                status="ok",
                context="Карточка закупки:\n- Наименование: Поставка сотового поликарбоната\n",
                source_url="0168300005126000012",
                extracted_chars=100,
                downloaded_files=[
                    TenderplanDownloadedFile(
                        filename="Техническое задание.docx",
                        content=b"docx",
                        category="documentation",
                        source_url="https://zakupki.gov.ru/file.docx",
                        size=4,
                    )
                ],
            )

        def fake_extract_text(path: str, _options: dict) -> tuple[str, str]:
            self.assertTrue(Path(path).exists())
            return "Техническое задание: сотовый поликарбонат, 120 листов", "ok"

        def fake_process_report(db_arg, job_arg: Job, _settings, context: str) -> None:
            self.assertIn("Поставка сотового поликарбоната", context)
            self.assertIn("Техническое задание: сотовый поликарбонат", context)
            job_arg.status = "completed"
            job_arg.progress = 100
            job_arg.message = "Готово"
            job_arg.completed_at = now_utc()
            db_arg.commit()

        with tempfile.TemporaryDirectory() as tmp:
            jobs.SessionLocal = Session
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.get_or_create_settings = lambda _db: SimpleNamespace(document_settings_json="{}")
            jobs.fetch_source_context_sync = fake_fetch
            jobs.document_parser.extract_text = fake_extract_text
            jobs._process_procurement_report = fake_process_report
            try:
                job = jobs.create_job(
                    db,
                    client_id=None,
                    mode="procurement_report",
                    title="ЕИС / zakupki.gov.ru",
                    target_suppliers=25,
                    files=[],
                    sources=[
                        {
                            "kind": SOURCE_KIND_OFFICIAL,
                            "value": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0168300005126000012",
                        }
                    ],
                )
                job_id = job.id

                jobs._process_job_sync(job_id)
                db.expire_all()
                stored_files = db.query(JobFile).filter(JobFile.job_id == job_id).all()
                refreshed = db.get(Job, job_id)
            finally:
                jobs.SessionLocal = original_session
                jobs.job_dir = original_job_dir
                jobs.get_or_create_settings = original_settings
                jobs.fetch_source_context_sync = original_fetch
                jobs.document_parser.extract_text = original_extract_text
                jobs._process_procurement_report = original_process_report
                db.close()

        self.assertEqual(refreshed.status, "completed")
        self.assertEqual(len(stored_files), 1)
        self.assertEqual(stored_files[0].original_filename, "Техническое задание.docx")

    def test_result_stem_keeps_cyrillic_output_filename_under_filesystem_limit(self) -> None:
        long_title = "Техническое задание " + "канат стальной оцинкованный " * 12
        long_subject = "поставка канатов грузовых и такелажной продукции " * 10
        job = Job(mode=MODE_SUPPLIER_SEARCH, status="completed", title=long_title)

        stem = _result_stem(job, long_subject)
        filename = _result_filename("suppliers", stem, ".xlsx")

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

        async def fake_suppliers(_settings, _context: str, _target: int, *, progress_callback=None, supplier_search_policy="normal"):
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
        self.assertEqual([path.suffix for path in outputs], [".docx", ".xlsx", ".docx"])
        self.assertEqual(Path(job.result_path).suffix, ".zip")
        output_names = [path.name for path in outputs] + [Path(job.result_path).name]
        self.assertEqual(output_names, [
            "Анализ - Сварочный полуавтомат.docx",
            "Поставщики - Сварочный полуавтомат.xlsx",
            "Запрос КП - Сварочный полуавтомат.docx",
            "Результаты - Сварочный полуавтомат.zip",
        ])
        for name in output_names:
            self.assertNotRegex(name, r"_[0-9a-f]{8}(?=\\.)")

    def test_procurement_report_writes_analysis_and_quote_request_files(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_report = jobs.generate_procurement_report
        original_job_dir = jobs.job_dir

        async def fake_report(_settings, _context: str) -> ReportGenerationResult:
            return ReportGenerationResult(
                report="""# Анализ
Предмет закупки: Канат стальной

### Товары и требования (Техническое задание)
| № | Наименование | Характеристики | Ед.изм. | Кол-во | Примечание |
|---|---|---|---|---|---|
| 1 | Канат стальной | ГОСТ 3062-80, диаметр 6,8 мм | м | 5000 | Просим указать в КП |

#### Исполнение
- **Срок поставки:** 30 календарных дней
- **Город поставки:** Казань
- **Условия оплаты:** по договору
- **Документы качества:** паспорт качества
- **Упаковка/тара:** бухты
""",
                ai_used=True,
                ai_model="test",
            )

        with tempfile.TemporaryDirectory() as tmp:
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.generate_procurement_report = fake_report
            try:
                job = Job(mode=MODE_PROCUREMENT_REPORT, status="running", title="ТЗ канат", target_suppliers=0)
                db.add(job)
                db.commit()
                db.refresh(job)

                _process_procurement_report(db, job, SimpleNamespace(has_active_ai_provider=False), "context")
                db.refresh(job)
                outputs = package_job_output_files(job)
                evidence = json.loads(Path(job.evidence_path).read_text(encoding="utf-8"))
                quote_content = Path(evidence["output_files"][1]["content_path"]).read_text(encoding="utf-8")
            finally:
                jobs.generate_procurement_report = original_report
                jobs.job_dir = original_job_dir
                db.close()

        self.assertEqual(job.status, "completed")
        self.assertEqual([item["kind"] for item in evidence["output_files"]], ["analysis", "quote_request"])
        self.assertEqual([path.name for path in outputs], ["Анализ - Канат стальной.docx", "Запрос КП - Канат стальной.docx"])
        self.assertIn("ЗАПРОС КП", quote_content)
        self.assertNotIn("Примечание", quote_content)
        self.assertNotIn("Просим указать в КП", quote_content)

    def test_supplier_search_writes_suppliers_and_quote_request_files(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_suppliers = jobs.discover_suppliers
        original_job_dir = jobs.job_dir

        async def fake_suppliers(_settings, context: str, _target: int, *, progress_callback=None, excluded_suppliers=None, supplier_search_policy="normal"):
            self.assertIn("канат", context.lower())
            self.assertEqual(excluded_suppliers, [])
            if progress_callback:
                await progress_callback(70, "Проверяю сайты и контакты")
            return (
                [
                    {
                        "company_name": "Поставщик",
                        "site": "https://supplier.example",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.example",
                        "comments": "Проверка подтвердила.",
                        "evidence_status": "verified",
                        "match_level": "exact",
                        "product_fit": "exact",
                        "product": "Канат стальной",
                    }
                ],
                {
                    "ai_used": True,
                    "procurement_profile": {
                        "summary": "Канат стальной",
                        "items": [
                            {
                                "id": "item-1",
                                "name": "Канат стальной",
                                "exact_terms": ["ГОСТ 3062-80", "диаметр 6,8 мм"],
                            }
                        ],
                    },
                },
            )

        with tempfile.TemporaryDirectory() as tmp:
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.discover_suppliers = fake_suppliers
            try:
                job = Job(mode=MODE_SUPPLIER_SEARCH, status="running", title="ТЗ канат", target_suppliers=1)
                db.add(job)
                db.commit()
                db.refresh(job)

                _process_supplier_search(
                    db,
                    job,
                    SimpleNamespace(has_active_ai_provider=False, allow_partial_supplier_reports=False),
                    "ТЗ: нужен канат стальной ГОСТ 3062-80, диаметр 6,8 мм, 5000 м",
                )
                db.refresh(job)
                outputs = package_job_output_files(job)
                evidence = json.loads(Path(job.evidence_path).read_text(encoding="utf-8"))
                quote_content = Path(evidence["output_files"][1]["content_path"]).read_text(encoding="utf-8")
            finally:
                jobs.discover_suppliers = original_suppliers
                jobs.job_dir = original_job_dir
                db.close()

        self.assertEqual(job.status, "completed")
        self.assertEqual([path.suffix for path in outputs], [".xlsx", ".docx"])
        self.assertEqual([path.name for path in outputs], ["Поставщики - Канат стальной.xlsx", "Запрос КП - Канат стальной.docx"])
        self.assertEqual([item["kind"] for item in evidence["output_files"]], ["suppliers", "quote_request"])
        self.assertIn("ЗАПРОС КП", quote_content)
        self.assertIn("Канат стальной", quote_content)

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

    def test_claim_next_job_skips_client_that_already_has_active_job(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        now = now_utc()
        try:
            active_a = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="active-a",
                created_at=now - timedelta(minutes=20),
                updated_at=now,
            )
            pending_a = Job(
                client_id="client-a",
                mode="supplier_search",
                status="pending",
                title="pending-a",
                created_at=now - timedelta(minutes=10),
            )
            pending_b = Job(
                client_id="client-b",
                mode="supplier_search",
                status="pending",
                title="pending-b",
                created_at=now - timedelta(minutes=5),
            )
            db.add_all([active_a, pending_a, pending_b])
            db.commit()
            pending_b_id = pending_b.id

            claimed = claim_next_job(db, worker_id="test-worker")
            db.refresh(pending_a)
            db.refresh(pending_b)

            self.assertEqual(claimed, pending_b_id)
            self.assertEqual(pending_a.status, "pending")
            self.assertEqual(pending_b.status, "running")
        finally:
            db.close()

    def test_claim_next_job_reaches_other_clients_after_large_blocked_prefix(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        now = now_utc()
        try:
            active_a = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="active-a",
                created_at=now - timedelta(minutes=200),
                updated_at=now,
            )
            blocked_a = [
                Job(
                    client_id="client-a",
                    mode="supplier_search",
                    status="pending",
                    title=f"blocked-a-{index}",
                    created_at=now - timedelta(minutes=150 - index),
                )
                for index in range(120)
            ]
            pending_b = Job(
                client_id="client-b",
                mode="supplier_search",
                status="pending",
                title="pending-b",
                created_at=now,
            )
            db.add(active_a)
            db.add_all(blocked_a)
            db.add(pending_b)
            db.commit()
            pending_b_id = pending_b.id

            claimed = claim_next_job(db, worker_id="test-worker")
            db.refresh(pending_b)

            self.assertEqual(claimed, pending_b_id)
            self.assertEqual(pending_b.status, "running")
        finally:
            db.close()

    def test_claim_next_job_reclaims_stale_running_job_for_same_client(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        now = now_utc()
        try:
            stale_running = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="stale-a",
                created_at=now - timedelta(minutes=60),
                updated_at=now - timedelta(minutes=31),
            )
            pending_a = Job(
                client_id="client-a",
                mode="supplier_search",
                status="pending",
                title="pending-a",
                created_at=now - timedelta(minutes=10),
            )
            db.add_all([stale_running, pending_a])
            db.commit()
            stale_id = stale_running.id

            claimed = claim_next_job(db, worker_id="test-worker", stale_after=timedelta(minutes=30))
            db.refresh(stale_running)

            self.assertEqual(claimed, stale_id)
            self.assertEqual(stale_running.status, "running")
            self.assertEqual(stale_running.message, "Задача взята в обработку")
        finally:
            db.close()

    def test_claim_next_job_keeps_anonymous_jobs_claimable_fifo(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        now = now_utc()
        try:
            first = Job(client_id=None, mode="supplier_search", status="pending", title="first", created_at=now - timedelta(minutes=2))
            second = Job(client_id=None, mode="supplier_search", status="pending", title="second", created_at=now - timedelta(minutes=1))
            db.add_all([first, second])
            db.commit()
            first_id = first.id

            claimed = claim_next_job(db, worker_id="test-worker")
            db.refresh(first)
            db.refresh(second)

            self.assertEqual(claimed, first_id)
            self.assertEqual(first.status, "running")
            self.assertEqual(second.status, "pending")
        finally:
            db.close()

    def test_worker_concurrency_normalization_keeps_safe_default(self) -> None:
        self.assertEqual(_normalized_worker_concurrency(None), 1)
        self.assertEqual(_normalized_worker_concurrency("bad"), 1)
        self.assertEqual(_normalized_worker_concurrency(0), 1)
        self.assertEqual(_normalized_worker_concurrency(2), 2)

    def test_fill_worker_slots_starts_only_configured_number_of_jobs(self) -> None:
        async def run() -> None:
            original_claim = jobs._claim_job_for_worker
            original_process = jobs.process_job
            claimed_jobs = iter(["job-1", "job-2", "job-3"])
            started: list[str] = []
            release = asyncio.Event()

            def fake_claim(_worker_id: str) -> str | None:
                return next(claimed_jobs, None)

            async def fake_process(job_id: str) -> None:
                started.append(job_id)
                await release.wait()

            jobs._claim_job_for_worker = fake_claim
            jobs.process_job = fake_process
            try:
                running_tasks: set[asyncio.Task[None]] = set()
                claimed = _fill_worker_slots(running_tasks, worker_id="test-worker", concurrency=2)
                await asyncio.sleep(0)

                self.assertEqual(claimed, 2)
                self.assertEqual(started, ["job-1", "job-2"])
                self.assertEqual(len(running_tasks), 2)
            finally:
                release.set()
                if running_tasks:
                    await asyncio.gather(*running_tasks)
                jobs._claim_job_for_worker = original_claim
                jobs.process_job = original_process

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
