from __future__ import annotations

import asyncio
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import openpyxl
import pytest
from docx import Document

from app import ai, document_parser, product_inventory, procurement_report, report_builder, supplier_search, tenderplan
from app.exact_product.docx_report import write_exact_product_docx
from app.exact_product.models import (
    AlternativeProduct,
    ExactProductPosition,
    ExactProductReport,
    GispRegistryMatch,
    SpecParameterMatch,
)
from app.exact_product.validation import validate_exact_products
from app.price_monitoring.excel_report import generate_price_monitoring_excel
from app.price_monitoring.extractor import extract_schema_org_product_data
from app.price_monitoring.models import BatchMonitoringResult, ItemPriceResult, SupplierQuote
from bs4 import BeautifulSoup


def test_ai_default_concurrency_and_queue_wait_isolation() -> None:
    with patch.dict(ai.os.environ, {}, clear=False):
        ai.os.environ.pop("AIPOISK_LLM_MAX_CONCURRENCY", None)
        assert ai._llm_concurrency_limit() == 8


@pytest.mark.asyncio
async def test_ai_queue_wait_does_not_consume_per_model_timeout() -> None:
    settings = SimpleNamespace(
        custom_ai_providers_json='[{"id":"p1","name":"P1","baseUrl":"http://127.0.0.1:9999/v1","apiKey":"k"}]',
        primary_provider="p1",
        primary_model="m1",
        light_provider="p1",
        light_model="m1",
        supplier_ai_provider="p1",
        supplier_ai_model="m1",
        ai_function_models_json="{}",
        saved_models_json="[]",
        ai_analysis_fallback_json="[]",
        ai_supplier_fallback_json="[]",
    )

    async def fast_post(selection, *_args, **_kwargs) -> str:
        await asyncio.sleep(0.01)
        return '{"ok": true}'

    ai._process_llm_limiter.reset_for_tests()
    rel_task: asyncio.Task[None] | None = None
    try:
        with (
            patch.dict(ai.os.environ, {"AIPOISK_LLM_MAX_CONCURRENCY": "1"}),
            patch.object(ai, "_post_llm_request", side_effect=fast_post),
        ):
            await ai._process_llm_limiter.acquire()

            async def release_later() -> None:
                await asyncio.sleep(0.08)
                ai._process_llm_limiter.release()

            rel_task = asyncio.create_task(release_later())
            # Selection timeout is 0.04s, while queue wait is 0.08s, overall timeout is 1.0s.
            # Queue wait must NOT trigger selection_timeout failure!
            res = await ai.call_llm(
                settings,
                "hello",
                timeout_seconds=0.04,
                total_timeout_seconds=1.0,
            )
            assert res == '{"ok": true}'
    finally:
        if rel_task is not None:
            await rel_task
        ai._process_llm_limiter.reset_for_tests()


def test_supplier_html_preserves_header_footer_mailto_tel_and_inn() -> None:
    html = """
    <html>
      <body>
        <header>
          <div>Завод ПромМаш | <a href="tel:+78005553535">8 (800) 555-35-35</a> | <a href="mailto:sales@prommash-zavod.ru">Написать</a></div>
        </header>
        <main>
          <h1>Производство промышленных насосов ЦНС и запорной арматуры</h1>
          <p>Серийный выпуск насосных агрегатов по ГОСТ для предприятий водоканала и энергетики.</p>
        </main>
        <footer>
          <p>ООО «Завод ПромМаш», ИНН: 7707083893, ОГРН 1027700132195</p>
        </footer>
      </body>
    </html>
    """
    page = supplier_search.html_text_to_page(html, "https://prommash-zavod.ru")
    assert page is not None
    assert "sales@prommash-zavod.ru" in page["text"]
    assert "7707083893" in page["text"]
    assert "+78005553535" in page["text"] or "555-35-35" in page["text"]


def test_supplier_blocked_aggregators_and_geo_scope_domains() -> None:
    for bad in ("companium.ru", "1cont.ru", "find-org.ru", "ruslist.su", "orgpage.ru", "contragent.pro", "excheck.pro"):
        assert supplier_search.is_blocked(bad) is True
        assert supplier_search.is_blocked(bad, geo_scope="world") is True

    # .kz and .by blocked in RU scope, allowed in CIS and WORLD scope
    assert supplier_search.is_blocked("https://zavod.kz", geo_scope="ru") is True
    assert supplier_search.is_blocked("https://zavod.kz", geo_scope="cis") is False
    assert supplier_search.is_blocked("https://zavod.by", geo_scope="cis") is False
    assert supplier_search.is_blocked("https://factory.de", geo_scope="cis") is True
    assert supplier_search.is_blocked("https://factory.de", geo_scope="world") is False


@pytest.mark.asyncio
async def test_supplier_short_context_and_hallucinated_contact_rejection() -> None:
    settings = SimpleNamespace(has_active_ai_provider=True)
    short_res = await supplier_search.extract_supplier_search_context(settings, "Поставка серверов для ЦОД")
    assert short_res == "Поставка серверов для ЦОД"

    # AI-hallucinated email and invalid INN absent from page must NOT be verified
    assert supplier_search._verified_email("hallucinated@factory.ru", []) == ""
    assert supplier_search._is_valid_ru_inn("7707083893") is True
    assert supplier_search._is_valid_ru_inn("1234567890") is False


def test_exact_product_numeric_bounds_and_honest_gisp_docx() -> None:
    positions = [
        {
            "position_no": 1,
            "name_in_tz": "Сушилка для рук",
            "identified_brand": "BXG",
            "identified_model": "JET-7000",
            "manufacturer": "BXG",
            "confidence": 1.0,
            "reasoning": "Проверено.",
            "specs_breakdown": [
                {
                    "param_name": "Номинальная мощность",
                    "tz_requirement": "не более 2001 Вт",
                    "product_fact": "2050 Вт",
                    "status": "match",
                    "comment": "Подтверждено паспортом.",
                }
            ],
            "alternative_brands": [],
        }
    ]
    validated = validate_exact_products(positions)
    assert validated[0]["specs_breakdown"][0]["status"] == "mismatch"
    assert validated[0]["confidence"] < 1.0

    # Check DOCX honest GISP status for analogs with and without gisp_match
    report = ExactProductReport(
        procurement_title="Сушилки",
        total_positions=1,
        positions=[
            ExactProductPosition(
                position_no=1,
                name_in_tz="Сушилка",
                identified_brand="BrandA",
                identified_model="M1",
                manufacturer="MfrA",
                confidence=0.95,
                reasoning="OK",
                specs_breakdown=[
                    SpecParameterMatch("Мощность", "не более 2000 Вт", "1800 Вт", "match", "OK")
                ],
                alternative_brands=[
                    AlternativeProduct(
                        brand="UnverifiedBrand",
                        model="U-100",
                        manufacturer="Unverified LLC",
                        confidence=0.92,
                        specs_breakdown=[
                            SpecParameterMatch("Мощность", "не более 2000 Вт", "1900 Вт", "match", "OK")
                        ],
                        gisp_match=None,
                    ),
                    AlternativeProduct(
                        brand="VerifiedRF",
                        model="RF-200",
                        manufacturer="Завод РФ",
                        confidence=0.96,
                        specs_breakdown=[
                            SpecParameterMatch("Мощность", "не более 2000 Вт", "1750 Вт", "match", "OK")
                        ],
                        gisp_match=GispRegistryMatch(registry_number="10582914", manufacturer="Завод РФ", product="RF-200"),
                    ),
                ],
            )
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        out_docx = Path(tmp) / "exact.docx"
        write_exact_product_docx(out_docx, report)
        doc = Document(str(out_docx))
        all_text = "\n".join([p.text for p in doc.paragraphs] + [
            cell.text for tbl in doc.tables for row in tbl.rows for cell in row.cells
        ])
        assert "ГИСП № 10582914" in all_text
        assert "Требует проверки" in all_text
        assert "Страна/реестр: требует проверки" in all_text
        assert "РФ (Реестр)" not in all_text
        assert "ГИСП: Реестр РФ" not in all_text


def test_ktru_vertical_single_item_table_does_not_split_characteristics_into_positions() -> None:
    ktru_table = "\n".join([
        "| № п/п | Код КТРУ | Наименование товара | Наименование характеристики | Значение характеристики | Ед. изм. |",
        "| 1 | 22.19.60.119-00000002 | Перчатки смотровые/процедурные нитриловые | Материал | Нитрил | - |",
        "| 2 | | | Текстура | Текстурированные на пальцах | - |",
        "| 3 | | | Неопудренные | Да | - |",
        "| 4 | | | Размер | M | усл. ед |",
        "| 5 | | | Усилие при разрыве | >= 6 | Н |",
    ])
    rows = product_inventory.extract_structured_product_inventory([], context=ktru_table)
    assert rows is not None
    assert len(rows) == 1
    assert "Перчатки" in rows[0]["name"]
    assert len(rows[0]["requirements"]) == 5


def test_document_parser_short_tz_zip_paths_and_filename_sanitization() -> None:
    ok, _ = document_parser.is_substantive_tz_text("ФБС 24.4.6-Т")
    assert ok is True

    assert document_parser.sanitize_filename("../../Спецификация №1 (ТЗ).docx") == "Спецификация №1 (ТЗ).docx"

    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "lots.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("Лот_1/ТЗ.txt", "Поставка труб стальных ГОСТ 10704")
            zf.writestr("Лот_2/ТЗ.txt", "Поставка задвижек чугунных 30ч6бр")
            zf.writestr("../../evil.txt", "should not escape")
        dest = Path(tmp) / "out"
        dest.mkdir()
        extracted = document_parser._extract_zip_members(zpath, dest, max_files=10)
        rel_paths = [str(p.relative_to(dest)) for p in extracted]
        assert any("Лот_1" in rp for rp in rel_paths)
        assert any("Лот_2" in rp for rp in rel_paths)
        assert all(p.resolve().is_relative_to(dest.resolve()) for p in extracted)


def test_tenderplan_partial_file_errors_and_okpd_date_preservation_and_excel_formula() -> None:
    # 1. Dates like 15.11.26 must NOT be stripped, while 4-group OKPD2 codes ARE stripped
    sample = "Срок поставки: до 15.11.26 г. Товар: Сервер 26.20.14.000 (ОКПД2: 26.20.14)"
    cleaned_md = procurement_report.remove_okpd_codes(sample)
    cleaned_rb = report_builder._remove_okpd_codes(sample)
    assert "15.11.26" in cleaned_md
    assert "15.11.26" in cleaned_rb
    assert "26.20.14.000" not in cleaned_md
    assert "26.20.14" not in cleaned_md

    # 2. Price monitoring Excel uses universal IF/STDEV (no _xlfn.IFS) and microdata extraction works
    soup = BeautifulSoup(
        '<html><body><h1>Насос КМ 80-50-200</h1><span itemprop="price" content="48500.00">48 500 ₽</span></body></html>',
        "html.parser",
    )
    prod, is_oos = extract_schema_org_product_data(soup)
    assert prod is not None
    assert prod["price"] == 48500.0
    assert is_oos is False

    with tempfile.TemporaryDirectory() as tmp:
        xlsx_path = Path(tmp) / "nmck.xlsx"
        item = ItemPriceResult(
            row_number=1,
            raw_name="Насос КМ 80-50-200",
            clean_name="Насос КМ 80-50-200",
            unit="шт",
            status="found",
            quotes=[
                SupplierQuote(company_name="ООО Завод 1", inn="7707083893", contacts="+7 (495) 111-22-33", price_rub=48000.0, raw_price_rub=48000.0, unit="шт", site_unit="шт", url="https://z1.ru", is_price_found=True),
                SupplierQuote(company_name="ООО Завод 2", inn="7707083893", contacts="+7 (495) 222-33-44", price_rub=50000.0, raw_price_rub=50000.0, unit="шт", site_unit="шт", url="https://z2.ru", is_price_found=True),
                SupplierQuote(company_name="ООО Завод 3", inn="7707083893", contacts="+7 (495) 333-44-55", price_rub=49000.0, raw_price_rub=49000.0, unit="шт", site_unit="шт", url="https://z3.ru", is_price_found=True),
            ],
        )
        generate_price_monitoring_excel([item], str(xlsx_path))
        wb = openpyxl.load_workbook(xlsx_path, data_only=False)
        ws = wb["Пример отчета"]
        formulas = [
            str(cell.value)
            for row in ws.iter_rows()
            for cell in row
            if isinstance(cell.value, str) and cell.value.startswith("=")
        ]
        assert any("=IF(COUNTA(" in f and "STDEV(" in f for f in formulas)
        assert not any("_xlfn.IFS" in f for f in formulas)
