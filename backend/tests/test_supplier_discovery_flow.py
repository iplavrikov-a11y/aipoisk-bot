from __future__ import annotations

import unittest
from types import SimpleNamespace

import app.supplier_search as supplier_search
from app.supplier_search import Candidate, CandidateMatch, CandidateRerank, ProcurementItem, ProcurementProfile


class SupplierDiscoveryFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_pages_adds_browser_rendered_page_when_http_has_no_contact(self) -> None:
        original_fetch_page = supplier_search.fetch_page
        original_browser = supplier_search.fetch_page_with_browser
        original_links = supplier_search.extract_internal_links

        async def fake_fetch_page(*args, **kwargs) -> dict:
            return {"url": "https://supplier.example", "html": "<html></html>", "text": "Каталог поставщика без опубликованного контакта"}

        async def fake_browser(url: str) -> dict:
            return {
                "url": url,
                "html": "<html></html>",
                "text": "Каталог поставщика. Контакты sales@supplier.example +7 999 111 22 33",
            }

        supplier_search.fetch_page = fake_fetch_page
        supplier_search.fetch_page_with_browser = fake_browser
        supplier_search.extract_internal_links = lambda *_args, **_kwargs: []
        try:
            pages = await supplier_search.collect_pages("https://supplier.example")
        finally:
            supplier_search.fetch_page = original_fetch_page
            supplier_search.fetch_page_with_browser = original_browser
            supplier_search.extract_internal_links = original_links

        self.assertEqual(pages[0]["text"], "Каталог поставщика. Контакты sales@supplier.example +7 999 111 22 33")
        self.assertEqual(len(pages), 1)

    async def test_build_procurement_profile_requires_ai_and_normalizes_items(self) -> None:
        original_call_llm = supplier_search.call_llm

        async def fake_call_llm(*args, **kwargs) -> str:
            return """
            {
              "summary": "Поставка двух товарных групп",
              "items": [
                {
                  "id": "main",
                  "name": "Сварочный полуавтомат",
                  "aliases": ["MIG/MAG"],
                  "category_terms": ["сварочное оборудование"],
                  "exact_terms": ["500А"],
                  "required_terms": ["500А"]
                },
                {"name": "Блок жидкостного охлаждения", "excluded_terms": ["доставка"]}
              ],
              "excluded_terms": ["ТОРГ-12"]
            }
            """

        supplier_search.call_llm = fake_call_llm
        try:
            profile = await supplier_search.build_procurement_profile(
                SimpleNamespace(has_active_ai_provider=True),
                "Поставка сварочного полуавтомата и блока охлаждения.",
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(profile.summary, "Поставка двух товарных групп")
        self.assertEqual([item.id for item in profile.items], ["main", "item-2"])
        self.assertEqual(profile.items[0].aliases, ("MIG/MAG",))
        self.assertEqual(profile.items[0].category_terms, ("сварочное оборудование",))
        self.assertEqual(profile.items[0].exact_terms, ("500А",))
        self.assertEqual(profile.excluded_terms, ("ТОРГ-12",))

    async def test_minprom_registry_requirement_is_ai_gated(self) -> None:
        original_call_llm = supplier_search.call_llm
        calls: list[dict] = []

        async def fake_call_llm(*args, **kwargs) -> str:
            calls.append(kwargs)
            return """
            {
              "required": true,
              "measure_type": "prohibition",
              "evidence": "Запрет действует. Требуются реестровые записи Минпромторга.",
              "reason": "В ТЗ прямо указано требование реестровой записи"
            }
            """

        supplier_search.call_llm = fake_call_llm
        try:
            requirement = await supplier_search.assess_minprom_registry_requirement(
                SimpleNamespace(has_active_ai_provider=True),
                "Нацрежим: запрет действует. Требуются реестровые записи Минпромторга.",
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertTrue(requirement.required)
        self.assertEqual(requirement.measure_type, "prohibition")
        self.assertEqual(calls[0]["routing_key"], "minprom_registry_requirement")

    async def test_minprom_registry_requirement_requires_ai_provider(self) -> None:
        with self.assertRaises(RuntimeError):
            await supplier_search.assess_minprom_registry_requirement(
                SimpleNamespace(has_active_ai_provider=False),
                "Требуются реестровые записи Минпромторга.",
            )

    async def test_discover_suppliers_passes_required_minprom_registry_context_to_review(self) -> None:
        originals = {
            "build_procurement_profile": supplier_search.build_procurement_profile,
            "build_supplier_queries": supplier_search.build_supplier_queries,
            "discover_candidates": supplier_search.discover_candidates,
            "ai_rerank_candidates": supplier_search.ai_rerank_candidates,
            "assess_minprom_registry_requirement": supplier_search.assess_minprom_registry_requirement,
            "discover_minprom_registry_context": supplier_search.discover_minprom_registry_context,
            "_review_candidates_until_target": supplier_search._review_candidates_until_target,
        }
        captured: dict = {}
        profile = ProcurementProfile(
            summary="Канат стальной",
            items=(ProcurementItem(id="item-1", name="Канат стальной", category_terms=("стальные канаты",)),),
        )
        candidate = Candidate(url="https://supplier.example", domain="supplier.example", title="поставщик")
        requirement = supplier_search.MinpromRegistryRequirement(
            required=True,
            measure_type="prohibition",
            evidence="Требуется реестровая запись",
            reason="Запрет действует",
        )
        registry_context = supplier_search.MinpromRegistryContext(
            requirement=requirement,
            queries=("стальные канаты ГИСП",),
            entries=({"registry_number": "123", "manufacturer": "Канатный завод", "product": "канат стальной"},),
            status="ok",
        )

        async def fake_profile(*args, **kwargs):
            return profile

        async def fake_queries(*args, **kwargs):
            return ["стальные канаты производитель"]

        async def fake_discover(*args, **kwargs):
            return [candidate], {"reports": [{"provider": "test", "status": "ok"}]}

        async def fake_rerank(*args, **kwargs):
            return CandidateRerank([candidate], {"status": "ok"})

        async def fake_assess(*args, **kwargs):
            return requirement

        async def fake_registry(*args, **kwargs):
            return registry_context

        async def fake_review(*args, registry_context=None, **kwargs):
            captured["registry_context"] = registry_context
            return (
                [
                    {
                        "company_name": "Канатный завод",
                        "site": "https://supplier.example",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.example",
                        "comments": "Есть реестровая запись Минпромторга.",
                        "evidence_status": "verified",
                        "quality_score": 90,
                    }
                ],
                [],
                {"reviewed_count": 1},
            )

        supplier_search.build_procurement_profile = fake_profile
        supplier_search.build_supplier_queries = fake_queries
        supplier_search.discover_candidates = fake_discover
        supplier_search.ai_rerank_candidates = fake_rerank
        supplier_search.assess_minprom_registry_requirement = fake_assess
        supplier_search.discover_minprom_registry_context = fake_registry
        supplier_search._review_candidates_until_target = fake_review
        try:
            accepted, evidence = await supplier_search.discover_suppliers(
                SimpleNamespace(has_active_ai_provider=True, supplier_search_provider_order="test"),
                "ТЗ: запрет действует, требуется реестровая запись Минпромторга.",
                target=1,
            )
        finally:
            for name, original in originals.items():
                setattr(supplier_search, name, original)

        self.assertEqual(len(accepted), 1)
        self.assertIs(captured["registry_context"], registry_context)
        self.assertTrue(evidence["minprom_registry"]["required"])
        self.assertEqual(evidence["minprom_registry"]["entries_count"], 1)

    async def test_ai_rerank_candidates_keeps_ai_ranked_supplier_candidates(self) -> None:
        original_call_llm = supplier_search.call_llm

        async def fake_call_llm(*args, **kwargs) -> str:
            return """
            {
              "ranked": [
                {"id": "1", "keep": true, "confidence": 0.91, "procurement_item_id": "item-1", "reason": "официальный дилер"},
                {"id": "0", "keep": false, "confidence": 10, "procurement_item_id": "item-1", "reason": "агрегатор"}
              ]
            }
            """

        candidates = [
            Candidate(url="https://bad.example", domain="bad.example", title="каталог"),
            Candidate(url="https://good.example", domain="good.example", title="производитель"),
        ]
        supplier_search.call_llm = fake_call_llm
        try:
            rerank = await supplier_search.ai_rerank_candidates(
                SimpleNamespace(has_active_ai_provider=True),
                ProcurementProfile(summary="ТЗ", items=(ProcurementItem(id="item-1", name="Товар"),)),
                candidates,
                target=1,
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual([candidate.domain for candidate in rerank.candidates], ["good.example"])
        self.assertEqual(rerank.candidates[0].procurement_item_id, "item-1")
        self.assertEqual(rerank.candidates[0].ai_rank_confidence, 91)

    async def test_ai_rerank_candidates_uses_ai_expansion_when_initial_pool_is_too_small(self) -> None:
        original_call_llm = supplier_search.call_llm
        calls = 0

        async def fake_call_llm(*args, **kwargs) -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                return """
                {
                  "ranked": [
                    {"id": "0", "keep": true, "confidence": 0.95, "procurement_item_id": "item-1", "reason": "точная страница"},
                    {"id": "1", "keep": true, "confidence": 0.88, "procurement_item_id": "item-1", "reason": "профильный поставщик"}
                  ]
                }
                """
            return """
            {
              "ranked": [
                {"id": "2", "keep": true, "confidence": 0.8, "procurement_item_id": "item-1", "reason": "производитель категории"},
                {"id": "3", "keep": true, "confidence": 0.78, "procurement_item_id": "item-1", "reason": "завод категории"},
                {"id": "4", "keep": true, "confidence": 0.76, "procurement_item_id": "item-1", "reason": "дилер категории"},
                {"id": "5", "keep": true, "confidence": 0.74, "procurement_item_id": "item-1", "reason": "поставщик категории"}
              ]
            }
            """

        candidates = [
            Candidate(
                url=f"https://supplier-{index}.example/catalog",
                domain=f"supplier-{index}.example",
                title="стальные канаты производитель",
                snippet="поставщик канатной продукции",
                source="test",
                query="производитель стальных канатов",
            )
            for index in range(8)
        ]
        supplier_search.call_llm = fake_call_llm
        try:
            rerank = await supplier_search.ai_rerank_candidates(
                SimpleNamespace(has_active_ai_provider=True),
                ProcurementProfile(
                    summary="Канат стальной",
                    items=(
                        ProcurementItem(
                            id="item-1",
                            name="Канат стальной",
                            category_terms=("стальные канаты", "канатная продукция"),
                        ),
                    ),
                ),
                candidates,
                target=3,
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(calls, 2)
        self.assertEqual([candidate.domain for candidate in rerank.candidates[:6]], [f"supplier-{index}.example" for index in range(6)])
        self.assertEqual(rerank.meta["initial_kept_count"], 2)
        self.assertEqual(rerank.meta["expanded_kept_count"], 4)

    async def test_build_supplier_queries_requires_ai_provider(self) -> None:
        with self.assertRaises(RuntimeError):
            await supplier_search.build_supplier_queries(
                SimpleNamespace(has_active_ai_provider=False),
                "Поставка промышленного оборудования",
                target=5,
            )

    async def test_discover_suppliers_requires_ai_provider(self) -> None:
        with self.assertRaises(RuntimeError):
            await supplier_search.discover_suppliers(
                SimpleNamespace(has_active_ai_provider=False),
                "Поставка промышленного оборудования",
                target=5,
            )

    async def test_discover_candidates_filters_previously_found_domains(self) -> None:
        original_ddgs = supplier_search._search_with_ddgs
        captured: dict = {}

        async def fake_ddgs(queries: list[str], max_results: int, *, existing_domains=None):
            captured["existing_domains"] = set(existing_domains or set())
            return [
                Candidate(url="https://old.example/catalog", domain="old.example", title="old", source="ddgs", query=queries[0]),
                Candidate(url="https://new.example/catalog", domain="new.example", title="new", source="ddgs", query=queries[0]),
            ]

        supplier_search._search_with_ddgs = fake_ddgs
        try:
            candidates, _meta = await supplier_search.discover_candidates(
                SimpleNamespace(supplier_search_provider_order="ddgs"),
                ["поставщик"],
                max_results=10,
                excluded_domains={"old.example"},
            )
        finally:
            supplier_search._search_with_ddgs = original_ddgs

        self.assertIn("old.example", captured["existing_domains"])
        self.assertEqual([candidate.domain for candidate in candidates], ["new.example"])

    async def test_build_supplier_queries_prefers_ai_queries_over_deterministic_fallback(self) -> None:
        original_call_llm = supplier_search.call_llm
        profile = ProcurementProfile(
            summary="Лазерный станок резки металла",
            items=(ProcurementItem(id="item-1", name="лазерный станок резки металла"),),
        )

        async def fake_call_llm(*args, **kwargs) -> str:
            return '{"queries": ["лазерный станок резки металла производитель", "официальный дилер лазерных станков"]}'

        supplier_search.call_llm = fake_call_llm
        try:
            queries = await supplier_search.build_supplier_queries(
                SimpleNamespace(has_active_ai_provider=True),
                "Техническое задание. Поставка лазерного станка резки металла.",
                target=5,
                profile=profile,
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(queries[:2], ["лазерный станок резки металла производитель", "официальный дилер лазерных станков"])

    async def test_build_supplier_queries_revises_overly_exact_query_set_with_ai(self) -> None:
        original_call_llm = supplier_search.call_llm
        calls: list[str] = []
        profile = ProcurementProfile(
            summary="Поставка стального каната 31 мм ЛК-РО",
            items=(
                ProcurementItem(
                    id="item-1",
                    name="Канат стальной",
                    aliases=("стальной канат ЛК-РО",),
                    required_terms=("диаметр 31 мм", "тип ЛК-РО", "ГОСТ 7668-80"),
                    category_terms=("стальные канаты", "канатная продукция"),
                    exact_terms=("31 мм", "ЛК-РО", "ГОСТ 7668-80"),
                ),
            ),
        )

        async def fake_call_llm(_settings, prompt: str, *args, **kwargs) -> str:
            calls.append(prompt)
            if len(calls) == 1:
                return """
                {"queries": [
                  "производитель стальных канатов ЛК-РО 31 мм",
                  "завод стальных канатов 31 мм ГОСТ 7668-80",
                  "купить канат стальной 31 мм ЛК-РО оптом"
                ]}
                """
            self.assertIn("слишком узко", prompt)
            return """
            {"queries": [
              "производитель стальных канатов",
              "завод канатной продукции",
              "поставщик стальных канатов оптом",
              "дилер стальных канатов",
              "метизный завод стальные канаты"
            ]}
            """

        supplier_search.call_llm = fake_call_llm
        try:
            queries = await supplier_search.build_supplier_queries(
                SimpleNamespace(has_active_ai_provider=True),
                "Поставка стального каната 31 мм ЛК-РО",
                target=15,
                profile=profile,
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(len(calls), 2)
        self.assertIn("производитель стальных канатов", queries)
        self.assertIn("завод канатной продукции", queries)
        self.assertTrue(any("31 мм" not in query and "ЛК-РО" not in query for query in queries))

    async def test_build_supplier_queries_retries_empty_message_ai_failure(self) -> None:
        original_call_llm = supplier_search.call_llm
        calls = 0
        profile = ProcurementProfile(
            summary="Сотовый поликарбонат",
            items=(ProcurementItem(id="item-1", name="сотовый поликарбонат"),),
        )

        async def fake_call_llm(*args, **kwargs) -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError()
            return '{"queries": ["сотовый поликарбонат производитель", "поликарбонатные панели поставщик"]}'

        supplier_search.call_llm = fake_call_llm
        try:
            queries = await supplier_search.build_supplier_queries(
                SimpleNamespace(has_active_ai_provider=True),
                "Поставка сотового поликарбоната",
                target=5,
                profile=profile,
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(calls, 2)
        self.assertEqual(queries[:2], ["сотовый поликарбонат производитель", "поликарбонатные панели поставщик"])

    async def test_build_supplier_queries_failure_includes_exception_type_after_retry(self) -> None:
        original_call_llm = supplier_search.call_llm
        calls = 0
        profile = ProcurementProfile(
            summary="Сотовый поликарбонат",
            items=(ProcurementItem(id="item-1", name="сотовый поликарбонат"),),
        )

        async def fake_call_llm(*args, **kwargs) -> str:
            nonlocal calls
            calls += 1
            raise TimeoutError()

        supplier_search.call_llm = fake_call_llm
        try:
            with self.assertRaises(RuntimeError) as raised:
                await supplier_search.build_supplier_queries(
                    SimpleNamespace(has_active_ai_provider=True),
                    "Поставка сотового поликарбоната",
                    target=5,
                    profile=profile,
                )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(calls, 2)
        self.assertIn("after retry", str(raised.exception))
        self.assertIn("TimeoutError", str(raised.exception))

    async def test_verify_candidate_does_not_fallback_to_keyword_acceptance_after_ai_reject(self) -> None:
        original_collect_pages = supplier_search.collect_pages
        original_ai_verify = supplier_search.ai_verify

        async def fake_collect_pages(url: str) -> list[dict]:
            return [
                {
                    "url": url,
                    "text": "Каталог. Сварочный полуавтомат MIG/MAG купить. Производитель. +7 999 111 22 33 sales@supplier.example",
                }
            ]

        async def fake_ai_verify(*args, **kwargs) -> dict:
            return {
                "action": "reject",
                "confidence": 20,
                "site_type": "directory",
                "product_fit": "category",
                "comments": "ИИ видит справочник, а не сайт поставщика.",
            }

        supplier_search.collect_pages = fake_collect_pages
        supplier_search.ai_verify = fake_ai_verify
        try:
            result = await supplier_search.verify_candidate(
                SimpleNamespace(has_active_ai_provider=True),
                Candidate(
                    url="https://supplier.example/catalog",
                    domain="supplier.example",
                    title="Сварочный полуавтомат купить",
                    snippet="производитель, каталог, контакты",
                    source="test",
                    query="сварочный полуавтомат поставщик",
                ),
                "Поставка сварочного полуавтомата MIG/MAG",
            )
        finally:
            supplier_search.collect_pages = original_collect_pages
            supplier_search.ai_verify = original_ai_verify

        self.assertIsNotNone(result)
        self.assertEqual(result["evidence_status"], "weak")
        self.assertIn("ИИ", result["comments"])

    async def test_verify_candidate_accepts_only_after_ai_accepts_when_ai_is_configured(self) -> None:
        original_collect_pages = supplier_search.collect_pages
        original_ai_verify = supplier_search.ai_verify

        async def fake_collect_pages(url: str) -> list[dict]:
            return [
                {
                    "url": url,
                    "text": "Официальный сайт производителя. Сварочный полуавтомат MIG/MAG. Контакты +7 999 111 22 33 sales@supplier.example",
                }
            ]

        async def fake_ai_verify(*args, **kwargs) -> dict:
            return {
                "action": "accept",
                "confidence": 0.92,
                "site_type": "manufacturer",
                "product_fit": "exact",
                "company_name": "Supplier",
                "status": "завод",
                "product": "Сварочный полуавтомат MIG/MAG",
                "phone": "+7 999 111 22 33",
                "email": "sales@supplier.example",
                "evidence_url": "https://supplier.example/catalog",
                "contact_url": "https://supplier.example/catalog",
                "evidence_snippet": "Сварочный полуавтомат MIG/MAG",
                "contact_evidence_snippet": "+7 999 111 22 33 sales@supplier.example",
                "comments": "ИИ подтвердил сайт производителя и контакт.",
            }

        supplier_search.collect_pages = fake_collect_pages
        supplier_search.ai_verify = fake_ai_verify
        try:
            result = await supplier_search.verify_candidate(
                SimpleNamespace(has_active_ai_provider=True),
                Candidate(
                    url="https://supplier.example/catalog",
                    domain="supplier.example",
                    title="Сварочный полуавтомат MIG/MAG",
                    snippet="производитель, каталог, контакты",
                    source="test",
                    query="сварочный полуавтомат поставщик",
                ),
                "Поставка сварочного полуавтомата MIG/MAG",
            )
        finally:
            supplier_search.collect_pages = original_collect_pages
            supplier_search.ai_verify = original_ai_verify

        self.assertIsNotNone(result)
        self.assertEqual(result["evidence_status"], "verified")
        self.assertEqual(result["company_name"], "Supplier")
        self.assertEqual(result["match_level"], "exact")
        self.assertEqual(result["ai_confidence"], 92)

    async def test_verify_candidate_replaces_ai_contact_placeholders_with_extracted_contacts(self) -> None:
        original_collect_pages = supplier_search.collect_pages
        original_ai_verify = supplier_search.ai_verify

        async def fake_collect_pages(url: str) -> list[dict]:
            return [
                {
                    "url": url,
                    "text": "Официальный сайт производителя. Сотовый поликарбонат. Контакты +7 999 111 22 33 sales@supplier.example",
                }
            ]

        async def fake_ai_verify(*args, **kwargs) -> dict:
            return {
                "action": "accept",
                "confidence": 0.92,
                "site_type": "manufacturer",
                "product_fit": "exact",
                "company_name": "Supplier",
                "status": "завод",
                "product": "Сотовый поликарбонат",
                "phone": "не найдено на главной",
                "email": "не найдено на главной",
                "evidence_url": "https://supplier.example/catalog",
                "contact_url": "https://supplier.example/catalog",
                "evidence_snippet": "Сотовый поликарбонат",
                "contact_evidence_snippet": "+7 999 111 22 33 sales@supplier.example",
                "comments": "ИИ подтвердил сайт производителя и контакт.",
            }

        supplier_search.collect_pages = fake_collect_pages
        supplier_search.ai_verify = fake_ai_verify
        try:
            result = await supplier_search.verify_candidate(
                SimpleNamespace(has_active_ai_provider=True),
                Candidate(
                    url="https://supplier.example/catalog",
                    domain="supplier.example",
                    title="Сотовый поликарбонат",
                    snippet="производитель, каталог, контакты",
                    source="test",
                    query="сотовый поликарбонат поставщик",
                ),
                "Поставка сотового поликарбоната",
            )
        finally:
            supplier_search.collect_pages = original_collect_pages
            supplier_search.ai_verify = original_ai_verify

        self.assertIsNotNone(result)
        self.assertEqual(result["phone"], "+7 (999) 111-22-33")
        self.assertEqual(result["email"], "sales@supplier.example")

    def test_verified_phone_normalizes_and_rejects_broken_numbers(self) -> None:
        self.assertEqual(supplier_search._verified_phone("8 800 119 00 00", []), "+7 (800) 119-00-00")
        self.assertEqual(supplier_search._verified_phone("8000\n1190000", []), "")
        self.assertEqual(
            supplier_search._verified_phone("не найдено", ["+7 999 111 22 33"]),
            "+7 (999) 111-22-33",
        )

    async def test_verify_candidate_rejects_ai_contact_placeholders_without_extracted_contacts(self) -> None:
        original_collect_pages = supplier_search.collect_pages
        original_ai_verify = supplier_search.ai_verify

        async def fake_collect_pages(url: str) -> list[dict]:
            return [{"url": url, "text": "Официальный сайт производителя. Сотовый поликарбонат."}]

        async def fake_ai_verify(*args, **kwargs) -> dict:
            return {
                "action": "accept",
                "confidence": 0.92,
                "site_type": "manufacturer",
                "product_fit": "exact",
                "company_name": "Supplier",
                "status": "завод",
                "product": "Сотовый поликарбонат",
                "phone": "не найдено на главной",
                "email": "не найдено на главной",
                "evidence_url": "https://supplier.example/catalog",
                "contact_url": "https://supplier.example/catalog",
                "evidence_snippet": "Сотовый поликарбонат",
                "contact_evidence_snippet": "не найдено на главной",
                "comments": "ИИ подтвердил сайт производителя и контакт.",
            }

        supplier_search.collect_pages = fake_collect_pages
        supplier_search.ai_verify = fake_ai_verify
        try:
            result = await supplier_search.verify_candidate(
                SimpleNamespace(has_active_ai_provider=True),
                Candidate(
                    url="https://supplier.example/catalog",
                    domain="supplier.example",
                    title="Сотовый поликарбонат",
                    snippet="производитель, каталог",
                    source="test",
                    query="сотовый поликарбонат поставщик",
                ),
                "Поставка сотового поликарбоната",
            )
        finally:
            supplier_search.collect_pages = original_collect_pages
            supplier_search.ai_verify = original_ai_verify

        self.assertIsNotNone(result)
        self.assertEqual(result["evidence_status"], "weak")
        self.assertIn("телефон", result["comments"].lower())

    async def test_ai_verify_prompt_forbids_full_match_claims_for_non_exact_fit(self) -> None:
        original_call_llm = supplier_search.call_llm
        captured: dict[str, str] = {}

        async def fake_call_llm(_settings, prompt: str, *args, **kwargs) -> str:
            captured["prompt"] = prompt
            return '{"action": "reject", "comments": "test"}'

        supplier_search.call_llm = fake_call_llm
        try:
            await supplier_search.ai_verify(
                SimpleNamespace(has_active_ai_provider=True),
                Candidate(
                    url="https://supplier.example/catalog",
                    domain="supplier.example",
                    title="Каталог поставщика",
                    snippet="производитель, каталог, контакты",
                    source="test",
                    query="сварочный полуавтомат поставщик",
                ),
                "Поставка сварочного полуавтомата MIG/MAG",
                [
                    {
                        "url": "https://supplier.example/catalog",
                        "text": "Каталог поставщика. Контакты +7 999 111 22 33 sales@supplier.example",
                    }
                ],
                ["sales@supplier.example"],
                ["+7 999 111 22 33"],
                CandidateMatch(True, "profile", "Промышленное оборудование", "Профильная категория"),
            )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertIn("Классификация product_fit", captured["prompt"])
        self.assertIn('запрещено писать "полностью соответствует"', captured["prompt"])

    def test_supplier_quality_score_caps_non_exact_product_fit(self) -> None:
        base = {
            "evidence_status": "verified",
            "site": "https://supplier.example/catalog",
            "evidence_url": "https://supplier.example/catalog",
            "contact_url": "https://supplier.example/contacts",
            "phone": "+7 999 111 22 33",
            "email": "sales@supplier.example",
            "search_query": "сварочный полуавтомат поставщик",
            "company_name": "Supplier",
        }

        exact_score = supplier_search._supplier_quality_score({**base, "match_level": "exact", "product_fit": "exact"})
        category_score = supplier_search._supplier_quality_score({**base, "match_level": "profile", "product_fit": "category"})
        profile_score = supplier_search._supplier_quality_score({**base, "match_level": "profile", "product_fit": "profile"})
        analog_score = supplier_search._supplier_quality_score({**base, "match_level": "adjacent", "product_fit": "analog"})

        self.assertGreaterEqual(exact_score, 80)
        self.assertLess(category_score, 80)
        self.assertLess(profile_score, 80)
        self.assertLess(analog_score, 80)

    async def test_discover_suppliers_returns_already_reviewed_verified_results_above_minimum(self) -> None:
        original_build = supplier_search.build_supplier_queries
        original_profile = supplier_search.build_procurement_profile
        original_candidates = supplier_search.discover_candidates
        original_rerank = supplier_search.ai_rerank_candidates
        original_verify = supplier_search.verify_candidate
        original_assess = supplier_search.assess_minprom_registry_requirement
        calls: list[str] = []
        progress_events: list[tuple[int, str]] = []

        async def fake_profile(settings, context: str) -> ProcurementProfile:
            return ProcurementProfile(
                summary="Промышленное оборудование",
                items=(ProcurementItem(id="item-1", name="промышленное оборудование"),),
            )

        async def fake_build(settings, context: str, target: int, profile=None) -> list[str]:
            return ["query"]

        async def fake_candidates(settings, queries: list[str], max_results: int, **kwargs):
            return (
                [
                    Candidate(
                        url=f"https://supplier-{index}.ru",
                        domain=f"supplier-{index}.ru",
                        title="производитель",
                        snippet="оборудование",
                        source="test",
                        query="query",
                    )
                    for index in range(30)
                ],
                {"provider_order": ["test"], "reports": []},
            )

        async def fake_rerank(settings, profile: ProcurementProfile, candidates: list[Candidate], target: int) -> CandidateRerank:
            return CandidateRerank(candidates=candidates, meta={"status": "test", "kept_count": len(candidates)})

        async def fake_assess(settings, context: str):
            return supplier_search.MinpromRegistryRequirement(required=False, measure_type="unknown", reason="Требование не найдено")

        async def fake_verify(settings, candidate: Candidate, context: str, *, profile=None, registry_context=None):
            calls.append(candidate.domain)
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_url": candidate.url,
                "contact_url": candidate.url,
                "phone": "+7 999 111 22 33",
                "email": "sales@example.ru",
                "evidence_status": "verified",
                "match_level": "exact",
                "source": candidate.source,
                "search_query": candidate.query,
            }

        async def fake_progress(progress: int, message: str) -> None:
            progress_events.append((progress, message))

        supplier_search.build_supplier_queries = fake_build
        supplier_search.build_procurement_profile = fake_profile
        supplier_search.discover_candidates = fake_candidates
        supplier_search.ai_rerank_candidates = fake_rerank
        supplier_search.assess_minprom_registry_requirement = fake_assess
        supplier_search.verify_candidate = fake_verify
        try:
            accepted, evidence = await supplier_search.discover_suppliers(
                SimpleNamespace(has_active_ai_provider=True),
                "поставка промышленного оборудования",
                target=3,
                progress_callback=fake_progress,
            )
        finally:
            supplier_search.build_supplier_queries = original_build
            supplier_search.build_procurement_profile = original_profile
            supplier_search.discover_candidates = original_candidates
            supplier_search.ai_rerank_candidates = original_rerank
            supplier_search.assess_minprom_registry_requirement = original_assess
            supplier_search.verify_candidate = original_verify

        self.assertEqual(len(accepted), 12)
        self.assertGreaterEqual(len(accepted), 3)
        self.assertLess(len(calls), 30)
        self.assertTrue(evidence["ai_required"])
        self.assertTrue(evidence["ai_used"])
        self.assertIn("supplier_candidate_verifier", evidence["ai_required_stages"])
        self.assertTrue(evidence["review"]["early_stop"])
        self.assertEqual(evidence["accepted_count"], 12)
        self.assertGreaterEqual(len(progress_events), 5)
        self.assertIn("Анализирую ТЗ", progress_events[0][1])
        self.assertTrue(any("Проверяю сайты" in message or "Проверено сайтов" in message for _, message in progress_events))

    async def test_discover_suppliers_runs_ai_recovery_search_when_first_round_underfills(self) -> None:
        original_build = supplier_search.build_supplier_queries
        original_profile = supplier_search.build_procurement_profile
        original_candidates = supplier_search.discover_candidates
        original_rerank = supplier_search.ai_rerank_candidates
        original_verify = supplier_search.verify_candidate
        original_assess = supplier_search.assess_minprom_registry_requirement
        original_recovery = supplier_search._build_supplier_recovery_queries_with_ai
        search_calls: list[list[str]] = []
        recovery_inputs: dict = {}
        progress_events: list[tuple[int, str]] = []

        async def fake_profile(settings, context: str) -> ProcurementProfile:
            return ProcurementProfile(
                summary="Промышленная номенклатура",
                items=(
                    ProcurementItem(
                        id="item-1",
                        name="промышленная номенклатура",
                        category_terms=("промышленная номенклатура", "заводы производители"),
                    ),
                ),
            )

        async def fake_build(settings, context: str, target: int, profile=None) -> list[str]:
            return ["точная позиция поставщик"]

        async def fake_candidates(settings, queries: list[str], max_results: int, **kwargs):
            search_calls.append(list(queries))
            if len(search_calls) == 1:
                candidates = [
                    Candidate(url=f"https://first-{index}.ru", domain=f"first-{index}.ru", title="поставщик", source="test", query=queries[0])
                    for index in range(4)
                ]
            else:
                candidates = [
                    Candidate(
                        url=f"https://recovery-{index}.ru",
                        domain=f"recovery-{index}.ru",
                        title="производитель категории",
                        source="test",
                        query=queries[0],
                    )
                    for index in range(4)
                ]
            return candidates, {"provider_order": ["test"], "reports": [{"provider": "test", "status": "ok"}]}

        async def fake_rerank(settings, profile: ProcurementProfile, candidates: list[Candidate], target: int) -> CandidateRerank:
            return CandidateRerank(candidates=candidates, meta={"status": "test", "kept_count": len(candidates)})

        async def fake_assess(settings, context: str):
            return supplier_search.MinpromRegistryRequirement(required=False, measure_type="unknown", reason="Требование не найдено")

        async def fake_recovery(settings, context: str, profile: ProcurementProfile, initial_queries, reviewed, accepted, target: int) -> list[str]:
            recovery_inputs["initial_queries"] = list(initial_queries)
            recovery_inputs["reviewed_count"] = len(reviewed)
            recovery_inputs["accepted_count"] = len(accepted)
            return ["производитель промышленной номенклатуры"]

        async def fake_verify(settings, candidate: Candidate, context: str, *, profile=None, registry_context=None):
            if candidate.domain == "first-0.ru" or candidate.domain.startswith("recovery-"):
                return {
                    "company_name": candidate.domain,
                    "site": candidate.url,
                    "evidence_url": candidate.url,
                    "contact_url": candidate.url,
                    "phone": "+7 999 111 22 33",
                    "email": "sales@example.ru",
                    "evidence_status": "verified",
                    "match_level": "exact",
                    "product_fit": "exact",
                    "ai_confidence": 95,
                    "source": candidate.source,
                    "search_query": candidate.query,
                }
            return {
                "company_name": candidate.domain,
                "site": candidate.url,
                "evidence_status": "weak",
                "source": candidate.source,
                "search_query": candidate.query,
                "comments": "AI-аудит отклонил кандидата.",
            }

        async def fake_progress(progress: int, message: str) -> None:
            progress_events.append((progress, message))

        supplier_search.build_supplier_queries = fake_build
        supplier_search.build_procurement_profile = fake_profile
        supplier_search.discover_candidates = fake_candidates
        supplier_search.ai_rerank_candidates = fake_rerank
        supplier_search.assess_minprom_registry_requirement = fake_assess
        supplier_search._build_supplier_recovery_queries_with_ai = fake_recovery
        supplier_search.verify_candidate = fake_verify
        try:
            accepted, evidence = await supplier_search.discover_suppliers(
                SimpleNamespace(has_active_ai_provider=True),
                "поставка промышленной номенклатуры",
                target=3,
                progress_callback=fake_progress,
            )
        finally:
            supplier_search.build_supplier_queries = original_build
            supplier_search.build_procurement_profile = original_profile
            supplier_search.discover_candidates = original_candidates
            supplier_search.ai_rerank_candidates = original_rerank
            supplier_search.assess_minprom_registry_requirement = original_assess
            supplier_search._build_supplier_recovery_queries_with_ai = original_recovery
            supplier_search.verify_candidate = original_verify

        self.assertGreaterEqual(len(accepted), 3)
        self.assertEqual(len(search_calls), 2)
        self.assertEqual(search_calls[1], ["производитель промышленной номенклатуры"])
        self.assertEqual(recovery_inputs["initial_queries"], ["точная позиция поставщик"])
        self.assertEqual(recovery_inputs["accepted_count"], 1)
        self.assertTrue(evidence["recovery_rounds"])
        self.assertEqual(evidence["recovery_rounds"][0]["status"], "ok")
        self.assertTrue(any("Расширяю поиск" in message for _, message in progress_events))

    async def test_ai_rerank_failure_includes_exception_type_when_message_is_empty(self) -> None:
        original_call_llm = supplier_search.call_llm
        calls = 0

        async def fake_call_llm(*args, **kwargs) -> str:
            nonlocal calls
            calls += 1
            raise TimeoutError()

        supplier_search.call_llm = fake_call_llm
        try:
            with self.assertRaises(RuntimeError) as raised:
                await supplier_search.ai_rerank_candidates(
                    SimpleNamespace(has_active_ai_provider=True),
                    ProcurementProfile(summary="ТЗ", items=(ProcurementItem(id="item-1", name="Товар"),)),
                    [Candidate(url="https://supplier.example", domain="supplier.example", title="поставщик")],
                    target=1,
                )
        finally:
            supplier_search.call_llm = original_call_llm

        self.assertEqual(calls, 2)
        self.assertIn("after retry", str(raised.exception))
        self.assertIn("TimeoutError", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
