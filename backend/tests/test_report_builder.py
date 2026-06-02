from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.report_builder import write_supplier_xlsx


class ReportBuilderTests(unittest.TestCase):
    def test_supplier_xlsx_includes_quality_source_and_contact_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suppliers.xlsx"
            write_supplier_xlsx(
                path,
                [
                    {
                        "company_name": "Поставщик",
                        "match_level": "exact",
                        "source": "yandex",
                        "contact_url": "https://supplier.ru/contacts",
                        "evidence_url": "https://supplier.ru/catalog",
                    }
                ],
                title="ТЗ",
                target=1,
            )

            wb = load_workbook(path, read_only=True)
            ws = wb.active
            headers = [cell.value for cell in ws[3]]
            values = [cell.value for cell in ws[4]]
            wb.close()

        self.assertIn("Уровень совпадения", headers)
        self.assertIn("Источник поиска", headers)
        self.assertIn("Contact URL", headers)
        self.assertIn("точное совпадение", values)
        self.assertIn("yandex", values)
        self.assertIn("https://supplier.ru/contacts", values)


if __name__ == "__main__":
    unittest.main()
