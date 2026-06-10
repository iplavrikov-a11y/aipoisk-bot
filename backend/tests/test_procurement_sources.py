from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import app.db as app_db
import app.jobs as jobs
import app.tenderplan as tenderplan
from app.db import Base
from app.jobs import create_job
from app.models import JobSource
from app.procurement_sources import (
    SOURCE_KIND_OFFICIAL,
    SOURCE_KIND_PROCUREMENT_URL,
    SOURCE_KIND_TENDERPLAN_NOTICE,
    build_source_context_block,
    candidate_source_urls,
    classify_source_url,
    extract_notice_numbers,
    extract_source_urls,
    fetch_source_context_sync,
    official_notice_number_from_url,
    official_followup_urls_from_pages,
    source_label,
    source_payloads_from_text,
)
from app.tenderplan import TenderplanDownloadedFile, TenderplanFetchResult


class ProcurementSourceTests(unittest.TestCase):
    def test_init_db_creates_job_sources_table(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        original_engine = app_db.engine
        try:
            app_db.engine = engine
            app_db.init_db()
            inspector = inspect(engine)
        finally:
            app_db.engine = original_engine

        self.assertTrue(inspector.has_table("job_sources"))

    def test_extract_source_urls_accepts_eis_and_commercial_platform_links(self) -> None:
        urls = extract_source_urls(
            "ЕИС: https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=12345, "
            "площадка: https://www.b2b-center.ru/market/view.html?id=777."
        )

        self.assertEqual(
            urls,
            [
                "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=12345",
                "https://www.b2b-center.ru/market/view.html?id=777",
            ],
        )

    def test_classify_source_url_separates_eis_from_other_procurement_sites(self) -> None:
        self.assertEqual(classify_source_url("https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=12345"), SOURCE_KIND_OFFICIAL)
        self.assertEqual(classify_source_url("https://etp.example.ru/procedure/123"), SOURCE_KIND_PROCUREMENT_URL)

    def test_extract_notice_numbers_accepts_44fz_and_223fz_numbers(self) -> None:
        numbers = extract_notice_numbers(
            "44-ФЗ: 0371100005626000040; 223-ФЗ: 32615728276; "
            "ИКЗ 261710600552071060100100350012620244 не источник."
        )

        self.assertEqual(numbers, ["0371100005626000040", "32615728276"])

    def test_extract_notice_numbers_ignores_numbers_inside_urls(self) -> None:
        numbers = extract_notice_numbers(
            "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0371100005626000040 "
            "и отдельно 0371100005626000041"
        )

        self.assertEqual(numbers, ["0371100005626000041"])

    def test_source_payloads_include_tenderplan_notice_for_plain_number(self) -> None:
        payloads = source_payloads_from_text("Прошу разобрать закупку 0371100005626000040")

        self.assertEqual(
            payloads,
            [
                {
                    "kind": SOURCE_KIND_TENDERPLAN_NOTICE,
                    "label": "Закупка 0371100005626000040",
                    "value": "0371100005626000040",
                }
            ],
        )
        self.assertEqual(source_label("32615728276"), "Закупка 32615728276")

    def test_official_notice_number_from_url_accepts_eis_query_variants(self) -> None:
        self.assertEqual(
            official_notice_number_from_url("https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0168300005126000012"),
            "0168300005126000012",
        )
        self.assertEqual(
            official_notice_number_from_url("https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616035046"),
            "32616035046",
        )
        self.assertEqual(
            official_notice_number_from_url("https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber=0372200127526000030"),
            "0372200127526000030",
        )
        self.assertEqual(official_notice_number_from_url("https://etp.example.ru/procedure/0168300005126000012"), "")

    def test_official_eis_fetch_uses_notice_number_source_first(self) -> None:
        original_fetch = tenderplan.fetch_tenderplan_source_sync
        calls: list[str] = []

        def fake_fetch(notice_number: str) -> TenderplanFetchResult:
            calls.append(notice_number)
            return TenderplanFetchResult(
                ok=True,
                status="ok",
                context="Карточка закупки:\n- Наименование: Поставка сотового поликарбоната\n",
                notice_number=notice_number,
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

        try:
            tenderplan.fetch_tenderplan_source_sync = fake_fetch
            result = fetch_source_context_sync(
                SOURCE_KIND_OFFICIAL,
                "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0168300005126000012",
            )
        finally:
            tenderplan.fetch_tenderplan_source_sync = original_fetch

        self.assertTrue(result.ok)
        self.assertEqual(calls, ["0168300005126000012"])
        self.assertIn("Поставка сотового поликарбоната", result.context)
        self.assertEqual(result.downloaded_files[0].filename, "Техническое задание.docx")

    def test_eis_candidate_urls_prioritize_original_notice_kind_pages(self) -> None:
        urls = candidate_source_urls(
            "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0317400001026000049",
            SOURCE_KIND_OFFICIAL,
        )

        self.assertIn("/notice/zk20/view/common-info.html", urls[0])
        self.assertIn("/notice/zk20/view/lot-list.html", urls[1])
        self.assertIn("/notice/zk20/view/documents.html", urls[2])
        self.assertIn("/notice/printForm/view.html", urls[3])

    def test_source_context_block_keeps_generic_platform_as_procurement_source(self) -> None:
        block = build_source_context_block(
            kind=SOURCE_KIND_PROCUREMENT_URL,
            url="https://etp.example.ru/procedure/123",
            text="Поставка стального каната. НМЦК 100000 рублей.",
        )

        self.assertIn("ССЫЛКА НА ПЛОЩАДКУ ЗАКУПКИ", block)
        self.assertIn("https://etp.example.ru/procedure/123", block)
        self.assertIn("Поставка стального каната", block)

    def test_official_eis_context_prioritizes_card_fields(self) -> None:
        block = build_source_context_block(
            kind=SOURCE_KIND_OFFICIAL,
            url="https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0317400001026000049",
            text="Заказчик: ФГБУ. ИНН 1234567890. Срок подачи заявок 10.06.2026.",
        )

        self.assertIn("ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ: ЕИС", block)
        self.assertIn("заказчика", block)
        self.assertIn("ИНН/КПП", block)
        self.assertIn("сроков подачи заявок", block)
        self.assertIn("Не пиши 'данных недостаточно'", block)

    def test_tenderplan_context_block_marks_notice_as_primary_source(self) -> None:
        block = build_source_context_block(
            kind=SOURCE_KIND_TENDERPLAN_NOTICE,
            url="0371100005626000040",
            text="Карточка закупки:\n- НМЦК/цена: 100 000 руб.",
        )

        self.assertIn("ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ", block)
        self.assertIn("основной источник критичных полей", block)
        self.assertIn("Разъяснения и ответы заказчика", block)

    def test_official_followup_urls_include_customer_organization_page(self) -> None:
        urls = official_followup_urls_from_pages(
            [
                {
                    "text": (
                        "Заказчик https://zakupki.gov.ru/epz/organization/view/info.html?organizationCode=03174000010 "
                        "Печатная форма https://zakupki.gov.ru/epz/order/notice/printForm/view.html?entityType=notice&entityId=43142066&source="
                    )
                }
            ]
        )

        self.assertEqual(
            urls,
            [
                "https://zakupki.gov.ru/epz/organization/view/info.html?organizationCode=03174000010",
                "https://zakupki.gov.ru/epz/order/notice/printForm/view.html?entityType=notice&entityId=43142066&source=",
            ],
        )

    def test_create_job_persists_source_urls_without_files_for_report_mode(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_job_dir = jobs.job_dir
        try:
            with tempfile.TemporaryDirectory() as tmp:
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                job = create_job(
                    db,
                    client_id=None,
                    mode="procurement_report",
                    title="source-only",
                    target_suppliers=3,
                    files=[],
                    sources=[{"kind": SOURCE_KIND_PROCUREMENT_URL, "value": "https://etp.example.ru/procedure/123"}],
                )

                db.refresh(job)
                sources = db.query(JobSource).filter(JobSource.job_id == job.id).all()
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertEqual(job.file_count, 0)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].kind, SOURCE_KIND_PROCUREMENT_URL)
        self.assertEqual(sources[0].value, "https://etp.example.ru/procedure/123")

    def test_create_job_rejects_procurement_source_for_supplier_search(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_job_dir = jobs.job_dir
        try:
            with tempfile.TemporaryDirectory() as tmp:
                jobs.job_dir = lambda job_id: Path(tmp) / "jobs" / job_id
                with self.assertRaisesRegex(ValueError, "Режим поиска поставщиков"):
                    create_job(
                        db,
                        client_id=None,
                        mode="supplier_search",
                        title="source-only",
                        target_suppliers=3,
                        files=[],
                        sources=[{"kind": SOURCE_KIND_TENDERPLAN_NOTICE, "value": "0371100005626000040"}],
                    )
                sources = db.query(JobSource).all()
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertEqual(sources, [])


if __name__ == "__main__":
    unittest.main()
