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
        )

        data = supplier_to_dict(supplier)

        self.assertEqual(data["match_level"], "exact")
        self.assertEqual(data["source"], "yandex")
        self.assertEqual(data["search_query"], '"ГМ-70" поставщик')


if __name__ == "__main__":
    unittest.main()
