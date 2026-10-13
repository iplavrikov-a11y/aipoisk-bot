from __future__ import annotations

import logging
from typing import List
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import ItemPriceResult

logger = logging.getLogger(__name__)


def generate_price_monitoring_excel(items: List[ItemPriceResult], output_path: str, max_suppliers: int = 5) -> str:
    """Генерирует Excel-файл со структурой и стилями, в точности соответствующими шаблону заказчика."""
    wb = Workbook()

    # --- ЛИСТ 1: Точно по скриншоту заказчика ---
    ws = wb.active
    ws.title = "Пример отчета"

    # Стили
    font_calibri_bold = Font(name="Calibri", size=11, bold=True)
    font_calibri_regular = Font(name="Calibri", size=11)
    font_red_bold = Font(name="Calibri", size=11, bold=True, color="FF0000")
    font_red_regular = Font(name="Calibri", size=11, color="FF0000")
    font_link = Font(name="Calibri", size=10, color="0000FF", underline="single")

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")

    # Строки 1-4: Заголовок таблицы
    # Колонка A: Номенклатура
    ws.merge_cells("A1:A3")
    cell_a = ws["A1"]
    cell_a.value = "Номенклатура"
    cell_a.font = font_calibri_bold
    cell_a.alignment = align_center

    # Колонка B: Ед. изм.
    ws.merge_cells("B1:B3")
    cell_b = ws["B1"]
    cell_b.value = "Ед. изм."
    cell_b.font = font_calibri_bold
    cell_b.alignment = align_center

    # Поставщики 1..5
    for s_idx in range(1, max_suppliers + 1):
        col_start = 3 + (s_idx - 1) * 2  # C=3, E=5, G=7, I=9, K=11
        col_end = col_start + 1          # D=4, F=6, H=8, J=10, L=12
        col_start_let = get_column_letter(col_start)
        col_end_let = get_column_letter(col_end)

        # Строка 1: Поставщик N (наименование)
        ws.merge_cells(f"{col_start_let}1:{col_end_let}1")
        cell_sup = ws[f"{col_start_let}1"]
        cell_sup.value = f"Поставщик {s_idx} ( наименование )"
        cell_sup.font = font_red_regular
        cell_sup.alignment = align_center

        # Строка 2: ИНН/КПП
        ws.merge_cells(f"{col_start_let}2:{col_end_let}2")
        cell_inn = ws[f"{col_start_let}2"]
        cell_inn.value = "ИНН/КПП"
        cell_inn.font = font_red_regular
        cell_inn.alignment = align_center

        # Строка 3: контакты
        ws.merge_cells(f"{col_start_let}3:{col_end_let}3")
        cell_cont = ws[f"{col_start_let}3"]
        cell_cont.value = "контакты"
        cell_cont.font = font_red_regular
        cell_cont.alignment = align_center

        # Строка 4: Цена руб./ед.
        cell_p = ws[f"{col_start_let}4"]
        cell_p.value = "Цена руб./ед."
        cell_p.font = font_red_regular
        cell_p.alignment = align_center

        # Строка 4: источник (ссылка)
        cell_src = ws[f"{col_end_let}4"]
        cell_src.value = 'источник (ссылка), либо ссылку "зашивать" в цену'
        cell_src.font = font_calibri_regular
        cell_src.alignment = align_center

    # Применяем границы и фон к заголовкам
    max_col = 2 + max_suppliers * 2
    for r in range(1, 5):
        for c in range(1, max_col + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = thin_border
            if r == 4 or c <= 2:
                cell.fill = header_fill

    # Заполняем строки данными
    current_row = 5
    for item in items:
        # A: Номенклатура
        cell_nom = ws.cell(row=current_row, column=1, value=item.raw_name)
        cell_nom.font = font_calibri_regular
        cell_nom.alignment = align_left
        cell_nom.border = thin_border

        # B: Ед. изм.
        cell_unit = ws.cell(row=current_row, column=2, value=item.unit)
        cell_unit.font = font_calibri_regular
        cell_unit.alignment = align_center
        cell_unit.border = thin_border

        # Заполняем поставщиков
        for s_idx in range(1, max_suppliers + 1):
            col_start = 3 + (s_idx - 1) * 2
            col_end = col_start + 1

            cell_price = ws.cell(row=current_row, column=col_start)
            cell_price.border = thin_border
            cell_price.alignment = align_right

            cell_link = ws.cell(row=current_row, column=col_end)
            cell_link.border = thin_border
            cell_link.alignment = align_left

            if s_idx <= len(item.quotes):
                q = item.quotes[s_idx - 1]
                if q.price_rub > 0:
                    cell_price.value = q.price_rub
                    cell_price.number_format = "#,##0.00"
                    cell_price.font = font_calibri_bold

                    # В ячейку источника выводим ссылку и название компании
                    cell_link.value = q.url
                    if q.url.startswith("http"):
                        cell_link.hyperlink = q.url
                        cell_link.font = font_link

                    # Также делаем саму цену кликабельной гиперссылкой!
                    if q.url.startswith("http"):
                        cell_price.hyperlink = q.url

                    # Формируем подсказку с реквизитами поставщика
                    info_parts = [q.company_name]
                    if q.inn:
                        info_parts.append(f"ИНН {q.inn}")
                    if q.contacts:
                        info_parts.append(q.contacts)
                    cell_link.value = f"{' | '.join(info_parts)}: {q.url}"
                else:
                    cell_price.value = "по запросу"
                    cell_price.font = font_calibri_regular
                    cell_link.value = q.url
            else:
                cell_price.value = ""
                cell_link.value = ""

        current_row += 1

    # Настройка ширины колонок
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 10
    for s_idx in range(1, max_suppliers + 1):
        col_start_let = get_column_letter(3 + (s_idx - 1) * 2)
        col_end_let = get_column_letter(4 + (s_idx - 1) * 2)
        ws.column_dimensions[col_start_let].width = 16
        ws.column_dimensions[col_end_let].width = 36

    # --- ЛИСТ 2: Подробный детализированный реестр для закупщика/1С ---
    ws2 = wb.create_sheet(title="Детализированный реестр")
    headers_reg = ["№", "Номенклатура", "Ед. изм.", "Статус", "Мин. цена (руб)"]
    for s_idx in range(1, max_suppliers + 1):
        headers_reg.extend([
            f"Поставщик {s_idx}",
            f"ИНН {s_idx}",
            f"Контакты {s_idx}",
            f"Цена {s_idx} (руб)",
            f"Ссылка {s_idx}",
        ])

    ws2.append(headers_reg)
    for col_idx in range(1, len(headers_reg) + 1):
        cell = ws2.cell(row=1, column=col_idx)
        cell.font = font_calibri_bold
        cell.fill = header_fill
        cell.alignment = align_center
        cell.border = thin_border

    row_num = 2
    for idx, item in enumerate(items, 1):
        row_vals = [
            idx,
            item.raw_name,
            item.unit,
            "Найдено" if item.has_prices else "Не найдено",
            item.best_price if item.has_prices else "-",
        ]
        for s_idx in range(1, max_suppliers + 1):
            if s_idx <= len(item.quotes):
                q = item.quotes[s_idx - 1]
                row_vals.extend([
                    q.company_name,
                    q.inn or "-",
                    q.contacts or "-",
                    q.price_rub if q.price_rub > 0 else "по запросу",
                    q.url,
                ])
            else:
                row_vals.extend(["-", "-", "-", "-", "-"])
        ws2.append(row_vals)
        for col_idx in range(1, len(headers_reg) + 1):
            cell = ws2.cell(row=row_num, column=col_idx)
            cell.font = font_calibri_regular
            cell.border = thin_border
            if col_idx == 4:
                cell.font = Font(name="Calibri", bold=True, color="008000" if item.has_prices else "808080")
        row_num += 1

    wb.save(output_path)
    logger.info("Saved price monitoring excel to %s", output_path)
    return output_path
