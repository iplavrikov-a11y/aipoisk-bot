from __future__ import annotations

import datetime as dt
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.billing import (
    KIND_PROCUREMENT_REPORT,
    OP_CHARGE,
    OP_RELEASE,
    OP_RESERVE,
    reserve_batch_procurement_report_job,
    settle_batch_procurement_report_job,
)
from app.custom_batch_registry import parse_procurement_registry_file
from app.custom_batch_runner import _strip_internal_source_names, _unwrap_grounding_urls
from app.db import SessionLocal, init_db
from app.jobs import create_job, job_dir
from app.main import app
from app.models import BillingTransaction, Client, ClientTariffOverride, WebUser, new_id
from app.repository import get_or_create_settings
from app.web_auth import CSRF_HEADER, CUSTOMER_COOKIE, create_web_session, hash_password


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_client_with_web_user(
    db: Session,
    *,
    allowed_batch: bool,
    balance_kopeks: int = 10_000,
    override_price_kopeks: int = 1500,
) -> tuple[Client, WebUser, str, str]:
    cid = new_id()
    client = Client(
        id=cid,
        telegram_id=f"tg_{cid[:10]}",
        name="Олег Тест",
        username=f"user_{cid[:6]}",
        is_active=True,
        allowed_procurement_report=True,
        allowed_custom_batch_report=allowed_batch,
        custom_report_prompt="Тестовый промт аналитика",
        money_balance_kopeks=balance_kopeks,
        money_reserved_kopeks=0,
    )
    db.add(client)
    db.flush()
    if override_price_kopeks > 0:
        db.add(
            ClientTariffOverride(
                client_id=client.id,
                kind=KIND_PROCUREMENT_REPORT,
                price_kopeks=override_price_kopeks,
                is_enabled=True,
                note="15 руб за закупку",
            )
        )
    user = WebUser(
        id=new_id(),
        client_id=client.id,
        email=f"test-{cid[:8]}@example.com",
        password_hash=hash_password("StrongTestPass123!"),
        name="Олег",
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    token, csrf, _ = create_web_session(db, user)
    return client, user, token, csrf


def _make_sample_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Мелочь"
    ws.append(["Закупка", None, None, None, None])
    ws.append(["Номер", "Название", "НМЦ", "Дата публикации", "Окончание приема заявок"])
    ws.append([
        "0329300294326000004",
        "Поставка прицепа для трактора",
        211333.33,
        dt.datetime(2026, 10, 31, 15, 41),
        dt.datetime(2026, 11, 9, 8, 0),
    ])
    ws.cell(3, 1).hyperlink = (
        "https://zakupki.kontur.ru:443/api/redirect?url=https%3A%2F%2Fzakupki.kontur.ru%2F0329300294326000004"
        "&metrics.EtpLink=https%3A%2F%2Fwww.rts-tender.ru%2Fauctionsearch%2Fnumber%2F0329300294326000004"
    )
    ws.append([
        "32616532998",
        "Поставка термосов для напитков",
        1008386.97,
        dt.datetime(2026, 10, 30, 14, 10),
        dt.datetime(2026, 11, 9, 10, 0),
    ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_parse_xlsx_registry_extracts_rows_and_hyperlinks(db_session: Session):
    settings = get_or_create_settings(db_session)
    xlsx_bytes = _make_sample_xlsx_bytes()

    ai_response = json.dumps(
        {
            "is_procurement_table": True,
            "data_start_row": 3,
            "columns": {
                "notice_number": 0,
                "title": 1,
                "nmck": 2,
                "publication_date": 3,
                "deadline_date": 4,
            },
        }
    )
    with patch("app.custom_batch_registry.call_llm", new=AsyncMock(return_value=ai_response)):
        res = await parse_procurement_registry_file(
            settings,
            filename="report.xlsx",
            content=xlsx_bytes,
        )

    assert res.is_registry is True
    assert res.sheet_name == "Мелочь"
    assert len(res.items) == 2
    assert res.items[0]["notice_number"] == "0329300294326000004"
    assert res.items[0]["title"] == "Поставка прицепа для трактора"
    assert "211 333,33 ₽" in res.items[0]["nmck_raw"]
    assert res.items[0]["deadline_date"] == "09.11.2026 08:00"
    assert "rts-tender.ru" in res.items[0]["etp_url"]


def test_batch_billing_reserves_and_partially_settles_at_15_rub(db_session: Session):
    db = db_session
    client, _, _, _ = _create_client_with_web_user(
        db,
        allowed_batch=True,
        balance_kopeks=10_000,  # 100.00 ₽
        override_price_kopeks=1500,  # 15.00 ₽
    )
    job = create_job(
        db,
        client_id=client.id,
        mode="procurement_report",
        title="Пакет 4 закупки",
        target_suppliers=10,
        files=[],
        initial_status="draft",
    )
    reserved = reserve_batch_procurement_report_job(db, client, job, procurement_count=4)
    assert reserved == 6000  # 4 * 15 ₽ = 60 ₽
    db.refresh(client)
    assert client.money_reserved_kopeks == 6000
    assert client.money_balance_kopeks == 10_000

    job.status = "running"
    db.commit()

    # Suppose 3 of 4 tenders succeeded and 1 had no docs: charge 45 ₽, refund 15 ₽
    charged = settle_batch_procurement_report_job(db, job, completed_count=3)
    assert charged is True
    db.refresh(client)
    assert client.money_reserved_kopeks == 0
    assert client.money_balance_kopeks == 5500  # 100 - 45 = 55 ₽

    txs = (
        db.query(BillingTransaction)
        .filter(BillingTransaction.job_id == job.id)
        .all()
    )
    ops = {t.operation: (t.units, t.amount_kopeks) for t in txs}
    assert ops[OP_RESERVE] == (4, 6000)
    assert ops[OP_CHARGE] == (3, 4500)
    assert ops[OP_RELEASE] == (1, 1500)


def test_batch_endpoints_enforce_permission_csrf_ownership_and_path_safety(db_session: Session):
    db = db_session
    regular_client, _, reg_token, reg_csrf = _create_client_with_web_user(db, allowed_batch=False)
    vip_client, _, vip_token, vip_csrf = _create_client_with_web_user(
        db,
        allowed_batch=True,
        balance_kopeks=10_000,
        override_price_kopeks=1500,
    )
    xlsx_bytes = _make_sample_xlsx_bytes()

    with TestClient(app) as tc:
        # 1. Non-allowed client gets 403
        tc.cookies.set(CUSTOMER_COOKIE, reg_token)
        r_denied = tc.post(
            "/api/customer/jobs/batch-report/preview",
            headers={CSRF_HEADER: reg_csrf},
            files={"file": ("list.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r_denied.status_code == 403

        # 2. VIP client without CSRF gets 403
        tc.cookies.set(CUSTOMER_COOKIE, vip_token)
        r_no_csrf = tc.post(
            "/api/customer/jobs/batch-report/create",
            json={"filename": "list.xlsx", "items": [{"notice_number": "32616532998", "title": "Термосы"}]},
        )
        assert r_no_csrf.status_code == 403

        # 3. VIP client creates batch job cleanly
        with patch("app.main.enqueue_job"):
            r_ok = tc.post(
                "/api/customer/jobs/batch-report/create",
                headers={CSRF_HEADER: vip_csrf},
                json={
                    "filename": "list.xlsx",
                    "items": [
                        {"id": "a1", "notice_number": "32616532998", "title": "Термосы", "nmck_raw": "1 008 386 ₽"},
                        {"id": "a2", "notice_number": "0329300294326000004", "title": "Прицеп", "nmck_raw": "211 333 ₽"},
                    ],
                },
            )
        assert r_ok.status_code == 200
        job_id = r_ok.json()["job"]["id"]
        assert r_ok.json()["job"]["is_custom_batch_report"] is True

        # 4. Regular client cannot read VIP client's batch report (404)
        tc.cookies.set(CUSTOMER_COOKIE, reg_token)
        r_other = tc.get(f"/api/customer/jobs/{job_id}/batch-report")
        assert r_other.status_code == 404

        # 5. Path traversal filename inside custom_batch_results.json is safely sanitized/confined
        out_dir = job_dir(job_id) / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "custom_batch_results.json").write_text(
            json.dumps(
                {
                    "is_custom_batch_report": True,
                    "total_count": 1,
                    "completed_count": 1,
                    "failed_count": 0,
                    "items": [
                        {
                            "index": 0,
                            "notice_number": "32616532998",
                            "title": "Термосы",
                            "status": "completed",
                            "report_markdown": "ok",
                            "docx_filename": "../../etc/passwd",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        tc.cookies.set(CUSTOMER_COOKIE, vip_token)
        r_trav = tc.get(f"/api/customer/jobs/{job_id}/batch-report/download/0")
        assert r_trav.status_code == 404


@pytest.mark.asyncio
async def test_strip_internal_names_and_unwrap_redirect():
    cleaned = _strip_internal_source_names("В карточке Tenderplan и на tenderplan.ru указан Тендерплана статус.")
    assert "tenderplan" not in cleaned.lower()
    assert "тендерплан" not in cleaned.lower()

    md = "Ссылка: [Магазин](https://vertexaisearch.cloud.google.com/grounding-api-redirect/TESTTOKEN123)"
    with patch(
        "app.custom_batch_runner._resolve_single_vertex_redirect",
        new=AsyncMock(return_value="https://www.posuda.ru/product/kettle-7l/"),
    ):
        unwrapped, sources = await _unwrap_grounding_urls(
            md,
            [{"web": {"title": "posuda.ru", "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/TESTTOKEN123"}}],
        )
    assert "https://www.posuda.ru/product/kettle-7l/" in unwrapped
    assert "vertexaisearch" not in unwrapped
    assert sources == [{"title": "posuda.ru", "url": "https://www.posuda.ru/product/kettle-7l/"}]


@pytest.mark.asyncio
async def test_parse_notice_only_xlsx_csv_and_docx_without_title_or_nmck(db_session: Session):
    settings = get_or_create_settings(db_session)

    # 1. Single-row, single-column headerless Excel with ONLY notice number
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["0329300294326000004"])
    buf = io.BytesIO()
    wb.save(buf)

    ai_col_only = json.dumps(
        {
            "is_procurement_table": True,
            "data_start_row": 1,
            "columns": {
                "notice_number": 0,
                "title": None,
                "nmck": None,
            },
        }
    )
    with patch("app.custom_batch_registry.call_llm", new=AsyncMock(return_value=ai_col_only)):
        res_xlsx = await parse_procurement_registry_file(
            settings,
            filename="quotes_only.xlsx",
            content=buf.getvalue(),
        )
    assert res_xlsx.is_registry is True
    assert len(res_xlsx.items) == 1
    assert res_xlsx.items[0]["notice_number"] == "0329300294326000004"
    assert res_xlsx.items[0]["nmck_raw"] == ""

    # 2. Single-row CSV with ONLY notice number (no title, no NMCK)
    with patch("app.custom_batch_registry.call_llm", new=AsyncMock(return_value=ai_col_only)):
        res_csv = await parse_procurement_registry_file(
            settings,
            filename="quotes_only.csv",
            content="32616532998\n".encode("utf-8"),
        )
    assert res_csv.is_registry is True
    assert len(res_csv.items) == 1
    assert res_csv.items[0]["notice_number"] == "32616532998"
    assert res_csv.items[0]["nmck_raw"] == ""

    # 3. DOCX containing only notice numbers (quotes / котировки without NMCK or titles)
    import docx as python_docx

    doc = python_docx.Document()
    doc.add_paragraph("0329300294326000004")
    doc.add_paragraph("32616532998")
    docx_buf = io.BytesIO()
    doc.save(docx_buf)

    ai_docx = json.dumps(
        {
            "is_procurement_table": True,
            "items": [
                {"notice_number": "0329300294326000004", "title": "", "nmck_raw": ""},
                {"notice_number": "32616532998", "title": "", "nmck_raw": ""},
            ],
        }
    )
    with patch("app.custom_batch_registry.call_llm", new=AsyncMock(return_value=ai_docx)):
        res_docx = await parse_procurement_registry_file(
            settings,
            filename="notices.docx",
            content=docx_buf.getvalue(),
        )
    assert res_docx.is_registry is True
    assert len(res_docx.items) == 2
    assert res_docx.items[0]["notice_number"] == "0329300294326000004"
    assert res_docx.items[1]["nmck_raw"] == ""


@pytest.mark.asyncio
async def test_execute_batch_backfills_missing_title_from_report(db_session: Session):
    from app.custom_batch_runner import CustomPromptRunResult, CustomTenderBundle, execute_custom_batch_items

    settings = get_or_create_settings(db_session)
    items = [{"id": "n1", "notice_number": "32616532998", "title": "Закупка 32616532998", "nmck_raw": ""}]
    with (
        patch(
            "app.custom_batch_runner.fetch_custom_tender_bundle",
            new=AsyncMock(return_value=CustomTenderBundle(ok=True, context="ТЗ на поставку термосов")),
        ),
        patch(
            "app.custom_batch_runner.run_custom_prompt_with_gemini_search",
            new=AsyncMock(
                return_value=CustomPromptRunResult(
                    markdown="* **Наименование объекта закупки:** Поставка термосов металлических\n",
                    model="gemini-4-hydrogen-xhigh",
                    sources=[],
                )
            ),
        ),
    ):
        results = await execute_custom_batch_items(settings, custom_prompt="Промт", items=items)
    assert len(results) == 1
    assert results[0]["status"] == "completed"
    assert results[0]["title"] == "Поставка термосов металлических"


def test_write_procurement_docx_renders_clickable_hyperlinks_and_clean_bullets(tmp_path: Path):
    import zipfile
    from app.report_builder import write_procurement_docx

    md = (
        "### 2. Подбор товара\n\n"
        "| Товар | Ссылка |\n"
        "| :--- | :--- |\n"
        "| Табурет | **[Табурет Комус](https://www.komus.ru/p/2329573/)** |\n\n"
        "1. **ООО «КИРАСА-СПБ»** — [kirasa-spb.ru](https://kirasa-spb.ru/stavni/)\n"
        "* *Почему подходят:* Местный производитель.\n"
        "* Ссылка без разметки: https://galikson.ru/shop/bronestavni/\n"
    )
    out = write_procurement_docx(tmp_path / "test_links.docx", md, title="Тест ссылок")
    assert out.is_file()

    with zipfile.ZipFile(out) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        rels_xml = zf.read("word/_rels/document.xml.rels").decode("utf-8")

    # Links must be real Word hyperlinks in rels and w:hyperlink XML tags, not raw [label](url)
    assert "<w:hyperlink" in doc_xml
    assert "https://www.komus.ru/p/2329573/" in rels_xml
    assert "https://kirasa-spb.ru/stavni/" in rels_xml
    assert "https://galikson.ru/shop/bronestavni/" in rels_xml
    assert "[kirasa-spb.ru](" not in doc_xml
    assert "*Почему подходят:*" not in doc_xml
    assert "Почему подходят:" in doc_xml
    assert "• " in doc_xml


def test_parse_procurement_text_list_handles_commas_columns_alphanumeric_and_urls():
    from app.custom_batch_registry import parse_procurement_text_list

    raw = (
        "0332300328126000079, 32616579502\n"
        "6298269\n"
        "302527-26LO;\n"
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0373200649326000016\n"
        "https://zakupki.lenreg.ru/trades/small/302527-26LO\n"
    )
    res = parse_procurement_text_list(raw)
    assert res.is_registry is True
    nums = [it["notice_number"] for it in res.items]
    assert nums == [
        "0332300328126000079",
        "32616579502",
        "6298269",
        "302527-26LO",
        "0373200649326000016",
        "302527-26LO",
    ]
    assert res.items[4]["eis_url"].startswith("https://zakupki.gov.ru/")
    assert res.items[5]["etp_url"].startswith("https://zakupki.lenreg.ru/")


@pytest.mark.asyncio
async def test_multisheet_xlsx_requires_sheet_selection_then_parses_chosen_sheets(db_session: Session):
    settings = get_or_create_settings(db_session)
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Все шаблоны"
    ws1.append(["Номер", "Название"])
    ws1.append(["0329300294326000004", "Поставка прицепа"])
    ws2 = wb.create_sheet("ГАЗ тендерплан")
    ws2.append(["Номер", "Название"])
    ws2.append(["32616532998", "Поставка термосов"])
    ws3 = wb.create_sheet("Пустая")  # Empty sheet must be ignored
    buf = io.BytesIO()
    wb.save(buf)
    raw = buf.getvalue()

    # Step 1: Initial inspect returns requires_sheet_selection=True with 2 non-empty tabs
    res_prompt = await parse_procurement_registry_file(
        settings,
        filename="multi.xlsx",
        content=raw,
    )
    assert res_prompt.requires_sheet_selection is True
    assert res_prompt.sheet_names == ["Все шаблоны", "ГАЗ тендерплан"]
    assert res_prompt.items == []

    # Step 2: Inspect selected sheets combines items from both chosen sheets
    ai_mapping = json.dumps(
        {
            "is_procurement_table": True,
            "data_start_row": 2,
            "columns": {"notice_number": 0, "title": 1},
        }
    )
    with patch("app.custom_batch_registry.call_llm", new=AsyncMock(return_value=ai_mapping)):
        res_selected = await parse_procurement_registry_file(
            settings,
            filename="multi.xlsx",
            content=raw,
            requested_sheets=["Все шаблоны", "ГАЗ тендерплан"],
        )
    assert res_selected.requires_sheet_selection is False
    assert res_selected.selected_sheets == ["Все шаблоны", "ГАЗ тендерплан"]
    assert len(res_selected.items) == 2
    assert res_selected.items[0]["sheet_name"] == "Все шаблоны"
    assert res_selected.items[1]["sheet_name"] == "ГАЗ тендерплан"


@pytest.mark.asyncio
async def test_multisheet_xlsx_resolves_sheet_names_with_trailing_spaces(db_session: Session):
    settings = get_or_create_settings(db_session)
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Все шаблоны"
    ws1.append(["Номер", "Название"])
    ws1.append(["0329300294326000004", "Прицеп"])
    ws2 = wb.create_sheet("ГАЗ тендерплан ")
    ws2.append(["Номер", "Название"])
    ws2.append(["32616532998", "Термосы"])
    buf = io.BytesIO()
    wb.save(buf)

    ai_mapping = json.dumps(
        {
            "is_procurement_table": True,
            "data_start_row": 2,
            "columns": {"notice_number": 0, "title": 1},
        }
    )
    with patch("app.custom_batch_registry.call_llm", new=AsyncMock(return_value=ai_mapping)):
        res = await parse_procurement_registry_file(
            settings,
            filename="spaces.xlsx",
            content=buf.getvalue(),
            requested_sheets=["ГАЗ тендерплан"],
        )
    assert res.requires_sheet_selection is False
    assert res.is_registry is True
    assert len(res.items) == 1
    assert res.items[0]["notice_number"] == "32616532998"
    assert res.items[0]["sheet_name"] == "ГАЗ тендерплан "


def test_separate_tab_flag_routes_standard_vs_custom_prompt_jobs(db_session: Session):
    from app.jobs import read_dobor_context

    db = db_session
    client, _, token, csrf = _create_client_with_web_user(db, allowed_batch=True, balance_kopeks=50_000)
    client.custom_report_separate_tab = True
    db.commit()

    with TestClient(app) as tc:
        tc.cookies.set(CUSTOMER_COOKIE, token)
        sess = tc.get("/api/customer/auth/session").json()
        assert sess["user"]["allowed_custom_batch_report"] is True
        assert sess["user"]["custom_report_separate_tab"] is True

        with patch("app.main.enqueue_job"):
            r_std = tc.post(
                "/api/customer/jobs",
                headers={CSRF_HEADER: csrf},
                data={
                    "mode": "procurement_report",
                    "source_urls": "0329300294326000004",
                },
            )
            assert r_std.status_code == 200
            std_job_id = r_std.json()["job"]["id"]

            r_cust = tc.post(
                "/api/customer/jobs",
                headers={CSRF_HEADER: csrf},
                data={
                    "mode": "procurement_report",
                    "source_urls": "0329300294326000004",
                    "use_custom_prompt": "true",
                },
            )
            assert r_cust.status_code == 200
            cust_job_id = r_cust.json()["job"]["id"]

    from app.models import Job

    std_job = db.get(Job, std_job_id)
    cust_job = db.get(Job, cust_job_id)
    assert not read_dobor_context(std_job).get("use_custom_prompt")
    assert read_dobor_context(cust_job).get("use_custom_prompt") is True


def test_html_stub_detection_and_non_seller_source_filtering():
    import httpx
    from app.custom_batch_runner import _is_html_stub_response

    html_resp = httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        content=b"<!DOCTYPE html><html><title>Captcha</title><body>Check browser</body></html>",
    )
    docx_resp = httpx.Response(
        200,
        headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        content=b"PK\x03\x04...",
    )
    assert _is_html_stub_response(html_resp) is True
    assert _is_html_stub_response(docx_resp) is False
