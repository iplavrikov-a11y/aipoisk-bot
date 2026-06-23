from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from openpyxl import load_workbook

from app.quote_request import build_quote_request_markdown
from app.report_builder import (
    PROCUREMENT_REPORT_DISCLAIMER,
    QUOTE_REQUEST_INTRO,
    write_procurement_docx,
    write_quote_request_docx,
    write_supplier_xlsx,
)


class ReportBuilderTests(unittest.TestCase):
    def test_procurement_docx_contains_soft_ai_disclaimer(self) -> None:
        from docx import Document

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analysis.docx"
            write_procurement_docx(
                path,
                "#### Общая информация\n- Заказчик: Тестовый заказчик",
                title="Анализ документации",
            )

            doc = Document(path)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

        self.assertIn(PROCUREMENT_REPORT_DISCLAIMER, text)
        self.assertIn("Критичные юридические, финансовые и технические условия", text)

    def test_procurement_docx_removes_okpd_and_formats_tz_columns(self) -> None:
        from docx import Document

        markdown = """#### Товары и требования (Техническое задание)
| № | Наименование | Характеристики | Ед.изм. | Кол-во |
|---|---|---|---|---|
| 1 | Канат стальной (ОКПД2: 25.93.11.120) | Назначение: применяется в качестве устройств растяжек и вант для кранов; требования к конструкции: ГОСТ 3062-80, конструкция 1x7, диаметр 6,8 мм. | м | 5000 |
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analysis.docx"
            write_procurement_docx(path, markdown, title="Анализ закупки")

            doc = Document(path)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
            table_text = "\n".join(cell.text for row in doc.tables[0].rows for cell in row.cells)
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml")

        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        grid_cols = [
            int(col.attrib[f"{{{ns['w']}}}w"])
            for col in root.findall(".//w:tbl[1]/w:tblGrid/w:gridCol", ns)
        ]

        self.assertNotRegex(f"{text}\n{table_text}", r"(?i)ОКПД|OKPD")
        self.assertNotIn("25.93.11.120", table_text)
        self.assertEqual(len(grid_cols), 5)
        self.assertLess(grid_cols[0], grid_cols[1])
        self.assertGreater(grid_cols[2], grid_cols[1])
        self.assertGreater(grid_cols[2], grid_cols[3] * 5)
        self.assertGreater(grid_cols[2], grid_cols[4] * 5)

    def test_quote_request_docx_uses_request_text_without_analysis_disclaimer(self) -> None:
        from docx import Document

        markdown = f"""ЗАПРОС КП

{QUOTE_REQUEST_INTRO}

| № | Наименование | Характеристики | Ед.изм. | Кол-во |
|---|---|---|---|---|
| 1 | Канат стальной КТРУ 25.93.11 | ГОСТ 3062-80, диаметр 6,8 мм | м | 5000 |

### Условия поставки

- **Срок поставки:** 30 календарных дней
- **Город поставки:** Казань
- **Документы качества:** паспорт качества
- **Упаковка/тара:** бухты
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote.docx"
            write_quote_request_docx(path, markdown, title="Запрос КП")

            doc = Document(path)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
            table_text = "\n".join(cell.text for row in doc.tables[0].rows for cell in row.cells)

        self.assertIn("Запрос КП", text)
        self.assertIn(QUOTE_REQUEST_INTRO, text)
        self.assertIn("Канат стальной", table_text)
        self.assertIn("Срок поставки:", text)
        self.assertNotIn(PROCUREMENT_REPORT_DISCLAIMER, text)
        self.assertNotRegex(f"{text}\n{table_text}", r"(?i)ОКПД|OKPD|КТРУ|KTRU")

    def test_quote_request_markdown_omits_note_column(self) -> None:
        source = """### Товары и требования
| № | Наименование | Характеристики | Ед.изм. | Кол-во | Примечание |
|---|---|---|---|---|---|
| 1 | Канат стальной | ГОСТ 3062-80, диаметр 6,8 мм | м | 5000 | Просим указать в КП |

- **Срок поставки:** 30 календарных дней
- **Город поставки:** Казань
- **Условия оплаты:** по договору
- **Документы качества:** паспорт качества
- **Упаковка/тара:** бухты
"""

        markdown = build_quote_request_markdown(source, subject="Канат стальной")

        self.assertIn("| № | Наименование | Характеристики | Ед.изм. | Кол-во |", markdown)
        self.assertNotIn("Примечание", markdown)
        self.assertNotIn("Просим указать в КП", markdown)

    def test_supplier_xlsx_is_client_facing_without_technical_search_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suppliers.xlsx"
            write_supplier_xlsx(
                path,
                [
                    {
                        "company_name": "Поставщик",
                        "match_level": "exact",
                        "quality_score": 91,
                        "quality_tier": "high",
                        "procurement_item": "Сварочный полуавтомат",
                        "ai_confidence": 92,
                        "site_type": "manufacturer",
                        "product_fit": "exact",
                        "product": "Сварочный полуавтомат MIG/MAG",
                        "contact_person": "Отдел продаж",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.ru",
                        "site": "https://supplier.ru",
                        "evidence_snippet": "В каталоге указан сварочный полуавтомат.",
                        "contact_evidence_snippet": "Контакты: +7 999 111 22 33",
                        "source": "yandex",
                        "contact_url": "https://supplier.ru/contacts",
                        "evidence_url": "https://supplier.ru/catalog",
                    }
                ],
                title="ТЗ",
                subject="Сварочный полуавтомат",
                target=1,
            )

            wb = load_workbook(path)
            ws = wb.active
            sheet_title = ws.title
            report_title = ws["A1"].value
            headers = [cell.value for cell in ws[3]]
            values = [cell.value for cell in ws[4]]
            site_hyperlink = ws["B4"].hyperlink.target if ws["B4"].hyperlink else ""
            wb.close()

        self.assertEqual(sheet_title, "Поставщики")
        self.assertEqual(report_title, "Отчёт по ТЗ: Сварочный полуавтомат")
        self.assertEqual(
            headers,
            [
                "Компания",
                "Сайт",
                "Телефоны",
                "Email",
                "Комментарий",
            ],
        )
        self.assertNotIn("Search Query", headers)
        self.assertNotIn("Evidence snippet", headers)
        self.assertNotIn("AI уверенность", headers)
        self.assertNotIn("Contact URL", headers)
        self.assertIn("Поставщик", values)
        self.assertIn("https://supplier.ru", values)
        self.assertIn("+7 999 111 22 33", values)
        self.assertIn("sales@supplier.ru", values)
        self.assertEqual(site_hyperlink, "https://supplier.ru")

    def test_supplier_xlsx_marks_non_exact_matches_as_confirmation_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suppliers.xlsx"
            write_supplier_xlsx(
                path,
                [
                    {
                        "company_name": "Профильный поставщик",
                        "product_fit": "profile",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.ru",
                        "site": "https://supplier.ru",
                        "comments": "Компания полностью соответствует ТЗ по профилю закупки.",
                    }
                ],
                title="ТЗ",
                target=1,
            )

            wb = load_workbook(path)
            ws = wb.active
            comment = ws["E4"].value
            wb.close()

        self.assertIn("Профильный поставщик.", comment)
        self.assertIn("Уточните", comment)
        self.assertNotIn("полностью соответствует", comment.lower())

    def test_supplier_xlsx_uses_short_exact_comment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suppliers.xlsx"
            write_supplier_xlsx(
                path,
                [
                    {
                        "company_name": "Поставщик",
                        "product_fit": "exact",
                        "product": "Сварочный полуавтомат MIG/MAG 500А с блоком охлаждения и комплектом поставки",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.ru",
                        "site": "https://supplier.ru",
                        "comments": "Очень длинное описание, которое не должно попадать в клиентский отчет целиком.",
                    }
                ],
                title="ТЗ",
                subject="Сварочный полуавтомат",
                target=1,
            )

            wb = load_workbook(path)
            ws = wb.active
            comment = ws["E4"].value
            wb.close()

        self.assertIn("Точный товар:", comment)
        self.assertIn("Контакты найдены на сайте", comment)
        self.assertLessEqual(len(comment), 260)

    def test_supplier_xlsx_hides_internal_target_when_overfilled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suppliers.xlsx"
            write_supplier_xlsx(
                path,
                [
                    {
                        "company_name": f"Поставщик {index}",
                        "product_fit": "category",
                        "product": "Стальные канаты",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.ru",
                        "site": f"https://supplier-{index}.ru",
                    }
                    for index in range(4)
                ],
                title="ТЗ",
                target=2,
            )

            wb = load_workbook(path)
            ws = wb.active
            summary = ws["A2"].value
            wb.close()

        self.assertIn("Найдено и проверено: 4", summary)
        self.assertNotIn("Минимум по настройкам", summary)
        self.assertNotIn("4/2", summary)

    def test_supplier_xlsx_hides_internal_target_when_underfilled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suppliers.xlsx"
            write_supplier_xlsx(
                path,
                [
                    {
                        "company_name": "Поставщик",
                        "product_fit": "category",
                        "product": "Промышленное оборудование",
                        "phone": "+7 999 111 22 33",
                        "email": "sales@supplier.ru",
                        "site": "https://supplier.ru",
                    }
                ],
                title="ТЗ",
                target=15,
            )

            wb = load_workbook(path)
            ws = wb.active
            summary = ws["A2"].value
            wb.close()

        self.assertIn("Найдено и проверено: 1", summary)
        self.assertNotIn("1/15", summary)
        self.assertNotIn("миним", summary.lower())


if __name__ == "__main__":
    unittest.main()
