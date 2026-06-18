from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import app.supplier_search as supplier_search
from app.supplier_search import Candidate


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "supplier_eval_cases.json"


class SupplierEvalSuiteTests(unittest.IsolatedAsyncioTestCase):
    async def test_multi_domain_supplier_pipeline_accepts_ai_verified_suppliers(self) -> None:
        cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        original_call_llm = supplier_search.call_llm
        original_discover = supplier_search.discover_candidates
        original_collect = supplier_search.collect_pages

        async def fake_call_llm(_settings, prompt: str, *args, routing_key: str = "", **kwargs) -> str:
            case = next(item for item in cases if item["context"][:40] in prompt or item["item_name"] in prompt)
            if routing_key == "supplier_procurement_profile":
                return json.dumps(
                    {
                        "summary": f"Поставка: {case['item_name']}",
                        "items": [{"id": "item-1", "name": case["item_name"], "aliases": []}],
                        "excluded_terms": ["доставка", "сроки", "гарантия"],
                    },
                    ensure_ascii=False,
                )
            if routing_key == "supplier_query_generation":
                return json.dumps({"queries": [f"{case['item_name']} поставщик официальный сайт"]}, ensure_ascii=False)
            if routing_key == "minprom_registry_requirement":
                return json.dumps(
                    {
                        "required": False,
                        "measure_type": "unknown",
                        "evidence": "",
                        "reason": "Требование реестровой записи Минпромторга не указано",
                    },
                    ensure_ascii=False,
                )
            if routing_key == "supplier_candidate_reranker":
                return json.dumps(
                    {
                        "ranked": [
                            {
                                "id": "0",
                                "keep": True,
                                "confidence": 0.9,
                                "procurement_item_id": "item-1",
                                "reason": "профильный поставщик",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            if routing_key == "supplier_candidate_verifier":
                return json.dumps(
                    {
                        "action": "accept",
                        "confidence": 0.91,
                        "site_type": "supplier",
                        "product_fit": "exact",
                        "procurement_item_id": "item-1",
                        "procurement_item_name": case["item_name"],
                        "company_name": case["supplier_domain"],
                        "status": "поставщик",
                        "product": case["item_name"],
                        "email": f"sales@{case['supplier_domain']}",
                        "phone": "+7 999 111 22 33",
                        "evidence_url": f"https://{case['supplier_domain']}/catalog",
                        "contact_url": f"https://{case['supplier_domain']}/contacts",
                        "evidence_snippet": case["item_name"],
                        "contact_evidence_snippet": f"sales@{case['supplier_domain']}",
                        "comments": "ИИ подтвердил поставщика.",
                    },
                    ensure_ascii=False,
                )
            raise AssertionError(f"unexpected routing key {routing_key}")

        async def fake_discover(_settings, queries: list[str], max_results: int, **kwargs):
            query = queries[0]
            case = next(item for item in cases if item["item_name"] in query)
            return (
                [
                    Candidate(
                        url=f"https://{case['supplier_domain']}/catalog",
                        domain=case["supplier_domain"],
                        title=case["item_name"],
                        snippet="поставщик официальный сайт контакты",
                        source="eval",
                        query=query,
                    )
                ],
                {"provider_order": ["eval"], "reports": [{"provider": "eval", "status": "ok", "returned": 1}]},
            )

        async def fake_collect(url: str) -> list[dict]:
            domain = url.split("/")[2]
            case = next(item for item in cases if item["supplier_domain"] == domain)
            return [
                {
                    "url": url,
                    "text": f"{case['item_name']} поставщик официальный сайт sales@{domain} +7 999 111 22 33",
                }
            ]

        supplier_search.call_llm = fake_call_llm
        supplier_search.discover_candidates = fake_discover
        supplier_search.collect_pages = fake_collect
        try:
            for case in cases:
                accepted, evidence = await supplier_search.discover_suppliers(
                    SimpleNamespace(has_active_ai_provider=True),
                    case["context"],
                    target=1,
                )
                self.assertEqual(len(accepted), 1, case["id"])
                self.assertEqual(accepted[0]["site_type"], "supplier", case["id"])
                self.assertEqual(accepted[0]["product_fit"], "exact", case["id"])
                self.assertTrue(evidence["ai_required"], case["id"])
                self.assertTrue(evidence["ai_used"], case["id"])
                self.assertEqual(evidence["procurement_profile"]["items"][0]["name"], case["item_name"], case["id"])
                self.assertFalse(evidence["minprom_registry"]["required"], case["id"])
        finally:
            supplier_search.call_llm = original_call_llm
            supplier_search.discover_candidates = original_discover
            supplier_search.collect_pages = original_collect


if __name__ == "__main__":
    unittest.main()
