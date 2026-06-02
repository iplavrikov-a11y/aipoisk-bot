from __future__ import annotations

import unittest
from types import SimpleNamespace

import app.supplier_search as supplier_search
from app.supplier_search import Candidate


class SupplierDiscoveryFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_discover_suppliers_stops_after_enough_ranked_verified_results(self) -> None:
        original_build = supplier_search.build_supplier_queries
        original_candidates = supplier_search.discover_candidates
        original_verify = supplier_search.verify_candidate
        calls: list[str] = []

        async def fake_build(settings, context: str, target: int) -> list[str]:
            return ["query"]

        async def fake_candidates(settings, queries: list[str], max_results: int):
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

        async def fake_verify(settings, candidate: Candidate, context: str):
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

        supplier_search.build_supplier_queries = fake_build
        supplier_search.discover_candidates = fake_candidates
        supplier_search.verify_candidate = fake_verify
        try:
            accepted, evidence = await supplier_search.discover_suppliers(
                SimpleNamespace(has_active_ai_provider=False),
                "поставка промышленного оборудования",
                target=3,
            )
        finally:
            supplier_search.build_supplier_queries = original_build
            supplier_search.discover_candidates = original_candidates
            supplier_search.verify_candidate = original_verify

        self.assertEqual(len(accepted), 3)
        self.assertLess(len(calls), 30)
        self.assertTrue(evidence["review"]["early_stop"])


if __name__ == "__main__":
    unittest.main()
