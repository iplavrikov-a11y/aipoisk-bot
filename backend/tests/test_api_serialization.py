from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.main import supplier_to_dict


class ApiSerializationTests(unittest.TestCase):
    def test_supplier_to_dict_includes_search_audit_fields(self) -> None:
        supplier = SimpleNamespace(
            company_name="Поставщик",
            region="Москва",
            status="поставщик",
            product="ГМ-70",
            phone="+7 999 111 22 33",
            email="sales@example.ru",
            site="https://supplier.ru/catalog",
            evidence_url="https://supplier.ru/catalog/gm-70",
            contact_url="https://supplier.ru/contacts",
            comments="Проверено",
            evidence_status="verified",
            match_level="exact",
            source="yandex",
            search_query='"ГМ-70" поставщик',
            quality_score=94,
            quality_tier="high",
            procurement_item_id="item-1",
            procurement_item="ГМ-70",
            ai_confidence=91,
            site_type="manufacturer",
            product_fit="exact",
            evidence_snippet="ГМ-70 в каталоге",
            contact_evidence_snippet="sales@example.ru",
            ai_rank_confidence=87,
            ai_rank_reason="официальный сайт",
        )

        data = supplier_to_dict(supplier)

        self.assertEqual(data["match_level"], "exact")
        self.assertEqual(data["source"], "yandex")
        self.assertEqual(data["search_query"], '"ГМ-70" поставщик')
        self.assertEqual(data["quality_score"], 94)
        self.assertEqual(data["quality_tier"], "high")
        self.assertEqual(data["procurement_item_id"], "item-1")
        self.assertEqual(data["procurement_item"], "ГМ-70")
        self.assertEqual(data["ai_confidence"], 91)
        self.assertEqual(data["site_type"], "manufacturer")
        self.assertEqual(data["product_fit"], "exact")
        self.assertEqual(data["evidence_snippet"], "ГМ-70 в каталоге")
        self.assertEqual(data["contact_evidence_snippet"], "sales@example.ru")
        self.assertEqual(data["ai_rank_confidence"], 87)
        self.assertEqual(data["ai_rank_reason"], "официальный сайт")


if __name__ == "__main__":
    unittest.main()
