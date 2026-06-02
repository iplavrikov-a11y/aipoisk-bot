from __future__ import annotations

import base64
import unittest
from types import SimpleNamespace

from app.supplier_search import (
    _expand_search_queries,
    _merge_candidates,
    _parse_google_items,
    _parse_yandex_xml,
    _provider_order,
)


class SearchSourceTests(unittest.TestCase):
    def test_provider_order_prefers_yandex_google_before_tavily_and_ddgs(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="")

        self.assertEqual(_provider_order(settings), ["yandex", "google", "tavily", "ddgs"])

    def test_provider_order_accepts_custom_supported_order(self) -> None:
        settings = SimpleNamespace(supplier_search_provider_order="google,unknown,yandex,ddgs")

        self.assertEqual(_provider_order(settings), ["google", "yandex", "ddgs"])

    def test_parse_yandex_xml_builds_candidates_and_filters_blocked_domains(self) -> None:
        xml = """
        <yandexsearch>
          <response>
            <results>
              <grouping>
                <group>
                  <doc>
                    <url>https://spaszavod.ru/catalog</url>
                    <title>Спасательный завод</title>
                    <passages><passage>горноспасательное оборудование</passage></passages>
                  </doc>
                </group>
                <group>
                  <doc>
                    <url>https://market.yandex.ru/product/1</url>
                    <title>Маркет</title>
                  </doc>
                </group>
              </grouping>
            </results>
          </response>
        </yandexsearch>
        """

        candidates = _parse_yandex_xml(xml, query="горноспасательное оборудование")

        self.assertEqual([item.domain for item in candidates], ["spaszavod.ru"])
        self.assertEqual(candidates[0].source, "yandex")
        self.assertEqual(candidates[0].query, "горноспасательное оборудование")

    def test_parse_yandex_xml_accepts_base64_raw_data(self) -> None:
        raw = "<yandexsearch><response><results><grouping><group><doc><url>https://techspas.ru/</url><title>Techspas</title></doc></group></grouping></results></response></yandexsearch>"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")

        candidates = _parse_yandex_xml(encoded, query="test")

        self.assertEqual([item.domain for item in candidates], ["techspas.ru"])

    def test_parse_google_items_builds_candidates_and_filters_blocked_domains(self) -> None:
        candidates = _parse_google_items(
            [
                {
                    "link": "https://npopuls.ru/catalog/gm-70",
                    "title": "НПО Пульс",
                    "snippet": "пожарная арматура",
                },
                {
                    "link": "https://zakupki.gov.ru/notice/1",
                    "title": "Закупка",
                    "snippet": "",
                },
            ],
            query="ГМ-70",
        )

        self.assertEqual([item.domain for item in candidates], ["npopuls.ru"])
        self.assertEqual(candidates[0].source, "google")
        self.assertEqual(candidates[0].query, "ГМ-70")

    def test_merge_candidates_keeps_first_domain_source(self) -> None:
        first = _parse_google_items(
            [{"link": "https://npopuls.ru/a", "title": "first", "snippet": ""}],
            query="first",
        )
        second = _parse_google_items(
            [{"link": "https://www.npopuls.ru/b", "title": "second", "snippet": ""}],
            query="second",
        )

        merged = _merge_candidates(first, second, max_results=10)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].title, "first")

    def test_expand_search_queries_interleaves_base_queries_before_variants(self) -> None:
        long_query = '"Приспособление для промежуточного подсоединения пожарных рукавов к трубопроводу (Сверло шахтное универсальное)" поставщик'
        expanded = _expand_search_queries(
            [
                long_query,
                '"СШУ-22" купить',
                "горноспасательное оборудование завод поставщик купить",
            ],
            max_queries=5,
        )

        self.assertIn('"СШУ-22" купить', expanded[:3])
        self.assertIn("горноспасательное оборудование завод поставщик купить", expanded[:3])


if __name__ == "__main__":
    unittest.main()
