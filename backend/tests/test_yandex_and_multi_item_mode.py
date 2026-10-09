from __future__ import annotations

import base64
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from app.models import Job, Base
from app.supplier_search import (
    ProcurementItem,
    ProcurementProfile,
    _accepted_supplier_results,
    _parse_yandex_xml,
)
from app.jobs import create_job
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class YandexAndMultiItemModeTests(unittest.TestCase):
    def test_parse_yandex_xml_base64_and_plain(self):
        sample_xml = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response date="20261009T220000">
    <results>
      <grouping>
        <group>
          <doc id="1">
            <url>https://example-supplier.ru/catalog/item</url>
            <domain>example-supplier.ru</domain>
            <title>Поставщик стройматериалов</title>
            <passages><passage>Купить оптом ламинат и линолеум от производителя</passage></passages>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""
        encoded_b64 = base64.b64encode(sample_xml.encode("utf-8")).decode("ascii")

        # 1. Parsing base64-encoded rawData
        candidates_from_b64 = _parse_yandex_xml(encoded_b64, query="ламинат оптом")
        self.assertEqual(len(candidates_from_b64), 1)
        self.assertEqual(candidates_from_b64[0].domain, "example-supplier.ru")
        self.assertIn("ламинат", candidates_from_b64[0].snippet)

        # 2. Parsing plain xml string
        candidates_from_plain = _parse_yandex_xml(sample_xml, query="ламинат оптом")
        self.assertEqual(len(candidates_from_plain), 1)
        self.assertEqual(candidates_from_plain[0].domain, "example-supplier.ru")

    def test_multi_item_balanced_mode_divides_quota(self):
        profile = ProcurementProfile(
            summary="Отделочные материалы",
            items=[
                ProcurementItem(id="item-1", name="Линолеум"),
                ProcurementItem(id="item-2", name="Ламинат"),
            ],
        )
        reviewed = []
        # 10 suppliers for item 1
        for i in range(10):
            reviewed.append({
                "site": f"https://linoleum-{i}.ru",
                "company_name": f"Линолеум Завод {i}",
                "evidence_status": "verified",
                "quality_score": 85,
                "procurement_item_id": "item-1",
                "procurement_item": "Линолеум",
                "product_fit": "exact",
            })
        # 10 suppliers for item 2
        for i in range(10):
            reviewed.append({
                "site": f"https://laminat-{i}.ru",
                "company_name": f"Ламинат Завод {i}",
                "evidence_status": "verified",
                "quality_score": 85,
                "procurement_item_id": "item-2",
                "procurement_item": "Ламинат",
                "product_fit": "exact",
            })

        # Target = 6 suppliers total. In balanced mode: 6 // 2 = 3 per item.
        accepted_balanced = _accepted_supplier_results(
            reviewed,
            target=6,
            profile=profile,
            multi_item_mode="balanced",
            limit_to_target=True,
        )
        self.assertEqual(len(accepted_balanced), 6)
        item1_count = sum(1 for r in accepted_balanced if r.get("procurement_item_id") == "item-1")
        item2_count = sum(1 for r in accepted_balanced if r.get("procurement_item_id") == "item-2")
        self.assertEqual(item1_count, 3)
        self.assertEqual(item2_count, 3)

    def test_multi_item_per_item_mode_allows_deep_pool(self):
        profile = ProcurementProfile(
            summary="Отделочные материалы",
            items=[
                ProcurementItem(id="item-1", name="Линолеум"),
                ProcurementItem(id="item-2", name="Ламинат"),
            ],
        )
        reviewed = []
        # 10 suppliers for item 1
        for i in range(10):
            reviewed.append({
                "site": f"https://linoleum-{i}.ru",
                "company_name": f"Линолеум Завод {i}",
                "evidence_status": "verified",
                "quality_score": 85,
                "procurement_item_id": "item-1",
                "procurement_item": "Линолеум",
                "product_fit": "exact",
            })
        # 10 suppliers for item 2
        for i in range(10):
            reviewed.append({
                "site": f"https://laminat-{i}.ru",
                "company_name": f"Ламинат Завод {i}",
                "evidence_status": "verified",
                "quality_score": 85,
                "procurement_item_id": "item-2",
                "procurement_item": "Ламинат",
                "product_fit": "exact",
            })

        # In per_item mode: per_item_quota is min(40, target)=10, so all 20 suppliers are accepted!
        accepted_per_item = _accepted_supplier_results(
            reviewed,
            target=10,
            profile=profile,
            multi_item_mode="per_item",
            limit_to_target=True,
        )
        self.assertEqual(len(accepted_per_item), 20)
        item1_count = sum(1 for r in accepted_per_item if r.get("procurement_item_id") == "item-1")
        item2_count = sum(1 for r in accepted_per_item if r.get("procurement_item_id") == "item-2")
        self.assertEqual(item1_count, 10)
        self.assertEqual(item2_count, 10)

    def test_create_job_stores_multi_item_mode(self):
        with TemporaryDirectory() as tmp:
            engine = create_engine(f"sqlite:///{Path(tmp)/'test.db'}")
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()
            try:
                job_default = create_job(
                    session,
                    client_id=None,
                    mode="supplier_search",
                    title="ТЗ По умолчанию",
                    target_suppliers=10,
                    files=[],
                )
                self.assertEqual(job_default.multi_item_mode, "balanced")

                job_per_item = create_job(
                    session,
                    client_id=None,
                    mode="supplier_search",
                    title="ТЗ Попозиционный",
                    target_suppliers=10,
                    files=[],
                    multi_item_mode="per_item",
                )
                self.assertEqual(job_per_item.multi_item_mode, "per_item")
            finally:
                session.close()
