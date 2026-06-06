from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import app.tenderplan as tenderplan_module
from app.tenderplan import (
    TenderplanClient,
    TenderplanFetchResult,
    attachment_items,
    build_tenderplan_download_context,
    best_filestore_fallback_url,
    build_tenderplan_context,
    filestore_fallbacks_from_documents_html,
    find_tender_matches,
    format_related_tenders,
    format_msk,
    fetch_tenderplan_source_sync,
    is_allowed_download_url,
    preferred_tender_id,
    merge_tenderplan_payloads,
    notice223_documents_url,
    normalize_document_name,
    normalize_notice_number,
    parse_tool_dictionary,
    run_curl_download,
    safe_attachment_filename,
)


def _ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


class TenderplanPureFunctionTests(unittest.TestCase):
    def test_normalize_notice_number_accepts_procurement_numbers_only(self) -> None:
        self.assertEqual(normalize_notice_number("0371100005626000040"), "0371100005626000040")
        self.assertEqual(normalize_notice_number("32615728276"), "32615728276")
        self.assertEqual(normalize_notice_number("261710600552071060100100350012620244"), "")

    def test_find_tender_matches_walks_nested_search_payload(self) -> None:
        payload = {
            "items": [
                {"number": "000", "_id": "wrong"},
                {"group": [{"number": "0371100005626000040", "_id": "tender-1"}]},
                {"number": "0371100005626000040", "_id": "tender-1"},
            ]
        }

        matches = find_tender_matches(payload, "0371100005626000040")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["_id"], "tender-1")

    def test_build_context_contains_card_dates_natregime_and_material_counts(self) -> None:
        publication = _ms(datetime(2026, 6, 1, 6, 0, tzinfo=timezone.utc))
        close = _ms(datetime(2026, 6, 10, 7, 0, tzinfo=timezone.utc))
        bidding = _ms(datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc))
        summing = _ms(datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc))
        tender_json = {
            "objects": {
                "ft": "Table",
                "fv": {
                    "th": {
                        "1": {"fv": "Наименование товара, работы, услуги"},
                        "2": {"fv": "Количество"},
                        "3": {"fv": "Нацрежим"},
                    },
                    "tb": {
                        "0": {
                            "1": {"fv": "Насос погружной"},
                            "2": {"fv": "3 шт"},
                            "3": {"fv": "Запрет закупок товаров"},
                        }
                    },
                },
            },
            "general": {"requirements": {"fn": "requirements", "fv": True}},
        }
        context = build_tenderplan_context(
            notice_number="0371100005626000040",
            tender_id="tp-1",
            fullinfo={
                "tender": {
                    "number": "0371100005626000040",
                    "href": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0371100005626000040",
                    "orderName": "Поставка насосов",
                    "placingWay": "Электронный аукцион",
                    "maxPrice": 123456.78,
                    "submissionCloseDateTime": close,
                    "biddingDateTime": bidding,
                    "summingUpDateTime": summing,
                    "feed": [{"event": "Размещен документ", "eventDateTime": publication}],
                    "customers": [{"name": "ФГБУ Заказчик"}],
                    "platform": {"name": "РТС-тендер", "href": "https://www.rts-tender.ru/"},
                    "json": json.dumps(tender_json, ensure_ascii=False),
                }
            },
            attachments=[{"realName": "Техническое задание.docx", "href": "https://zakupki.gov.ru/file.html?id=1", "size": 2048}],
            explanations=[{"id": "exp-1"}],
            explanation_attachments=[{"realName": "Ответ на запрос.docx", "href": "https://zakupki.gov.ru/file.html?id=2", "size": 1024}],
        )

        self.assertIn("ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ", context)
        self.assertIn("- Номер извещения: 0371100005626000040", context)
        self.assertIn("- Способ осуществления закупки: Электронный аукцион", context)
        self.assertIn("- Размещено: 01.06.2026", context)
        self.assertIn("- Дата и время окончания срока подачи заявок (МСК): 10.06.2026 10:00 МСК", context)
        self.assertIn("- Аукцион/подача цены: 10.06.2026 12:00 МСК", context)
        self.assertIn("- Дата подведения итогов (МСК): 11.06.2026 13:00 МСК", context)
        self.assertIn("Насос погружной: Запрет закупок товаров", context)
        self.assertIn("Техническое задание.docx", context)
        self.assertIn("Разъяснения/ответы заказчика: 1 записей, 1 файлов", context)

    def test_build_context_renders_numeric_placing_way_as_code_not_method(self) -> None:
        context = build_tenderplan_context(
            notice_number="32616063169",
            tender_id="tp-1",
            fullinfo={
                "tender": {
                    "number": "32616063169",
                    "href": "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32616063169",
                    "orderName": "Поставка каната",
                    "placingWay": 22,
                }
            },
            attachments=[],
            explanations=[],
            explanation_attachments=[],
        )

        self.assertIn("- Код способа закупки источника: 22", context)
        self.assertIn("Человекочитаемый способ закупки", context)
        self.assertNotIn("- Способ осуществления закупки: 22", context)

    def test_build_context_decodes_numeric_placing_way_from_global_search(self) -> None:
        context = build_tenderplan_context(
            notice_number="32616063169",
            tender_id="tp-1",
            fullinfo={
                "tender": {
                    "number": "32616063169",
                    "href": "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32616063169",
                    "orderName": "Поставка каната",
                    "placingWay": 22,
                    "globalSearch": "Поставка каната 32616063169 Запрос котировок в электронной форме",
                }
            },
            attachments=[],
            explanations=[],
            explanation_attachments=[],
        )

        self.assertIn("- Способ осуществления закупки: Запрос котировок в электронной форме", context)
        self.assertIn("- Код способа закупки источника: 22", context)
        self.assertIn("- Источник расшифровки способа: текст карточки закупки", context)
        self.assertNotIn("Человекочитаемый способ закупки", context)

    def test_build_context_decodes_numeric_placing_way_from_dictionary(self) -> None:
        context = build_tenderplan_context(
            notice_number="32616063169",
            tender_id="tp-1",
            fullinfo={
                "tender": {
                    "number": "32616063169",
                    "href": "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32616063169",
                    "orderName": "Поставка каната",
                    "placingWay": 22,
                    "status": 1,
                }
            },
            attachments=[],
            explanations=[],
            explanation_attachments=[],
            placing_way_names={"22": "Запрос котировок в электронной форме"},
            placing_way_source="Tenderplan /api/tools/placingways/list",
            status_names={"1": "Прием заявок"},
            status_source="Tenderplan /api/tools/statuses/list",
        )

        self.assertIn("- Способ осуществления закупки: Запрос котировок в электронной форме", context)
        self.assertIn("- Код способа закупки источника: 22", context)
        self.assertIn("- Источник расшифровки способа: официальный справочник способов закупки", context)
        self.assertIn("- Статус: Прием заявок (код источника: 1; источник: официальный справочник статусов)", context)
        self.assertNotIn("Человекочитаемый способ закупки", context)

    def test_parse_tool_dictionary_uses_id_name_pairs(self) -> None:
        self.assertEqual(
            parse_tool_dictionary([
                {"_id": 22, "name": "Запрос котировок в электронной форме", "shortName": "ЗКЭФ"},
                {"_id": 27, "name": " Запрос цен товаров, работ, услуг "},
                {"_id": None, "name": "bad"},
            ]),
            {
                "22": "Запрос котировок в электронной форме",
                "27": "Запрос цен товаров, работ, услуг",
            },
        )

    def test_build_context_decodes_zero_codes_from_dictionary(self) -> None:
        context = build_tenderplan_context(
            notice_number="32616049433",
            tender_id="tp-1",
            fullinfo={
                "tender": {
                    "number": "32616049433",
                    "href": "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32616049433",
                    "orderName": "Поставка канатов",
                    "placingWay": 0,
                    "status": 0,
                }
            },
            attachments=[],
            explanations=[],
            explanation_attachments=[],
            placing_way_names={"0": "Иной способ"},
            placing_way_source="Tenderplan /api/tools/placingways/list",
            status_names={"0": "Неизвестно"},
            status_source="Tenderplan /api/tools/statuses/list",
        )

        self.assertIn("- Способ осуществления закупки: Иной способ", context)
        self.assertIn("- Код способа закупки источника: 0", context)
        self.assertIn("- Статус: Неизвестно (код источника: 0; источник: официальный справочник статусов)", context)

    def test_download_context_surfaces_partial_download_failures(self) -> None:
        context = build_tenderplan_download_context([], [{"name": "ТЗ.docx", "error": "http_500"}])

        self.assertIn("Скачано файлов для последующего анализа: 0", context)
        self.assertIn("Не скачано файлов: 1", context)
        self.assertIn("ТЗ.docx: http_500", context)

    def test_related_tenders_are_rendered_as_multi_lot_notice_context(self) -> None:
        lines = format_related_tenders(
            [
                {"_id": "lot-1", "orderName": "Поставка стекол ЛИАЗ", "maxPrice": 620000},
                {"_id": "lot-2", "orderName": "Поставка стекол КАМАЗ", "maxPrice": 400000},
            ],
            selected_tender_id="lot-1",
        )

        self.assertIn("основная карточка; Поставка стекол ЛИАЗ; НМЦК: 620 000.00 руб.", lines[0])
        self.assertIn("карточка 2; Поставка стекол КАМАЗ; НМЦК: 400 000.00 руб.", lines[1])

    def test_format_msk_accepts_milliseconds_and_seconds(self) -> None:
        value = _ms(datetime(2026, 6, 10, 7, 0, tzinfo=timezone.utc))

        self.assertEqual(format_msk(value), "10.06.2026 10:00 МСК")
        self.assertEqual(format_msk(value / 1000), "10.06.2026 10:00 МСК")

    def test_download_url_allowlist_and_safe_names(self) -> None:
        self.assertTrue(is_allowed_download_url("https://zakupki.gov.ru/file.html?id=1"))
        self.assertTrue(is_allowed_download_url("https://fcs.zakupki.gov.ru/file.html?id=1"))
        self.assertFalse(is_allowed_download_url("https://example.com/file.docx"))

        filename = safe_attachment_filename("ТЗ", "https://zakupki.gov.ru/files/spec.docx", "documentation")

        self.assertTrue(filename.startswith("Документация - "))
        self.assertTrue(filename.endswith(".docx"))

    def test_safe_attachment_filename_preserves_extension_after_truncation(self) -> None:
        filename = safe_attachment_filename(
            "Приложение_Рабочая_документация_шифр_1372.40_2024_НК1.1_к_тЗ__закупки___Техническое_задание_очень_длинное_имя_файла_которое_ЕИС_может_вернуть_в_карточке.docx",
            "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=1",
            "documentation",
        )

        self.assertLessEqual(len(filename.encode("utf-8")), 180)
        self.assertTrue(filename.endswith(".docx"))

    def test_preferred_tender_id_chooses_notice_over_price_request_card(self) -> None:
        fullinfo_by_id = {
            "price-request": {
                "tender": {
                    "number": "0372200127526000030",
                    "href": "https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber=0372200127526000030",
                }
            },
            "notice": {
                "tender": {
                    "number": "0372200127526000030",
                    "href": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0372200127526000030",
                }
            },
        }

        self.assertEqual(preferred_tender_id(fullinfo_by_id, fallback_id="price-request"), "notice")

    def test_notice223_documents_url_uses_purchase_number_and_notice_guid(self) -> None:
        url = notice223_documents_url(
            "https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616063169",
            '<a href="/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616063169&noticeGuid=62ee9167-a154-4e8c-9451-448d170abe2a">Документы</a>',
        )

        self.assertEqual(
            url,
            "https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616063169&noticeGuid=62ee9167-a154-4e8c-9451-448d170abe2a",
        )

    def test_filestore_fallbacks_from_documents_html_maps_links_by_filename(self) -> None:
        html = """
        <a href="/223/filestore/public/1.0/download/fz223/file.html?uid=9E43F42DC695407589B8DCCB17683275">
            Приложение №2 Техническое задание.docx
        </a>
        """

        result = filestore_fallbacks_from_documents_html(
            html,
            base_url="https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616063169",
        )

        self.assertEqual(
            result[normalize_document_name("Приложение №2 Техническое задание.docx")],
            "https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=9E43F42DC695407589B8DCCB17683275",
        )

    def test_filestore_fallback_matching_tolerates_short_tz_and_punctuation(self) -> None:
        by_name = {
            normalize_document_name("Приложение №1 Проект договора.doc"): "https://zakupki.gov.ru/contract",
            normalize_document_name("Приложение №2 Техническое задание.docx"): "https://zakupki.gov.ru/tz",
        }

        self.assertEqual(best_filestore_fallback_url("ТЗ.docx", by_name), "https://zakupki.gov.ru/tz")
        self.assertEqual(
            normalize_document_name("Приложение №2 Техническое задание.docx"),
            normalize_document_name("Приложение _2 Техническое задание"),
        )

    def test_filestore_fallback_matching_refuses_ambiguous_lot_names(self) -> None:
        by_name = {
            normalize_document_name("Извещение 207 Лот 1.docx"): "https://zakupki.gov.ru/lot1",
            normalize_document_name("Извещение 207 Лот 2.docx"): "https://zakupki.gov.ru/lot2",
        }

        self.assertEqual(best_filestore_fallback_url("Извещение 207 Лот.docx", by_name), "")

    def test_curl_download_retries_transient_server_error(self) -> None:
        calls = 0

        def fake_run(args, **kwargs):
            nonlocal calls
            calls += 1
            output = Path(args[args.index("-o") + 1])
            if calls == 1:
                return subprocess.CompletedProcess(args, 0, stdout="500", stderr="")
            output.write_bytes(b"ok")
            return subprocess.CompletedProcess(args, 0, stdout="200", stderr="")

        with tempfile.TemporaryDirectory() as tmp, patch("app.tenderplan.subprocess.run", side_effect=fake_run):
            status, error = run_curl_download("https://zakupki.gov.ru/file.docx", Path(tmp) / "file.docx")

        self.assertEqual((status, error), ("200", ""))
        self.assertEqual(calls, 2)

    def test_attachment_items_accepts_nested_attachment_payloads(self) -> None:
        items = attachment_items(
            {
                "group": [
                    {"displayName": "Ответ на запрос", "href": "https://zakupki.gov.ru/file.html?id=1", "size": 1234},
                    {"displayName": "Без ссылки"},
                ]
            },
            "explanation",
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "Ответ на запрос")
        self.assertEqual(items[0].category, "explanation")

    def test_merge_tenderplan_payloads_flattens_and_deduplicates_by_href(self) -> None:
        merged = merge_tenderplan_payloads(
            [{"realName": "Лот 1", "href": "https://zakupki.gov.ru/lot1.docx"}],
            {"group": [{"displayName": "Лот 1 дубль", "href": "https://zakupki.gov.ru/lot1.docx"}]},
            [{"realName": "Лот 2", "href": "https://zakupki.gov.ru/lot2.docx"}],
        )

        self.assertEqual([item.get("href") for item in merged], ["https://zakupki.gov.ru/lot1.docx", "https://zakupki.gov.ru/lot2.docx"])

    def test_fetch_procurement_aggregates_documents_from_related_lots(self) -> None:
        number = "32616089466"
        captured = []
        called_paths = []
        client = TenderplanClient(token="token")

        def fake_get_json(path, *, params=None, default=None):
            called_paths.append(path)
            tender_id = (params or {}).get("id")
            if path == "/api/search/tender":
                return {"items": [{"number": number, "_id": "lot-1"}, {"number": number, "_id": "lot-2"}]}
            if path == "/api/tenders/v2/fullinfo":
                return {
                    "tender": {
                        "_id": tender_id,
                        "number": number,
                        "href": "https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616089466",
                        "orderName": f"Лот {tender_id}",
                    }
                }
            if path == "/api/tenders/attachments":
                return [{"realName": f"{tender_id}.docx", "href": f"https://zakupki.gov.ru/{tender_id}.docx"}]
            return default if default is not None else []

        def fake_download(items, *, fallback_urls=None):
            captured.extend(items)
            return [], []

        with (
            patch.object(client, "_get_json", side_effect=fake_get_json),
            patch("app.tenderplan.resolve_223_filestore_fallbacks", return_value={}),
            patch("app.tenderplan.download_tenderplan_attachments", side_effect=fake_download),
        ):
            result = client.fetch_procurement(number)

        self.assertTrue(result.ok)
        self.assertEqual([item.name for item in captured], ["lot-1.docx", "lot-2.docx"])
        self.assertFalse(any("protocol" in path for path in called_paths))

    def test_fetch_source_uses_shared_service_and_downloads_file_endpoint(self) -> None:
        class FakeResponse:
            def __init__(self, *, payload=None, content=b"", status_code=200) -> None:
                self._payload = payload
                self.content = content
                self.status_code = status_code

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def post(self, url, params=None):
                self.post_url = url
                return FakeResponse(
                    payload={
                        "success": True,
                        "schema_version": "2.1",
                        "status": "ok",
                        "notice_number": "32616063169",
                        "tender_id": "tp-1",
                        "context": "Tenderplan context",
                        "warnings": [],
                        "document_hints": {
                            "primary_technical_spec": {
                                "filename": "ТЗ.docx",
                                "document_type": "technical_spec",
                            }
                        },
                        "files": [
                            {
                                "filename": "ТЗ.docx",
                                "url": "/v1/files/abc",
                                "category": "documentation",
                                "document_type": "technical_spec",
                                "document_type_source": "filename+content",
                                "document_type_confidence": 0.95,
                                "content_document_types": ["technical_spec"],
                                "source_url": "https://zakupki.gov.ru/file",
                            }
                        ],
                        "download_errors": [],
                    }
                )

            def get(self, url):
                self.get_url = url
                return FakeResponse(content=b"docx")

        fake_client = FakeClient()
        with (
            patch.object(tenderplan_module.config, "tender_source_service_url", "http://127.0.0.1:8096"),
            patch.object(tenderplan_module.config, "tender_source_service_timeout_seconds", 5),
            patch("app.tenderplan.httpx.Client", return_value=fake_client),
            patch.object(TenderplanClient, "fetch_procurement", side_effect=AssertionError("fallback should not run")),
        ):
            result = fetch_tenderplan_source_sync("32616063169")

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.context, "Tenderplan context")
        self.assertEqual(result.downloaded_files[0].filename, "ТЗ.docx")
        self.assertEqual(result.downloaded_files[0].content, b"docx")
        self.assertEqual(result.downloaded_files[0].document_type, "technical_spec")
        self.assertEqual(result.downloaded_files[0].document_type_source, "filename+content")
        self.assertEqual(result.downloaded_files[0].content_document_types, ["technical_spec"])
        self.assertEqual(result.service_schema_version, "2.1")
        self.assertEqual(result.document_hints["primary_technical_spec"]["filename"], "ТЗ.docx")
        self.assertEqual(fake_client.get_url, "http://127.0.0.1:8096/v1/files/abc")

    def test_fetch_source_prefixes_shared_service_warnings(self) -> None:
        class FakeResponse:
            def __init__(self, payload=None, content: bytes = b""):
                self._payload = payload
                self.content = content

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def post(self, url, params=None):
                return FakeResponse(
                    payload={
                        "success": True,
                        "status": "partial",
                        "notice_number": "32616063169",
                        "context": "Tenderplan context",
                        "warnings": ["Не скачано файлов: 1"],
                        "files": [],
                        "download_errors": [{"name": "bad.docx", "error": "host_not_allowed"}],
                    }
                )

        with (
            patch.object(tenderplan_module.config, "tender_source_service_url", "http://127.0.0.1:8096"),
            patch.object(tenderplan_module.config, "tender_source_service_timeout_seconds", 5),
            patch("app.tenderplan.httpx.Client", return_value=FakeClient()),
        ):
            result = fetch_tenderplan_source_sync("32616063169")

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "partial")
        self.assertIn("Предупреждения источника документации", result.context)
        self.assertEqual(result.warnings, ["Не скачано файлов: 1"])

    def test_fetch_source_falls_back_to_local_client_when_shared_service_fails(self) -> None:
        fallback = TenderplanFetchResult(ok=True, status="ok", notice_number="32616063169", context="local")

        with (
            patch.object(tenderplan_module.config, "tender_source_service_url", "http://127.0.0.1:8096"),
            patch.object(tenderplan_module.config, "tenderplan_api_token", "token"),
            patch("app.tenderplan.fetch_tender_source_service_sync", return_value=TenderplanFetchResult(ok=False, status="service_failed", error="down")),
            patch.object(TenderplanClient, "fetch_procurement", return_value=fallback) as local_fetch,
        ):
            result = fetch_tenderplan_source_sync("32616063169")

        self.assertEqual(result.context, "local")
        local_fetch.assert_called_once_with("32616063169")


if __name__ == "__main__":
    unittest.main()
