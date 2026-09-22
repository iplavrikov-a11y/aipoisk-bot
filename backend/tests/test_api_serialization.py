from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import Job, Client, ClientTelegramAccount, WebUser, SystemSettings
from app.main import supplier_to_dict, job_to_dict, client_to_dict, telegram_account_to_dict, web_user_to_admin_dict


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

    def test_job_to_dict_includes_ai_provider_and_model(self) -> None:
        job = Job(
            id="job-ai-test",
            mode="supplier_search",
            title="Поиск поставщиков",
            ai_provider="openrouter",
            ai_model="anthropic/claude-3.5-sonnet",
        )
        data = job_to_dict(job)
        self.assertEqual(data["ai_provider"], "openrouter")
        self.assertEqual(data["ai_provider_name"], "OpenRouter")
        self.assertEqual(data["ai_model"], "anthropic/claude-3.5-sonnet")
        self.assertEqual(data["ai_label"], "OpenRouter · anthropic/claude-3.5-sonnet")

    def test_client_and_account_serialization_includes_created_at(self) -> None:
        created = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        client = Client(
            id="client-test-1",
            name="Тестовый клиент",
            created_at=created,
        )
        account = ClientTelegramAccount(
            id="tg-acc-1",
            client_id="client-test-1",
            telegram_id="123456",
            username="testmanager",
            name="Менеджер",
            created_at=created,
        )
        web_user = WebUser(
            id="web-u-1",
            client_id="client-test-1",
            email="manager@client.ru",
            created_at=created,
            last_login_at=created,
        )
        c_dict = client_to_dict(client)
        self.assertIn("created_at", c_dict)
        self.assertEqual(c_dict["created_at"], created.isoformat())

        acc_dict = telegram_account_to_dict(account)
        self.assertIn("created_at", acc_dict)
        self.assertEqual(acc_dict["created_at"], created.isoformat())

        web_dict = web_user_to_admin_dict(web_user)
        self.assertIn("created_at", web_dict)
        self.assertIn("last_login_at", web_dict)
        self.assertEqual(web_dict["created_at"], created.isoformat())
        self.assertEqual(web_dict["last_login_at"], created.isoformat())


if __name__ == "__main__":
    unittest.main()
