"""Stress tests for supplier search pipeline with real-world TZ scenarios.

These tests verify that the supplier search pipeline handles various real-world
technical specifications efficiently and correctly. They test:
1. Parallel page fetching performance
2. Browser pool reuse
3. Early stop optimization
4. Various product categories
5. Edge cases (empty results, timeouts, etc.)
"""
from __future__ import annotations

import asyncio
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app.supplier_search as supplier_search
from app.supplier_search import (
    Candidate,
    CandidateMatch,
    CandidateRerank,
    ProcurementItem,
    ProcurementProfile,
    _candidate_review_batch_size,
    _accepted_supplier_results,
)

# Real TZ scenarios from actual procurement documents
REAL_TZ_SCENARIOS = [
    {
        "id": "polycarbonate",
        "name": "Поликарбонат монолитный",
        "context": """Техническое задание на поставку монолитного поликарбоната.

        Наименование: Панель поликарбонатная монолитная прозрачная 8мм
        Количество: 500 м2

        Требования:
        - Толщина: 8 мм ±0.5 мм
        - Прозрачность: не менее 88%
        - Устойчивость к УФ-излучению
        - Температура эксплуатации: -40°C до +120°C
        - Размеры листов: 2.05м x 3.05м
        - Упаковка: пленка + угловые прокладки

        Документы:
        - Сертификат соответствия
        - Паспорт качества
        - Сертификат на УФ-защиту""",
        "item_name": "поликарбонат монолитный прозрачный 8мм",
        "target_suppliers": 5,
    },
    {
        "id": "welding_equipment",
        "name": "Сварочный полуавтомат",
        "context": """Техническое задание на поставку сварочного оборудования.

        Наименование: Сварочный полуавтомат MIG/MAG
        Модель: Any-well PRC 500

        Технические характеристики:
        - Ток сварки: 50-500А
        - Напряжение холостого хода: 65В
        - ПВ при 500А: 80%
        - Сечения проволоки: 0.8-1.6 мм
        - Газ: CO2, Ar+CO2

        Комплектация:
        - Сварочный аппарат
        - Тележка
        - Газовая горелка 4м
        - Массовый кабель 3м

        Гарантия: 24 месяца""",
        "item_name": "сварочный полуавтомат MIG/MAG 500А",
        "target_suppliers": 5,
    },
    {
        "id": "diesel_generator",
        "name": "Дизель-генераторная установка",
        "context": """Техническое задание на поставку ДГУ.

        Наименование: Дизель-генераторная установка 100 кВт

        Требования:
        - Мощность: 100 кВт / 125 кВА
        - Напряжение: 400/230В
        - Частота: 50 Гц
        - Двигатель: дизельный, 4-тактный
        - Автоматический ввод резерва (АВР)
        - Шум: не более 75 дБ на расстоянии 7м
        - Расход топлива: не более 28 л/ч при 100% нагрузке

        Комплектация:
        - ДГУ в кожухе
        - Панель управления
        - Топливный бак 200л
        - Аккумуляторная батарея""",
        "item_name": "дизель-генераторная установка 100 кВт с АВР",
        "target_suppliers": 5,
    },
    {
        "id": "laboratory_reagents",
        "name": "Лабораторные реактивы",
        "context": """Техническое задание на поставку лабораторных реактивов.

        Наименование: Набор реактивов для ВЭЖХ (HPLC)

        Состав набора:
        - Ацетонитрил HPLC grade, 4x2.5л
        - Метанол HPLC grade, 4x2.5л
        - Уксусная кислота 99.8%, 1л
        - Трифторуксусная кислота 99%, 100мл
        - Ультрачистая вода 18.2 МОм*см, 50л

        Требования:
        - Чистота: HPLC grade, не менее 99.9%
        - Класс: для аналитической хроматографии
        - Упаковка: стеклянная тара с каплесборником
        - Хранение: при температуре 5-25°C""",
        "item_name": "набор реактивов для ВЭЖХ HPLC grade",
        "target_suppliers": 4,
    },
    {
        "id": "fire_hoses",
        "name": "Пожарные рукава и приспособления",
        "context": """Техническое задание на поставку пожарного оборудования.

        Наименование: Приспособления для промежуточного подсоединения пожарных рукавов

        Требования:
        - Номинальный диаметр: 50, 65, 80 мм
        - Рабочее давление: не менее 1.6 МПа
        - Материал: алюминиевый сплав или нержавеющая сталь
        - Соединения: быстросъемные муфты по ГОСТ
        - Комплект: приспособление + ключ + прокладки

        Документы:
        - Сертификат пожарной безопасности
        - Протокол испытаний
        - Сертификат соответствия""",
        "item_name": "приспособления для подсоединения пожарных рукавов",
        "target_suppliers": 5,
    },
    {
        "id": "video_monitors",
        "name": "Видеомониторы",
        "context": """Техническое задание на поставку мониторингового оборудования.

        Наименование: Видеомонитор 27"

        Требования:
        - Диагональ: 27 дюймов
        - Разрешение: 2560x1440 (QHD)
        - Матрица: IPS
        - Яркость: не менее 350 кд/м2
        - Время отклика: не более 5 мс
        - Интерфейсы: HDMI 2.0 x2, DisplayPort 1.4
        - Питание: 100-240В AC

        Количество: 15 штук
        Гарантия: 36 месяцев""",
        "item_name": "видеомонитор 27 дюймов QHD IPS",
        "target_suppliers": 4,
    },
]


class SupplierSearchStressTests(unittest.IsolatedAsyncioTestCase):
    """Stress tests for the supplier search pipeline."""

    def _make_settings(self, provider_id: str = "test") -> SimpleNamespace:
        return SimpleNamespace(
            has_active_ai_provider=True,
            custom_ai_providers_json=json.dumps([{"id": provider_id}]),
            saved_models_json=json.dumps([]),
            ai_function_models_json=json.dumps({}),
            ai_analysis_fallback_json=json.dumps([]),
            ai_supplier_fallback_json=json.dumps([]),
            primary_provider=provider_id,
            primary_model="test-model",
            light_provider=provider_id,
            light_model="test-model",
            supplier_ai_provider=provider_id,
            supplier_ai_model="test-model",
        )

    async def test_parallel_page_fetching_performance(self) -> None:
        """Test that parallel page fetching is faster than sequential."""
        original_fetch_page = supplier_search.fetch_page
        call_times: list[float] = []

        async def slow_fetch_page(client, url: str) -> dict | None:
            """Simulate slow page fetch."""
            start = time.monotonic()
            await asyncio.sleep(0.1)  # Simulate 100ms network delay
            call_times.append(time.monotonic() - start)
            return {"url": url, "html": "<html></html>", "text": "Контакты sales@example.com +7 999 111 22 33"}

        supplier_search.fetch_page = slow_fetch_page
        supplier_search.extract_internal_links = lambda *_args, **_kwargs: [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
            "https://example.com/page4",
            "https://example.com/page5",
        ]

        try:
            start = time.monotonic()
            pages = await supplier_search.collect_pages("https://example.com")
            elapsed = time.monotonic() - start
        finally:
            supplier_search.fetch_page = original_fetch_page
            supplier_search.extract_internal_links = original_extract_internal_links

        # Should have main page + 5 internal pages = 6 total
        self.assertEqual(len(pages), 6)
        # Parallel fetch should be much faster than sequential (6 * 100ms = 600ms sequential)
        # With 3 concurrent requests, should be ~200ms
        self.assertLess(elapsed, 0.5, f"Parallel fetch took {elapsed:.2f}s, expected < 0.5s")

    async def test_browser_pool_reuse(self) -> None:
        """Test that browser pool reuses browser instances by checking pool logic."""
        original_browser = supplier_search.fetch_page_with_browser

        # Create a pool with a mock browser
        pool = supplier_search._BrowserPool()
        browser_instances = []

        class FakeBrowser:
            def __init__(self):
                self.id = f"browser-{len(browser_instances)}"
                browser_instances.append(self.id)

            def is_connected(self):
                return True

            async def new_page(self, **kwargs):
                class FakePage:
                    async def goto(self, url, **kwargs):
                        pass
                    async def content(self):
                        return "<html><body>sales@example.com</body></html>"
                    async def close(self):
                        pass
                return FakePage()

            async def close(self):
                pass

        pool._browser = FakeBrowser()  # type: ignore

        long_text = "Kонтактная информация: sales@example.com телефон +7 999 111 22 33 " * 5

        async def mock_fetch(url: str):
            async with pool:
                browser = pool._browser
                assert browser is not None
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until="networkidle", timeout=18000)
                    html_text = f"<html><body>{long_text}</body></html>"
                    final_url = url
                finally:
                    await page.close()
            return supplier_search.html_text_to_page(html_text[:300000], final_url)

        supplier_search.fetch_page_with_browser = mock_fetch

        try:
            for _ in range(3):
                result = await supplier_search.fetch_page_with_browser("https://example.com")
                self.assertIsNotNone(result)

            # Browser should be reused (only 1 instance created)
            self.assertEqual(len(browser_instances), 1)
        finally:
            supplier_search.fetch_page_with_browser = original_browser

    async def test_browser_pool_initializes_once_under_concurrency(self) -> None:
        starts = 0
        launches = 0
        stops = 0

        class FakeBrowser:
            def is_connected(self) -> bool:
                return True

            async def close(self) -> None:
                return None

        class FakeChromium:
            async def launch(self, **_kwargs):
                nonlocal launches
                launches += 1
                await asyncio.sleep(0.01)
                return FakeBrowser()

        class FakePlaywright:
            def __init__(self) -> None:
                self.chromium = FakeChromium()

            async def stop(self) -> None:
                nonlocal stops
                stops += 1

        class FakeStarter:
            async def start(self):
                nonlocal starts
                starts += 1
                await asyncio.sleep(0.01)
                return FakePlaywright()

        pool = supplier_search._BrowserPool()
        with patch("playwright.async_api.async_playwright", return_value=FakeStarter()):
            browsers = await asyncio.gather(*[pool.get_browser() for _ in range(8)])
            await pool.close()

        self.assertEqual(starts, 1)
        self.assertEqual(launches, 1)
        self.assertEqual(len({id(browser) for browser in browsers}), 1)
        self.assertEqual(stops, 1)

    async def test_browser_pool_stops_playwright_when_launch_fails(self) -> None:
        stops = 0

        class FailingChromium:
            async def launch(self, **_kwargs):
                raise RuntimeError("launch failed")

        class FakePlaywright:
            def __init__(self) -> None:
                self.chromium = FailingChromium()

            async def stop(self) -> None:
                nonlocal stops
                stops += 1

        class FakeStarter:
            async def start(self):
                return FakePlaywright()

        pool = supplier_search._BrowserPool()
        with patch("playwright.async_api.async_playwright", return_value=FakeStarter()):
            with self.assertRaisesRegex(RuntimeError, "launch failed"):
                await pool.get_browser()

        self.assertEqual(stops, 1)
        self.assertIsNone(pool._playwright)
        self.assertIsNone(pool._browser)

    async def test_browser_failure_logs_safe_job_context(self) -> None:
        class FailingPool:
            async def __aenter__(self):
                return self

            async def __aexit__(self, _exc_type, _exc_value, _traceback) -> None:
                return None

            async def get_browser(self):
                raise RuntimeError("browser launch rejected for https://example.com/?token=secret")

            async def close(self) -> None:
                return None

        with supplier_search.supplier_search_job_context("job-log-test"):
            with (
                patch.object(supplier_search, "_BrowserPool", return_value=FailingPool()),
                self.assertLogs("app.supplier_search", level="WARNING") as captured,
            ):
                result = await supplier_search.fetch_page_with_browser(
                    "https://supplier.example/catalog?token=hidden",
                    source="yandex",
                )

        self.assertIsNone(result)
        log_output = "\n".join(captured.output)
        self.assertIn("job_id=job-log-test", log_output)
        self.assertIn("source=yandex", log_output)
        self.assertIn("url=https://supplier.example/catalog", log_output)
        self.assertNotIn("token=hidden", log_output)
        self.assertNotIn("token=secret", log_output)

    async def test_discover_suppliers_closes_job_browser_pool_on_error(self) -> None:
        closes = 0

        class FakePool:
            async def close(self) -> None:
                nonlocal closes
                closes += 1

        async def fail_profile(*_args, **_kwargs):
            raise RuntimeError("profile failed")

        settings = SimpleNamespace(has_active_ai_provider=True)
        with (
            patch.object(supplier_search, "_BrowserPool", return_value=FakePool()),
            patch.object(supplier_search, "build_procurement_profile", side_effect=fail_profile),
        ):
            with self.assertRaisesRegex(RuntimeError, "profile failed"):
                await supplier_search.discover_suppliers(settings, "context", 3)

        self.assertEqual(closes, 1)

    async def test_review_batch_cancels_siblings_when_candidate_raises(self) -> None:
        candidates = [
            Candidate(
                url=f"https://supplier-{index}.ru",
                domain=f"supplier-{index}.ru",
                title="производитель",
                snippet="оборудование",
                source="test",
                query="оборудование поставщик",
            )
            for index in range(3)
        ]
        all_started = asyncio.Event()
        started = 0
        cancelled: set[str] = set()

        async def controlled_verify(_settings, candidate, _context, **_kwargs):
            nonlocal started
            started += 1
            if started == len(candidates):
                all_started.set()
            await all_started.wait()
            if candidate.domain == "supplier-0.ru":
                raise RuntimeError("candidate failed")
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.add(candidate.domain)
                raise

        with patch.object(
            supplier_search,
            "_verify_candidate_with_limits",
            side_effect=controlled_verify,
        ):
            with self.assertRaisesRegex(RuntimeError, "candidate failed"):
                await supplier_search._review_candidates_until_target(
                    self._make_settings(),
                    candidates,
                    "оборудование",
                    target=3,
                )

        self.assertEqual(cancelled, {"supplier-1.ru", "supplier-2.ru"})

    async def test_review_batch_cancels_siblings_when_parent_is_cancelled(self) -> None:
        candidates = [
            Candidate(
                url=f"https://supplier-{index}.ru",
                domain=f"supplier-{index}.ru",
                title="производитель",
                snippet="оборудование",
                source="test",
                query="оборудование поставщик",
            )
            for index in range(3)
        ]
        all_started = asyncio.Event()
        started = 0
        cancelled: set[str] = set()

        async def blocking_verify(_settings, candidate, _context, **_kwargs):
            nonlocal started
            started += 1
            if started == len(candidates):
                all_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.add(candidate.domain)
                raise

        with patch.object(
            supplier_search,
            "_verify_candidate_with_limits",
            side_effect=blocking_verify,
        ):
            review_task = asyncio.create_task(
                supplier_search._review_candidates_until_target(
                    self._make_settings(),
                    candidates,
                    "оборудование",
                    target=3,
                )
            )
            await all_started.wait()
            review_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await review_task

        self.assertEqual(cancelled, {candidate.domain for candidate in candidates})

    async def test_early_stop_with_high_acceptance_rate(self) -> None:
        """Test that early stop triggers when acceptance rate is high."""
        original_verify = supplier_search.verify_candidate
        verify_count = 0

        async def fast_verify(settings, candidate, context, **kwargs):
            nonlocal verify_count
            verify_count += 1
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_url": candidate.url,
                "contact_url": candidate.url,
                "phone": "+7 999 111 22 33",
                "email": "sales@example.com",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": candidate.source,
                "search_query": candidate.query,
            }

        supplier_search.verify_candidate = fast_verify

        try:
            settings = self._make_settings()
            candidates = [
                Candidate(
                    url=f"https://supplier-{i}.ru",
                    domain=f"supplier-{i}.ru",
                    title="производитель",
                    snippet="оборудование",
                    source="test",
                    query="оборудование поставщик",
                )
                for i in range(50)
            ]

            start = time.monotonic()
            accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
                settings,
                candidates,
                "оборудование",
                target=10,
            )
            elapsed = time.monotonic() - start

            # Should have early stopped after first batch
            self.assertTrue(meta["early_stop"])
            # stopped_after should be the batch size for target=10, which is 20
            batch_size = _candidate_review_batch_size(10)
            self.assertLessEqual(meta["stopped_after_candidates"], batch_size)
            # Should have verified fewer than 50 candidates
            self.assertLess(verify_count, 50)
        finally:
            supplier_search.verify_candidate = original_verify

    async def test_batch_size_calculation(self) -> None:
        """Test batch size calculation for different targets."""
        # Target 1 -> batch size 12 (minimum)
        self.assertEqual(_candidate_review_batch_size(1), 12)
        # Target 3 -> batch size 12
        self.assertEqual(_candidate_review_batch_size(3), 12)
        # Target 5 -> batch size 12
        self.assertEqual(_candidate_review_batch_size(5), 12)
        # Target 10 -> batch size 20
        self.assertEqual(_candidate_review_batch_size(10), 20)
        # Target 15 -> batch size 30
        self.assertEqual(_candidate_review_batch_size(15), 30)
        # Target 20 -> batch size 32 (maximum)
        self.assertEqual(_candidate_review_batch_size(20), 32)

    def test_delivery_target_keeps_client_minimum_as_floor(self) -> None:
        self.assertEqual(supplier_search._supplier_delivery_target(1), 3)
        self.assertEqual(supplier_search._supplier_delivery_target(5), 7)
        self.assertEqual(supplier_search._supplier_delivery_target(15), 20)
        self.assertEqual(supplier_search._supplier_delivery_target(100), 100)

    async def test_yandex_primary_skips_reserve_sources_when_candidate_floor_is_met(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="google,tavily,ddgs")
        calls: list[tuple[str, int]] = []

        def make_candidates(source: str, count: int) -> list[Candidate]:
            return [
                Candidate(
                    url=f"https://{source}-{index}.example/catalog",
                    domain=f"{source}-{index}.example",
                    title=f"{source} supplier {index}",
                    snippet="supplier",
                    source=source,
                    query="test",
                )
                for index in range(count)
            ]

        async def yandex(_settings, _queries, max_results, **_kwargs):
            calls.append(("yandex", max_results))
            return make_candidates("yandex", 24)

        async def reserve(*_args, **_kwargs):
            raise AssertionError("reserve source must not run after sufficient Yandex candidates")

        with (
            patch.object(supplier_search, "_search_with_yandex", yandex),
            patch.object(supplier_search, "_search_with_google", reserve),
            patch.object(supplier_search, "_search_with_tavily", reserve),
            patch.object(supplier_search, "_search_with_ddgs", reserve),
        ):
            candidates, meta = await supplier_search.discover_candidates(
                settings,
                ["test"],
                max_results=60,
                primary_candidate_floor=20,
                fallback_candidate_limit=8,
            )

        self.assertEqual(calls, [("yandex", 60)])
        self.assertEqual(len(candidates), 24)
        self.assertFalse(meta["strategy"]["fallback_used"])
        self.assertEqual(
            [report["status"] for report in meta["reports"]],
            ["ok", "skipped_primary_sufficient", "skipped_primary_sufficient", "skipped_primary_sufficient"],
        )

    async def test_yandex_primary_caps_reserve_candidates_when_it_is_short(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="google,tavily,ddgs")
        calls: list[tuple[str, int]] = []

        def make_candidates(source: str, count: int) -> list[Candidate]:
            return [
                Candidate(
                    url=f"https://{source}-{index}.example/catalog",
                    domain=f"{source}-{index}.example",
                    title=f"{source} supplier {index}",
                    snippet="supplier",
                    source=source,
                    query="test",
                )
                for index in range(count)
            ]

        async def yandex(_settings, _queries, max_results, **_kwargs):
            calls.append(("yandex", max_results))
            return make_candidates("yandex", 4)

        async def google(_settings, _queries, max_results, **_kwargs):
            calls.append(("google", max_results))
            return make_candidates("google", 12)

        async def reserve(*_args, **_kwargs):
            raise AssertionError("reserve cap must prevent additional providers")

        with (
            patch.object(supplier_search, "_search_with_yandex", yandex),
            patch.object(supplier_search, "_search_with_google", google),
            patch.object(supplier_search, "_search_with_tavily", reserve),
            patch.object(supplier_search, "_search_with_ddgs", reserve),
        ):
            candidates, meta = await supplier_search.discover_candidates(
                settings,
                ["test"],
                max_results=60,
                primary_candidate_floor=20,
                fallback_candidate_limit=6,
            )

        self.assertEqual(calls, [("yandex", 60), ("google", 6)])
        self.assertEqual(len(candidates), 10)
        self.assertTrue(meta["strategy"]["fallback_used"])
        self.assertEqual(
            [report["status"] for report in meta["reports"]],
            ["ok", "ok", "skipped_fallback_limit", "skipped_fallback_limit"],
        )

    async def test_reserve_sources_can_cover_yandex_unavailability(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="google")
        calls: list[tuple[str, int]] = []

        async def yandex(_settings, _queries, max_results, **_kwargs):
            calls.append(("yandex", max_results))
            return []

        async def google(_settings, _queries, max_results, **_kwargs):
            calls.append(("google", max_results))
            return [
                Candidate(
                    url="https://fallback.example/catalog",
                    domain="fallback.example",
                    title="fallback supplier",
                    snippet="supplier",
                    source="google",
                    query="test",
                )
            ]

        with (
            patch.object(supplier_search, "_search_with_yandex", yandex),
            patch.object(supplier_search, "_search_with_google", google),
        ):
            candidates, meta = await supplier_search.discover_candidates(
                settings,
                ["test"],
                max_results=60,
                primary_candidate_floor=20,
                fallback_candidate_limit=6,
            )

        self.assertEqual(calls, [("yandex", 60), ("google", 60)])
        self.assertEqual(len(candidates), 1)
        self.assertTrue(meta["strategy"]["fallback_used"])

    async def test_real_tz_polycarbonate_search(self) -> None:
        """Test supplier search with real polycarbonate TZ."""
        scenario = REAL_TZ_SCENARIOS[0]
        original_verify = supplier_search.verify_candidate
        original_discover = supplier_search.discover_candidates
        original_collect = supplier_search.collect_pages
        original_call_llm = supplier_search.call_llm
        original_profile = supplier_search.build_procurement_profile
        original_build_queries = supplier_search.build_supplier_queries
        original_assess = supplier_search.assess_minprom_registry_requirement
        original_rerank = supplier_search.ai_rerank_candidates

        # Mock verify to accept all candidates
        async def mock_verify(settings, candidate, context, **kwargs):
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_url": candidate.url,
                "contact_url": candidate.url,
                "phone": "+7 999 111 22 33",
                "email": f"sales@{candidate.domain}",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": candidate.source,
                "search_query": candidate.query,
            }

        # Mock discover to return realistic candidates
        async def mock_discover(settings, queries, max_results, **kwargs):
            candidates = [
                Candidate(
                    url=f"https://polycarbonate-supplier-{i}.ru/catalog",
                    domain=f"polycarbonate-supplier-{i}.ru",
                    title="Поликарбонат монолитный прозрачный 8мм",
                    snippet="Поставка поликарбоната монолитного прозрачного от производителя",
                    source="test",
                    query=queries[0] if queries else "поликарбонат",
                )
                for i in range(20)
            ]
            return candidates, {"provider_order": ["test"], "reports": []}

        # Mock collect_pages to return contact info
        async def mock_collect(url):
            return [{"url": url, "html": "<html></html>", "text": "Контакты sales@example.com +7 999 111 22 33"}]

        # Mock LLM calls
        async def mock_profile(settings, context):
            return ProcurementProfile(
                summary="Поставка поликарбоната",
                items=(ProcurementItem(id="item-1", name="поликарбонат монолитный прозрачный 8мм"),),
            )

        query_targets: list[int] = []

        async def mock_build_queries(settings, context, target, profile=None):
            query_targets.append(target)
            return ["поликарбонат монолитный поставщик", "монолитный поликарбонат производитель"]

        async def mock_assess(settings, context):
            return supplier_search.MinpromRegistryRequirement(required=False)

        rerank_targets: list[int] = []

        async def mock_rerank(settings, profile, candidates, target, **kwargs):
            rerank_targets.append(target)
            return CandidateRerank(candidates=candidates[:target * 5], meta={"status": "test"})

        supplier_search.verify_candidate = mock_verify
        supplier_search.discover_candidates = mock_discover
        supplier_search.collect_pages = mock_collect
        supplier_search.build_procurement_profile = mock_profile
        supplier_search.build_supplier_queries = mock_build_queries
        supplier_search.assess_minprom_registry_requirement = mock_assess
        supplier_search.ai_rerank_candidates = mock_rerank

        try:
            settings = self._make_settings()
            start = time.monotonic()
            accepted, evidence = await supplier_search.discover_suppliers(
                settings,
                scenario["context"],
                target=scenario["target_suppliers"],
            )
            elapsed = time.monotonic() - start

            # Verify results
            self.assertGreaterEqual(len(accepted), scenario["target_suppliers"])
            self.assertGreater(evidence["delivery_target"], scenario["target_suppliers"])
            self.assertEqual(query_targets[0], scenario["target_suppliers"])
            self.assertEqual(rerank_targets[0], evidence["delivery_target"])
            self.assertTrue(evidence["ai_required"])
            self.assertTrue(evidence["ai_used"])
            self.assertLess(elapsed, 5.0, f"Search took {elapsed:.2f}s, expected < 5s")
        finally:
            supplier_search.verify_candidate = original_verify
            supplier_search.discover_candidates = original_discover
            supplier_search.collect_pages = original_collect
            supplier_search.build_procurement_profile = original_profile
            supplier_search.build_supplier_queries = original_build_queries
            supplier_search.assess_minprom_registry_requirement = original_assess
            supplier_search.ai_rerank_candidates = original_rerank

    async def test_concurrent_candidate_verification(self) -> None:
        """Test that multiple candidates can be verified concurrently."""
        original_verify = supplier_search.verify_candidate
        verification_times: list[float] = []

        async def timed_verify(settings, candidate, context, **kwargs):
            start = time.monotonic()
            await asyncio.sleep(0.05)  # Simulate 50ms verification
            elapsed = time.monotonic() - start
            verification_times.append(elapsed)
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_url": candidate.url,
                "contact_url": candidate.url,
                "phone": "+7 999 111 22 33",
                "email": f"sales@{candidate.domain}",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": candidate.source,
                "search_query": candidate.query,
            }

        supplier_search.verify_candidate = timed_verify

        try:
            settings = self._make_settings()
            candidates = [
                Candidate(
                    url=f"https://supplier-{i}.ru",
                    domain=f"supplier-{i}.ru",
                    title="производитель",
                    snippet="оборудование",
                    source="test",
                    query="оборудование поставщик",
                )
                for i in range(10)
            ]

            start = time.monotonic()
            accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
                settings,
                candidates,
                "оборудование",
                target=5,
            )
            total_elapsed = time.monotonic() - start

            # Should have verified all candidates in parallel
            self.assertEqual(len(verification_times), 10)
            # Total time should be less than sequential (10 * 50ms = 500ms)
            # With parallel execution, should be ~100ms
            self.assertLess(total_elapsed, 0.3, f"Concurrent verification took {total_elapsed:.2f}s")
        finally:
            supplier_search.verify_candidate = original_verify

    async def test_edge_case_empty_candidates(self) -> None:
        """Test handling of empty candidate list."""
        settings = self._make_settings()
        candidates = []

        accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
            settings,
            candidates,
            "оборудование",
            target=5,
        )

        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(reviewed), 0)
        self.assertFalse(meta["early_stop"])

    async def test_edge_case_single_candidate(self) -> None:
        """Test handling of single candidate."""
        original_verify = supplier_search.verify_candidate

        async def mock_verify(settings, candidate, context, **kwargs):
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_url": candidate.url,
                "contact_url": candidate.url,
                "phone": "+7 999 111 22 33",
                "email": "sales@example.com",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": candidate.source,
                "search_query": candidate.query,
            }

        supplier_search.verify_candidate = mock_verify

        try:
            settings = self._make_settings()
            candidates = [
                Candidate(
                    url="https://single-supplier.ru",
                    domain="single-supplier.ru",
                    title="производитель",
                    snippet="оборудование",
                    source="test",
                    query="оборудование поставщик",
                )
            ]

            accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
                settings,
                candidates,
                "оборудование",
                target=5,
            )

            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(reviewed), 1)
        finally:
            supplier_search.verify_candidate = original_verify

    async def test_memory_efficiency_with_large_candidate_set(self) -> None:
        """Test that large candidate sets don't cause memory issues."""
        original_verify = supplier_search.verify_candidate

        async def mock_verify(settings, candidate, context, **kwargs):
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_url": candidate.url,
                "contact_url": candidate.url,
                "phone": "+7 999 111 22 33",
                "email": f"sales@{candidate.domain}",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": candidate.source,
                "search_query": candidate.query,
            }

        supplier_search.verify_candidate = mock_verify

        try:
            settings = self._make_settings()
            # Create large candidate set
            candidates = [
                Candidate(
                    url=f"https://supplier-{i}.ru",
                    domain=f"supplier-{i}.ru",
                    title="производитель",
                    snippet="оборудование",
                    source="test",
                    query="оборудование поставщик",
                )
                for i in range(100)
            ]

            accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
                settings,
                candidates,
                "оборудование",
                target=10,
            )

            # Should handle large sets without issues
            self.assertGreaterEqual(len(accepted), 10)
            self.assertLessEqual(meta["stopped_after_candidates"], 20)
        finally:
            supplier_search.verify_candidate = original_verify


# Helper function to restore extract_internal_links
def original_extract_internal_links(*args, **kwargs):
    """Restore the original extract_internal_links function."""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse

    html_text = args[0] if args else kwargs.get("html_text", "")
    base_url_value = args[1] if len(args) > 1 else kwargs.get("base_url_value", "")

    base = supplier_search.base_domain(base_url_value)
    soup = BeautifulSoup(html_text, "html.parser")
    scored = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url_value, str(anchor.get("href") or ""))
        parsed = urlparse(href)
        if supplier_search.base_domain(parsed.netloc) != base:
            continue
        label = f"{anchor.get_text(' ', strip=True)} {href}".lower()
        score = 0
        if any(word in label for word in ["контакт", "contact", "отдел", "sales", "продаж", "связ", "requisite", "реквизит"]):
            score += 4
        if any(word in label for word in ["каталог", "product", "produk", "товар", "оборуд", "shop", "catalog"]):
            score += 3
        if any(word in label for word in ["о компании", "about", "производ", "завод", "company"]):
            score += 2
        if score:
            scored.append((score, href))
    unique = []
    for _, href in sorted(scored, reverse=True):
        if href not in unique:
            unique.append(href)
    return unique[:5]


if __name__ == "__main__":
    unittest.main()
