from __future__ import annotations

import asyncio
import json
import threading
import unittest
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.jobs as jobs
from app.db import Base
from app.billing import KIND_SUPPLIER_SEARCH, KIND_SUPPLIER_SEARCH_EXTRA, OP_RELEASE, OP_RESERVE
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
    extract_yandex_job_metrics,
    package_job_output_files,
    should_requeue_stale_job,
)
from app.models import BillingTransaction, Client, Job, JobFile, SupplierResult, now_utc
from app.procurement_report import ReportGenerationResult
from app.procurement_sources import SOURCE_KIND_OFFICIAL, SourceFetchResult
from app.tenderplan import TenderplanDownloadedFile


class JobRecoveryTests(unittest.TestCase):
    def test_cleanup_releases_open_reservation_and_keeps_ledger_consistent(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_job_dir = jobs.job_dir
        try:
            with tempfile.TemporaryDirectory() as tmp:
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                client = Client(id="client-cleanup", telegram_id="cleanup-user")
                job = Job(
                    id="job-cleanup",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="completed",
                    completed_at=now_utc() - timedelta(days=100),
                    created_at=now_utc() - timedelta(days=100),
                )
                db.add_all(
                    [
                        client,
                        job,
                        BillingTransaction(
                            client_id=client.id,
                            job_id=job.id,
                            kind=KIND_SUPPLIER_SEARCH,
                            operation=OP_RESERVE,
                            units=1,
                        ),
                    ]
                )
                db.commit()

                removed = jobs.cleanup_expired_jobs(
                    db,
                    SimpleNamespace(
                        completed_job_retention_days=90,
                        failed_job_retention_days=90,
                        storage_retention_days=90,
                    ),
                )
                transactions = db.query(BillingTransaction).order_by(BillingTransaction.created_at).all()
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertEqual(removed, 1)
        self.assertEqual([item.operation for item in transactions], [OP_RESERVE, OP_RELEASE])
        self.assertTrue(all(item.job_id is None for item in transactions))

    def test_cleanup_does_not_delete_offer_while_decision_or_delivery_is_pending(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        old = now_utc() - timedelta(days=5)
        try:
            client = Client(id="client-live-offer", telegram_id="offer-user")
            job = Job(
                id="job-live-offer",
                client_id=client.id,
                mode=MODE_SUPPLIER_SEARCH,
                status="partial",
                confirmation_kind="registry_fallback",
                confirmation_outcome="accepted",
                offer_delivery_outcome="pending",
                completed_at=old,
                created_at=old,
                updated_at=old,
            )
            db.add_all(
                [
                    client,
                    job,
                    BillingTransaction(
                        client_id=client.id,
                        job_id=job.id,
                        kind=KIND_SUPPLIER_SEARCH,
                        operation=OP_RESERVE,
                        units=1,
                    ),
                ]
            )
            db.commit()

            removed = jobs.cleanup_expired_jobs(
                db,
                SimpleNamespace(
                    completed_job_retention_days=1,
                    failed_job_retention_days=1,
                    storage_retention_days=1,
                ),
            )

            self.assertEqual(removed, 0)
            self.assertIsNotNone(db.get(Job, job.id))
            self.assertEqual(
                [row.operation for row in db.query(BillingTransaction).filter(BillingTransaction.job_id == job.id).all()],
                [OP_RESERVE],
            )
        finally:
            db.close()

    def test_supplier_count_message_hides_internal_target_when_underfilled(self) -> None:
        message = _supplier_count_message("Частично готово", 8, 15)

        self.assertEqual(
            message,
            "Частично готово: отобрано кандидатов 8. Уровень технического совпадения указан в отчёте",
        )
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

    def test_create_job_blocks_manual_minprom_policy_when_registry_not_ready(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_job_dir = jobs.job_dir
        original_preflight = jobs.minprom_registry_preflight_error
        try:
            with tempfile.TemporaryDirectory() as tmp:
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                jobs.minprom_registry_preflight_error = lambda policy: (
                    "Локальный реестр Минпромторга не готов" if policy == jobs.SUPPLIER_POLICY_MINPROM_ONLY else ""
                )

                with self.assertRaisesRegex(ValueError, "Локальный реестр Минпромторга не готов"):
                    jobs.create_job(
                        db,
                        client_id=None,
                        mode=MODE_SUPPLIER_SEARCH,
                        title="ТЗ",
                        target_suppliers=10,
                        files=[("tz.txt", b"nasos")],
                        supplier_search_policy=jobs.SUPPLIER_POLICY_MINPROM_ONLY,
                    )

                self.assertEqual(db.query(Job).count(), 0)
        finally:
            jobs.job_dir = original_job_dir
            jobs.minprom_registry_preflight_error = original_preflight
            db.close()

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

    def test_successful_reparse_clears_previous_file_error(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_session = jobs.SessionLocal
        original_job_dir = jobs.job_dir
        original_settings = jobs.get_or_create_settings
        original_extract_text = jobs.document_parser.extract_text
        original_process_report = jobs._process_procurement_report

        def fake_extract_text(_path: str, _options: dict) -> tuple[str, str]:
            return "Техническое задание: поставка оборудования", "ok"

        def fake_process_report(db_arg, job_arg: Job, _settings, _context: str) -> None:
            job_arg.status = "completed"
            job_arg.progress = 100
            job_arg.message = "Готово"
            job_arg.completed_at = now_utc()
            db_arg.commit()

        with tempfile.TemporaryDirectory() as tmp:
            jobs.SessionLocal = Session
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.get_or_create_settings = lambda _db: SimpleNamespace(document_settings_json="{}")
            jobs.document_parser.extract_text = fake_extract_text
            jobs._process_procurement_report = fake_process_report
            try:
                job = jobs.create_job(
                    db,
                    client_id=None,
                    mode="procurement_report",
                    title="Тест",
                    target_suppliers=25,
                    files=[("ТЗ.odt", b"broken-before")],
                    sources=[],
                )
                job_id = job.id
                stored_file = db.query(JobFile).filter(JobFile.job_id == job_id).one()
                stored_file.parse_status = "error:OSError"
                stored_file.error = "error:OSError: pandoc"
                db.commit()

                jobs._process_job_sync(job_id)
                db.expire_all()
                refreshed_file = db.query(JobFile).filter(JobFile.job_id == job_id).one()
            finally:
                jobs.SessionLocal = original_session
                jobs.job_dir = original_job_dir
                jobs.get_or_create_settings = original_settings
                jobs.document_parser.extract_text = original_extract_text
                jobs._process_procurement_report = original_process_report
                db.close()

        self.assertEqual(refreshed_file.parse_status, "ok")
        self.assertEqual(refreshed_file.error, "")

    def test_result_stem_keeps_cyrillic_output_filename_under_filesystem_limit(self) -> None:
        long_title = "Техническое задание " + "канат стальной оцинкованный " * 12
        long_subject = "поставка канатов грузовых и такелажной продукции " * 10
        job = Job(mode=MODE_SUPPLIER_SEARCH, status="completed", title=long_title)

        stem = _result_stem(job, long_subject)
        filename = _result_filename("suppliers", stem, ".xlsx")

        self.assertLessEqual(len(filename.encode("utf-8")), 255)
        self.assertTrue(stem)

    def test_combined_registry_only_mode_completes_when_underfilled(self) -> None:
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
            self.assertEqual(supplier_search_policy, jobs.SUPPLIER_POLICY_MINPROM_ONLY)
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
                job = Job(
                    mode=MODE_ANALYSIS_AND_SUPPLIERS,
                    status="running",
                    title="ТЗ сварка",
                    target_suppliers=2,
                    supplier_search_policy=jobs.SUPPLIER_POLICY_MINPROM_ONLY,
                )
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

    def test_combined_mode_keeps_browser_failure_reason_when_analysis_warns(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_report = jobs.generate_procurement_report
        original_suppliers = jobs.discover_suppliers
        original_supplier_context = jobs.extract_supplier_search_context
        original_quote_builder = jobs.build_quote_request_markdown_with_ai
        original_job_dir = jobs.job_dir

        async def fake_report(_settings, _context: str) -> ReportGenerationResult:
            return ReportGenerationResult(
                report="# Анализ\nПредмет закупки: Канат стальной",
                ai_used=True,
                warning="Нужно проверить настройки ИИ.",
            )

        async def fake_supplier_context(_settings, _context: str) -> str:
            return "ТЗ: канат стальной"

        async def fake_suppliers(_settings, _context: str, _target: int, *, progress_callback=None, supplier_search_policy="normal"):
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
                    "browser_failures": {"count": 1, "failures": []},
                    "procurement_profile": {"items": []},
                },
            )

        async def fake_quote_builder(*_args, **_kwargs) -> str:
            return "# Запрос КП"

        with tempfile.TemporaryDirectory() as tmp:
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.generate_procurement_report = fake_report
            jobs.extract_supplier_search_context = fake_supplier_context
            jobs.discover_suppliers = fake_suppliers
            jobs.build_quote_request_markdown_with_ai = fake_quote_builder
            try:
                job = Job(mode=MODE_ANALYSIS_AND_SUPPLIERS, status="running", title="ТЗ канат", target_suppliers=1)
                db.add(job)
                db.commit()

                _process_analysis_and_suppliers(db, job, SimpleNamespace(), "context")
                db.refresh(job)
            finally:
                jobs.generate_procurement_report = original_report
                jobs.discover_suppliers = original_suppliers
                jobs.extract_supplier_search_context = original_supplier_context
                jobs.build_quote_request_markdown_with_ai = original_quote_builder
                jobs.job_dir = original_job_dir
                db.close()

        self.assertEqual(job.status, "needs_review")
        self.assertIn("нужна проверка ИИ-настроек", job.message)
        self.assertIn("Часть сайтов временно не удалось проверить", job.message)
        self.assertIn("Нужно проверить настройки ИИ.", job.error)
        self.assertIn("Часть сайтов не удалось проверить", job.error)

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

    def test_registry_only_supplier_search_completes_when_underfilled(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_suppliers = jobs.discover_suppliers
        original_quote_builder = jobs.build_quote_request_markdown_with_ai
        original_job_dir = jobs.job_dir

        async def fake_suppliers(_settings, _context: str, _target: int, *, progress_callback=None, excluded_suppliers=None, supplier_search_policy="normal"):
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
                    "browser_failures": {"count": 2, "failures": []},
                    "procurement_profile": {"summary": "Канат стальной", "items": []},
                },
            )

        async def fake_quote_builder(*_args, **_kwargs) -> str:
            return "# Запрос КП\n\nПросим направить предложение."

        with tempfile.TemporaryDirectory() as tmp:
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.discover_suppliers = fake_suppliers
            jobs.build_quote_request_markdown_with_ai = fake_quote_builder
            try:
                results = {}
                for policy in (jobs.SUPPLIER_POLICY_NORMAL, jobs.SUPPLIER_POLICY_MINPROM_ONLY):
                    job = Job(
                        mode=MODE_SUPPLIER_SEARCH,
                        status="running",
                        title="ТЗ канат",
                        target_suppliers=2,
                        supplier_search_policy=policy,
                    )
                    db.add(job)
                    db.commit()
                    db.refresh(job)

                    _process_supplier_search(
                        db,
                        job,
                        SimpleNamespace(has_active_ai_provider=False, allow_partial_supplier_reports=True),
                        "ТЗ: нужен канат стальной",
                    )
                    db.refresh(job)
                    results[policy] = (job.status, job.message, job.error)
            finally:
                jobs.discover_suppliers = original_suppliers
                jobs.build_quote_request_markdown_with_ai = original_quote_builder
                jobs.job_dir = original_job_dir
                db.close()

        normal_status, normal_message, normal_error = results[jobs.SUPPLIER_POLICY_NORMAL]
        self.assertEqual(normal_status, jobs.STATUS_AWAITING_CUSTOMER_CONFIRMATION)
        self.assertIn("Часть сайтов временно не удалось проверить", normal_message)
        self.assertIn("временной технической ошибки", normal_error)

        registry_status, registry_message, registry_error = results[jobs.SUPPLIER_POLICY_MINPROM_ONLY]
        self.assertEqual(registry_status, "completed")
        self.assertEqual(
            registry_message,
            "Готово: отобрано кандидатов 1. Уровень технического совпадения указан в отчёте",
        )
        self.assertEqual(registry_error, "")

    def test_browser_start_failure_marks_job_failed_with_clear_safe_reason(self) -> None:
        original_session = jobs.SessionLocal
        original_job_dir = jobs.job_dir
        original_settings = jobs.get_or_create_settings
        original_extract_text = jobs.document_parser.extract_text
        original_suppliers = jobs.discover_suppliers

        async def failed_browser_search(*_args, **_kwargs):
            raise RuntimeError("Не удалось запустить проверку сайтов. Попробуйте повторить задачу.")

        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(
                f"sqlite:///{Path(tmp) / 'jobs.db'}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            db = Session()
            jobs.SessionLocal = Session
            jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
            jobs.get_or_create_settings = lambda _db: SimpleNamespace(document_settings_json="{}")
            jobs.document_parser.extract_text = lambda _path, _options: (
                "Техническое задание: требуется поставка каната стального оцинкованного для производственных работ.",
                "ok",
            )
            jobs.discover_suppliers = failed_browser_search
            try:
                job = jobs.create_job(
                    db,
                    client_id=None,
                    mode=MODE_SUPPLIER_SEARCH,
                    title="ТЗ канат",
                    target_suppliers=1,
                    files=[("ТЗ.txt", b"supplier search")],
                    sources=[],
                )
                jobs._process_job_sync(job.id)
                db.expire_all()
                refreshed = db.get(Job, job.id)
                assert refreshed is not None
                evidence = json.loads(Path(refreshed.evidence_path).read_text(encoding="utf-8"))
            finally:
                jobs.SessionLocal = original_session
                jobs.job_dir = original_job_dir
                jobs.get_or_create_settings = original_settings
                jobs.document_parser.extract_text = original_extract_text
                jobs.discover_suppliers = original_suppliers
                db.close()

        self.assertEqual(refreshed.status, "failed")
        self.assertEqual(refreshed.error, "Не удалось запустить проверку сайтов. Попробуйте повторить задачу.")
        self.assertEqual(evidence["error"]["message"], refreshed.error)
        self.assertNotIn("token=", refreshed.error)

    def test_supplier_search_stops_blocked_discovery_after_database_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "jobs.db"
            engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            setup_db = Session()
            cancel_db = Session()
            original_suppliers = jobs.discover_suppliers
            original_session_local = jobs.SessionLocal
            original_job_dir = jobs.job_dir
            discovery_started = threading.Event()
            discovery_cancelled = threading.Event()
            worker_cancelled = threading.Event()
            worker_finished = threading.Event()
            worker_errors: list[BaseException] = []
            loop_holder: list[asyncio.AbstractEventLoop] = []
            blocker_holder: list[asyncio.Event] = []
            worker_thread: threading.Thread | None = None

            async def blocked_discovery(_settings, _context: str, _target: int, *, progress_callback=None, excluded_suppliers=None, supplier_search_policy="normal"):
                blocker = asyncio.Event()
                blocker_holder.append(blocker)
                loop_holder.append(asyncio.get_running_loop())
                discovery_started.set()
                try:
                    await blocker.wait()
                except asyncio.CancelledError:
                    discovery_cancelled.set()
                    raise
                return [], {"ai_used": True, "procurement_profile": {"items": []}}

            try:
                jobs.discover_suppliers = blocked_discovery
                jobs.SessionLocal = Session
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                job = Job(mode=MODE_SUPPLIER_SEARCH, status="running", title="ТЗ", target_suppliers=1)
                setup_db.add(job)
                setup_db.commit()
                job_id = job.id

                def run_worker() -> None:
                    worker_db = Session()
                    try:
                        worker_job = worker_db.get(Job, job_id)
                        assert worker_job is not None
                        _process_supplier_search(
                            worker_db,
                            worker_job,
                            SimpleNamespace(has_active_ai_provider=False, allow_partial_supplier_reports=False),
                            "ТЗ: нужен канат стальной",
                        )
                    except JobCancelledError:
                        worker_cancelled.set()
                    except BaseException as exc:
                        worker_errors.append(exc)
                    finally:
                        worker_db.close()
                        worker_finished.set()

                worker_thread = threading.Thread(target=run_worker, daemon=True)
                worker_thread.start()
                self.assertTrue(discovery_started.wait(1))

                cancelled_job = cancel_db.get(Job, job_id)
                assert cancelled_job is not None
                cancelled_job.status = "cancelled"
                cancel_db.commit()

                self.assertTrue(
                    worker_finished.wait(2),
                    "После отмены в базе поиск должен остановиться без ожидания следующего сообщения о прогрессе.",
                )
                self.assertTrue(discovery_cancelled.is_set())
                self.assertTrue(worker_cancelled.is_set())
                self.assertEqual(worker_errors, [])
            finally:
                if loop_holder and blocker_holder and not loop_holder[0].is_closed():
                    loop_holder[0].call_soon_threadsafe(blocker_holder[0].set)
                if worker_thread is not None:
                    worker_thread.join(timeout=2)
                jobs.discover_suppliers = original_suppliers
                jobs.SessionLocal = original_session_local
                jobs.job_dir = original_job_dir
                cancel_db.close()
                setup_db.close()

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

    def test_claim_next_job_skips_client_that_already_has_active_jobs_at_limit(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        now = now_utc()
        try:
            active_a1 = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="active-a-1",
                created_at=now - timedelta(minutes=25),
                updated_at=now,
            )
            active_a2 = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="active-a-2",
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
            db.add_all([active_a1, active_a2, pending_a, pending_b])
            db.commit()
            pending_b_id = pending_b.id

            claimed = claim_next_job(db, worker_id="test-worker", max_running_jobs_per_client=2)
            db.refresh(pending_a)
            db.refresh(pending_b)

            self.assertEqual(claimed, pending_b_id)
            self.assertEqual(pending_a.status, "pending")
            self.assertEqual(pending_b.status, "running")
        finally:
            db.close()

    def test_claim_next_job_allows_second_job_for_client_when_limit_is_two(self) -> None:
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
            pending_a_id = pending_a.id

            claimed = claim_next_job(db, worker_id="test-worker", max_running_jobs_per_client=2)
            db.refresh(pending_a)
            db.refresh(pending_b)

            self.assertEqual(claimed, pending_a_id)
            self.assertEqual(pending_a.status, "running")
            self.assertEqual(pending_b.status, "pending")
        finally:
            db.close()

    def test_claim_next_job_reaches_other_clients_after_large_blocked_prefix(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        now = now_utc()
        try:
            active_a1 = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="active-a-1",
                created_at=now - timedelta(minutes=210),
                updated_at=now,
            )
            active_a2 = Job(
                client_id="client-a",
                mode="supplier_search",
                status="running",
                title="active-a-2",
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
            db.add_all([active_a1, active_a2])
            db.add_all(blocked_a)
            db.add(pending_b)
            db.commit()
            pending_b_id = pending_b.id

            claimed = claim_next_job(db, worker_id="test-worker", max_running_jobs_per_client=2)
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

    def test_additional_registry_fallback_uses_extra_billing_kind_without_new_ai(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_suppliers = jobs.discover_suppliers
        original_quote_builder = jobs.build_quote_request_markdown_with_ai
        original_job_dir = jobs.job_dir
        ai_quote_calls = 0

        rows = [
            {
                "company_name": "Поставщик без записи",
                "site": "https://supplier.example",
                "phone": "+7 999 111 22 33",
                "email": "sales@supplier.example",
                "comments": "Проверен официальный сайт и контакты.",
                "evidence_status": "verified",
                "match_level": "exact",
                "product_fit": "exact",
                "product": "Волоконный усилитель",
                "supplier_search_policy": jobs.SUPPLIER_POLICY_MINPROM_ONLY,
                "supplier_search_origin": "ordinary_fallback",
                "minprom_registry_required": True,
                "minprom_registry_status": "empty",
                "minprom_registry_match": {"matched": False},
            }
        ]

        async def fake_suppliers(*_args, **_kwargs):
            return (
                [],
                {
                    "ai_used": True,
                    "procurement_profile": {"items": [{"name": "Волоконный усилитель"}]},
                    "minprom_registry": {"status": "empty"},
                    "registry_result": {"status": "empty", "verified_count": 0},
                    "non_registry_alternative": {
                        "available": True,
                        "verified_count": 1,
                        "verified_rows": rows,
                        "reason_code": "registry_no_relevant_entries",
                    },
                },
            )

        async def forbidden_ai_quote(*_args, **_kwargs):
            nonlocal ai_quote_calls
            ai_quote_calls += 1
            raise AssertionError("fallback must not call AI quote builder")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                jobs.discover_suppliers = fake_suppliers
                jobs.build_quote_request_markdown_with_ai = forbidden_ai_quote
                client = Client(id="fallback-client", telegram_id="fallback-user")
                job = Job(
                    id="fallback-job",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="running",
                    title="ТЗ",
                    target_suppliers=10,
                    supplier_search_policy=jobs.SUPPLIER_POLICY_MINPROM_ONLY,
                    supplier_search_run_type=jobs.SUPPLIER_RUN_ADDITIONAL,
                )
                db.add_all(
                    [
                        client,
                        job,
                        BillingTransaction(
                            client_id=client.id,
                            job_id=job.id,
                            kind=KIND_SUPPLIER_SEARCH_EXTRA,
                            operation=OP_RESERVE,
                            units=1,
                        ),
                    ]
                )
                db.commit()

                _process_supplier_search(db, job, SimpleNamespace(allow_partial_supplier_reports=True), "ТЗ на усилитель")
                db.refresh(job)
                evidence = json.loads(Path(job.evidence_path).read_text(encoding="utf-8"))
                supplier_rows = db.query(SupplierResult).filter(SupplierResult.job_id == job.id).all()
                transactions = db.query(BillingTransaction).filter(BillingTransaction.job_id == job.id).all()

                self.assertEqual(job.status, "awaiting_customer_confirmation")
                self.assertEqual(job.confirmation_kind, "registry_fallback")
                self.assertEqual(job.confirmation_outcome, "pending")
                self.assertEqual(job.active_output_manifest, "locked_offer")
                self.assertEqual(job.result_path, "")
                self.assertEqual(job.verified_count, 1)
                self.assertEqual(len(supplier_rows), 1)
                self.assertEqual([row.operation for row in transactions], [OP_RESERVE])
                self.assertEqual([row.kind for row in transactions], [KIND_SUPPLIER_SEARCH_EXTRA])
                self.assertEqual(ai_quote_calls, 0)
                self.assertTrue(Path(evidence["output_manifests"]["full"]["archive_path"]).exists())
                self.assertEqual(
                    evidence["output_manifests"]["full"]["entitlements"],
                    [KIND_SUPPLIER_SEARCH_EXTRA],
                )
                self.assertEqual(
                    {item["billing_kind"] for item in evidence["output_files"]},
                    {KIND_SUPPLIER_SEARCH_EXTRA},
                )
                quote_text_path = next(
                    item["content_path"] for item in evidence["output_files"] if item["kind"] == "quote_request"
                )
                self.assertIn("Подтверждение соответствия", Path(quote_text_path).read_text(encoding="utf-8"))
        finally:
            jobs.discover_suppliers = original_suppliers
            jobs.build_quote_request_markdown_with_ai = original_quote_builder
            jobs.job_dir = original_job_dir
            db.close()

    def test_combined_registry_fallback_prebuilds_full_and_analysis_only_manifests(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_report = jobs.generate_procurement_report
        original_suppliers = jobs.discover_suppliers
        original_supplier_context = jobs.extract_supplier_search_context
        original_quote_builder = jobs.build_quote_request_markdown_with_ai
        original_job_dir = jobs.job_dir

        async def fake_report(_settings, _context: str) -> ReportGenerationResult:
            return ReportGenerationResult(report="# Анализ\nПредмет закупки: Волоконный усилитель", ai_used=True)

        async def fake_supplier_context(_settings, _context: str) -> str:
            return "ТЗ на волоконный усилитель"

        fallback_row = {
            "company_name": "Поставщик",
            "site": "https://supplier.example",
            "phone": "+7 999 111 22 33",
            "email": "sales@supplier.example",
            "evidence_status": "verified",
            "match_level": "exact",
            "product_fit": "exact",
            "product": "Волоконный усилитель",
            "supplier_search_policy": jobs.SUPPLIER_POLICY_MINPROM_ONLY,
            "supplier_search_origin": "ordinary_fallback",
            "minprom_registry_required": True,
            "minprom_registry_status": "ok",
            "minprom_registry_match": {"matched": False},
        }

        async def fake_suppliers(*_args, **_kwargs):
            return (
                [],
                {
                    "ai_used": True,
                    "procurement_profile": {"items": [{"name": "Волоконный усилитель"}]},
                    "non_registry_alternative": {
                        "available": True,
                        "verified_count": 1,
                        "verified_rows": [fallback_row],
                        "reason_code": "registry_entries_no_supplier_match",
                    },
                },
            )

        async def forbidden_ai_quote(*_args, **_kwargs):
            raise AssertionError("combined fallback must not call AI quote builder")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                jobs.generate_procurement_report = fake_report
                jobs.extract_supplier_search_context = fake_supplier_context
                jobs.discover_suppliers = fake_suppliers
                jobs.build_quote_request_markdown_with_ai = forbidden_ai_quote
                job = Job(
                    id="combined-fallback-job",
                    mode=MODE_ANALYSIS_AND_SUPPLIERS,
                    status="running",
                    title="Закупка",
                    target_suppliers=10,
                    supplier_search_policy=jobs.SUPPLIER_POLICY_MINPROM_ONLY,
                )
                db.add(job)
                db.commit()

                _process_analysis_and_suppliers(db, job, SimpleNamespace(), "context")
                db.refresh(job)
                evidence = json.loads(Path(job.evidence_path).read_text(encoding="utf-8"))

                self.assertEqual(job.status, "awaiting_customer_confirmation")
                self.assertEqual(job.confirmation_kind, "registry_fallback")
                self.assertEqual(job.verified_count, 1)
                self.assertEqual(job.result_path, "")
                self.assertEqual(set(evidence["output_manifests"]), {"full", "analysis_only"})
                self.assertEqual(
                    [item["kind"] for item in evidence["output_manifests"]["analysis_only"]["files"]],
                    ["analysis", "quote_request"],
                )
                self.assertTrue(Path(evidence["output_manifests"]["full"]["archive_path"]).exists())
                self.assertTrue(Path(evidence["output_manifests"]["analysis_only"]["archive_path"]).exists())
        finally:
            jobs.generate_procurement_report = original_report
            jobs.discover_suppliers = original_suppliers
            jobs.extract_supplier_search_context = original_supplier_context
            jobs.build_quote_request_markdown_with_ai = original_quote_builder
            jobs.job_dir = original_job_dir
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

    def test_extract_yandex_job_metrics_handles_nested_combo_evidence(self) -> None:
        evidence = {
            "mode": "analysis_and_suppliers",
            "supplier_search": {
                "search": {
                    "yandex_requests_count": 34,
                    "yandex_cost_rub": 1.36,
                },
                "recovery_rounds": [
                    {
                        "search": {
                            "yandex_requests_count": 36,
                            "yandex_cost_rub": 1.44,
                        }
                    }
                ],
            },
        }
        reqs, cost = extract_yandex_job_metrics(evidence, price_per_request=0.04)
        self.assertEqual(reqs, 70)
        self.assertEqual(cost, 2.80)


if __name__ == "__main__":
    unittest.main()

