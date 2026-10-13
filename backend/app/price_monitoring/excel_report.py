from __future__ import annotations

import logging
import re
from collections import Counter
from typing import List, Optional
from urllib.parse import urlparse

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import ItemPriceResult, SupplierQuote

logger = logging.getLogger(__name__)


def format_short_url(url: str) -> str:
    """Форматирует компактную кликабельную ссылку без визуального захламления ячейки."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        path = parsed.path.strip("/")
        if not path:
            return domain
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1:
            slug = parts[0]
            if len(slug) > 24:
                slug = slug[:22] + ".."
            return f"{domain}/{slug}"
        else:
            last_part = parts[-1]
            if len(last_part) > 24:
                last_part = last_part[:22] + ".."
            return f"{domain}/.../{last_part}"
    except Exception:
        return url[:35]


def _format_contacts_multiline(contacts: Optional[str]) -> str:
    """
    Форматирует контакты компактно по категориям:
    - Телефоны на 1 строке через запятую: "Тел: +7..., 8..."
    - Email на 1 строке через запятую: "Email: info@..., sales@..."
    - Город / адрес на 1 строке.
    Гарантирует не более 3 строк, исключая обрезание в ячейках Excel.
    """
    if not contacts:
        return "контакты на сайте"

    raw_parts = [p.strip() for p in re.split(r'[,;\n]+', contacts) if p.strip()]
    phones: list[str] = []
    emails: list[str] = []
    others: list[str] = []
    seen: set[str] = set()

    for p in raw_parts:
        clean_p = re.sub(r'\s+', ' ', p).strip()
        key = clean_p.lower()
        if key in seen:
            continue
        seen.add(key)

        if "@" in clean_p and "." in clean_p:
            emails.append(clean_p)
        elif any(c.isdigit() for c in clean_p) and (len(re.sub(r'\D', '', clean_p)) in (10, 11) or "800" in clean_p or "+7" in clean_p or "tel" in clean_p.lower()):
            phones.append(clean_p)
        else:
            others.append(clean_p)

    lines: list[str] = []
    if phones:
        lines.append("Тел: " + ", ".join(phones[:3]))
    if emails:
        lines.append("Email: " + ", ".join(emails[:2]))
    if others:
        clean_others: list[str] = []
        for o in others:
            if not any(o.lower() == co.lower() or o.lower() in co.lower() for co in clean_others):
                clean_others.append(o)
        if clean_others:
            lines.append(", ".join(clean_others[:2]))

    if not lines:
        return contacts[:80]
    return "\n".join(lines[:3])



def _format_contacts_compact(contacts: Optional[str]) -> str:
    """
    Форматирует контакты в одну горизонтальную строку:
    'Тел: +7..., Email: info@..., г. Москва'
    Все телефоны и email разделяются запятыми, предотвращая обрезание в строках.
    """
    if not contacts:
        return "контакты на сайте"

    raw_parts = [p.strip() for p in re.split(r'[,;\n]+', contacts) if p.strip()]
    phones: list[str] = []
    emails: list[str] = []
    cities: list[str] = []
    seen: set[str] = set()

    for p in raw_parts:
        clean_p = re.sub(r'\s+', ' ', p).strip()
        key = clean_p.lower()
        if key in seen:
            continue
        seen.add(key)

        if "@" in clean_p and "." in clean_p:
            emails.append(clean_p)
        elif any(c.isdigit() for c in clean_p) and (len(re.sub(r'\D', '', clean_p)) in (10, 11) or "800" in clean_p or "+7" in clean_p or "tel" in clean_p.lower()):
            phones.append(clean_p)
        else:
            cities.append(clean_p)

    out_items: list[str] = []
    if phones:
        out_items.append("Тел: " + ", ".join(phones[:2]))
    if emails:
        out_items.append("Email: " + ", ".join(emails[:2]))
    if cities:
        clean_cities: list[str] = []
        for c in cities:
            if not any(c.lower() == cc.lower() or c.lower() in cc.lower() for cc in clean_cities):
                clean_cities.append(c)
        if clean_cities:
            out_items.append(", ".join(clean_cities[:2]))

    if not out_items:
        return contacts[:80]
    return ", ".join(out_items)


def _build_cell_comment(q: SupplierQuote, item_unit: str) -> Comment:
    """Формирует всплывающую подсказку (комментарий Excel) с реквизитами поставщика и пересчетом."""
    lines = [
        f"Поставщик: {q.company_name}",
        f"ИНН: {q.inn or 'не указан'}" + (f" / КПП: {q.kpp}" if q.kpp else ""),
        f"Контакты: {q.contacts or 'см. на сайте'}",
    ]
    if q.raw_price_rub > 0 and q.site_unit:
        lines.append(f"Цена на сайте: {q.raw_price_rub:,.2f} ₽ ({q.site_unit})")
    lines.append(f"Цена в отчете: {q.price_rub:,.2f} ₽ за {item_unit}")
    if q.conversion_comment:
        lines.append(f"Пересчет: {q.conversion_comment}")
    if q.comment:
        lines.append(f"Примечание: {q.comment}")
    lines.append(f"Полная ссылка: {q.url}")

    text = "\n".join(lines)
    comm = Comment(text, "TenderLex")
    comm.width = 380
    comm.height = 140
    return comm


def generate_price_monitoring_excel(items: List[ItemPriceResult], output_path: str, max_suppliers: int = 5) -> str:
    """
    Генерирует Excel-файл со структурой и стилями, в точности соответствующими шаблону заказчика.
    Лист 1: 'Пример отчета' (сводная матрица с реквизитами в шапке, компактными ссылками и всплывающими подсказками).
    Лист 2: 'Детализированный реестр' (полный перечень для 1С/закупщика с ИНН, КПП, контактами и формулами пересчета).
    """
    wb = Workbook()

    # --- ЛИСТ 1: 'Пример отчета' по шаблону заказчика ---
    ws = wb.active
    ws.title = "Пример отчета"

    # Стили
    font_calibri_bold = Font(name="Calibri", size=11, bold=True)
    font_calibri_regular = Font(name="Calibri", size=11)
    font_header_bold = Font(name="Calibri", size=10, bold=True)
    font_header_regular = Font(name="Calibri", size=10)
    font_link = Font(name="Calibri", size=10, color="0563C1", underline="single")
    font_price_bold = Font(name="Calibri", size=11, bold=True, color="166534")
    font_price_outlier = Font(name="Calibri", size=11, bold=True, color="B45309")

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    sup_header_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")

    # Колонки A и B
    ws.merge_cells("A1:A4")
    cell_a = ws["A1"]
    cell_a.value = "Номенклатура"
    cell_a.font = font_calibri_bold
    cell_a.alignment = align_center

    ws.merge_cells("B1:B4")
    cell_b = ws["B1"]
    cell_b.value = "Ед. изм."
    cell_b.font = font_calibri_bold
    cell_b.alignment = align_center

    # Определяем основных поставщиков по массиву позиций
    supplier_freq: Counter[str] = Counter()
    supplier_best_meta: dict[str, SupplierQuote] = {}
    for item in items:
        for q in item.quotes:
            if q.company_name and q.price_rub > 0:
                supplier_freq[q.company_name] += 1
                if q.company_name not in supplier_best_meta or (q.inn and not supplier_best_meta[q.company_name].inn):
                    supplier_best_meta[q.company_name] = q

    top_suppliers = [sup_name for sup_name, _ in supplier_freq.most_common(max_suppliers)]

    # Поставщик считается доминирующим ТОЛЬКО если закрывает почти всю закупку (>= 80% позиций)
    dominant_threshold = max(1, int(len(items) * 0.8)) if len(items) > 1 else 1

    # Шапка поставщиков 1..max_suppliers (строки 1-4)
    for s_idx in range(1, max_suppliers + 1):
        col_start = 3 + (s_idx - 1) * 2  # C=3, E=5, G=7, I=9, K=11
        col_end = col_start + 1          # D=4, F=6, H=8, J=10, L=12
        col_start_let = get_column_letter(col_start)
        col_end_let = get_column_letter(col_end)

        # Выбираем метаданные поставщика для шапки столбца
        sup_quote: Optional[SupplierQuote] = None
        if s_idx <= len(top_suppliers):
            sup_quote = supplier_best_meta.get(top_suppliers[s_idx - 1])
        elif items and any(len(it.quotes) >= s_idx for it in items):
            for it in items:
                if len(it.quotes) >= s_idx and it.quotes[s_idx - 1].price_rub > 0:
                    sup_quote = it.quotes[s_idx - 1]
                    break

        is_dominant = False
        if sup_quote and supplier_freq:
            item_coverage = supplier_freq.get(sup_quote.company_name, 0)
            is_dominant = item_coverage >= dominant_threshold

        if sup_quote and is_dominant:
            c_name = sup_quote.company_name.strip()
            if not any(c_name.startswith(p) for p in ("ООО", "АО", "ЗАО", "ПАО", "ИП", "Общество", "Акционерное")):
                c_display = f'ООО "{c_name}"'
            else:
                c_display = c_name

            sup_name_text = f"Поставщик {s_idx} ({c_display})"
            inn_parts = []
            if sup_quote.inn:
                inn_parts.append(f"ИНН {sup_quote.inn}")
            if sup_quote.kpp:
                inn_parts.append(f"КПП {sup_quote.kpp}")
            inn_kpp_text = " / ".join(inn_parts) if inn_parts else "ИНН: уточняется"
            contacts_text = _format_contacts_multiline(sup_quote.contacts)
        else:
            sup_name_text = f"Поставщик {s_idx} ( наименование )"
            inn_kpp_text = "ИНН/КПП"
            contacts_text = "контакты"

        # Строка 1: Поставщик N (наименование)
        ws.merge_cells(f"{col_start_let}1:{col_end_let}1")
        cell_sup = ws[f"{col_start_let}1"]
        cell_sup.value = sup_name_text
        cell_sup.font = font_header_bold
        cell_sup.alignment = align_center

        # Строка 2: ИНН/КПП
        ws.merge_cells(f"{col_start_let}2:{col_end_let}2")
        cell_inn = ws[f"{col_start_let}2"]
        cell_inn.value = inn_kpp_text
        cell_inn.font = font_header_regular
        cell_inn.alignment = align_center

        # Строка 3: контакты
        ws.merge_cells(f"{col_start_let}3:{col_end_let}3")
        cell_cont = ws[f"{col_start_let}3"]
        cell_cont.value = contacts_text
        cell_cont.font = font_header_regular
        cell_cont.alignment = align_center

        # Строка 4: Цена руб./ед.
        cell_p = ws[f"{col_start_let}4"]
        cell_p.value = "Цена руб./ед."
        cell_p.font = font_header_bold
        cell_p.alignment = align_center

        # Строка 4: источник (ссылка)
        cell_src = ws[f"{col_end_let}4"]
        cell_src.value = "источник (ссылка)"
        cell_src.font = font_header_regular
        cell_src.alignment = align_center

    # Сводные колонки: Мин. цена и Средняя цена
    col_min_idx = 3 + max_suppliers * 2
    col_avg_idx = col_min_idx + 1
    col_min_let = get_column_letter(col_min_idx)
    col_avg_let = get_column_letter(col_avg_idx)

    ws.merge_cells(f"{col_min_let}1:{col_min_let}4")
    cell_min_hdr = ws[f"{col_min_let}1"]
    cell_min_hdr.value = "Мин. цена, руб."
    cell_min_hdr.font = font_calibri_bold
    cell_min_hdr.alignment = align_center

    ws.merge_cells(f"{col_avg_let}1:{col_avg_let}4")
    cell_avg_hdr = ws[f"{col_avg_let}1"]
    cell_avg_hdr.value = "Средняя цена, руб."
    cell_avg_hdr.font = font_calibri_bold
    cell_avg_hdr.alignment = align_center

    # Применяем границы и фон к заголовкам
    max_col = col_avg_idx
    for r in range(1, 5):
        for c in range(1, max_col + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = thin_border
            if r == 4 or c <= 2 or c >= col_min_idx:
                cell.fill = header_fill
            else:
                cell.fill = sup_header_fill

    # Список колонок с ценами для формул MIN и AVERAGE
    price_col_letters = [get_column_letter(3 + (s - 1) * 2) for s in range(1, max_suppliers + 1)]

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

        # Заполняем котировки поставщиков
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
                    cell_price.font = font_price_outlier if q.is_outlier else font_price_bold

                    # В ячейку источника выводим реквизиты поставщика, контакты через запятую и ссылку
                    c_name = q.company_name.strip()
                    if not any(c_name.startswith(p) for p in ("ООО", "АО", "ЗАО", "ПАО", "ИП", "Общество", "Акционерное")):
                        clean_c = c_name.strip(" '\"")
                        if clean_c != format_short_url(q.url) and "." not in clean_c:
                            c_display = f'ООО "{clean_c}"'
                        else:
                            c_display = clean_c
                    else:
                        c_display = c_name

                    line1 = c_display + (f" | ИНН {q.inn}" if q.inn else "")
                    line2 = _format_contacts_compact(q.contacts)
                    short_link_display = format_short_url(q.url)
                    line3 = short_link_display

                    cell_link.value = f"{line1}\n{line2}\n{line3}"
                    if q.url.startswith("http"):
                        cell_link.hyperlink = q.url
                        cell_link.font = font_link
                        cell_price.hyperlink = q.url

                    # Формируем информативную всплывающую подсказку в ячейке
                    comment_obj = _build_cell_comment(q, item.unit)
                    cell_link.comment = comment_obj
                    cell_price.comment = comment_obj
                else:
                    cell_price.value = "по запросу"
                    cell_price.font = font_calibri_regular
                    cell_link.value = format_short_url(q.url)
                    if q.url.startswith("http"):
                        cell_link.hyperlink = q.url
                        cell_link.font = font_link
            else:
                cell_price.value = ""
                cell_link.value = ""

        # Формулы Мин. цена и Средняя цена (исключаем аномальные выбросы из базового расчета)
        clean_col_letters = []
        all_numeric_col_letters = []
        for s_idx in range(1, max_suppliers + 1):
            if s_idx <= len(item.quotes):
                q = item.quotes[s_idx - 1]
                if q.price_rub > 0:
                    c_let = get_column_letter(3 + (s_idx - 1) * 2)
                    all_numeric_col_letters.append(c_let)
                    if not q.is_outlier:
                        clean_col_letters.append(c_let)

        target_letters = clean_col_letters if clean_col_letters else all_numeric_col_letters
        if not target_letters:
            target_letters = price_col_letters

        args_str = ",".join(f"{col_let}{current_row}" for col_let in target_letters)
        cell_min = ws.cell(row=current_row, column=col_min_idx)
        cell_min.border = thin_border
        cell_min.alignment = align_right
        cell_min.number_format = "#,##0.00"
        cell_min.font = font_price_bold
        cell_min.value = f"=MIN({args_str})"

        cell_avg = ws.cell(row=current_row, column=col_avg_idx)
        cell_avg.border = thin_border
        cell_avg.alignment = align_right
        cell_avg.number_format = "#,##0.00"
        cell_avg.font = font_calibri_bold
        cell_avg.value = f"=AVERAGE({args_str})"

        current_row += 1

    # Настройка высоты строк шапки и данных Листа 1 (предотвращает схлопывание контактов и названий)
    ws.row_dimensions[1].height = 28  # Поставщик N
    ws.row_dimensions[2].height = 22  # ИНН / КПП
    ws.row_dimensions[3].height = 36  # Контакты
    ws.row_dimensions[4].height = 24  # Заголовки колонок "Цена руб./ед.", "источник (ссылка)"

    for r in range(5, current_row):
        ws.row_dimensions[r].height = 54  # Строки номенклатуры (3 строки с реквизитами и ссылкой)

    # Настройка ширины колонок Листа 1
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 12
    for s_idx in range(1, max_suppliers + 1):
        col_start_let = get_column_letter(3 + (s_idx - 1) * 2)
        col_end_let = get_column_letter(4 + (s_idx - 1) * 2)
        ws.column_dimensions[col_start_let].width = 16
        ws.column_dimensions[col_end_let].width = 42

    ws.column_dimensions[col_min_let].width = 18
    ws.column_dimensions[col_avg_let].width = 18

    # --- ЛИСТ 2: Подробный детализированный реестр для закупщика/1С ---
    ws2 = wb.create_sheet(title="Детализированный реестр")
    headers_reg = ["№", "Номенклатура", "Ед. изм. заявки", "Статус", "Мин. цена (руб)"]
    for s_idx in range(1, max_suppliers + 1):
        headers_reg.extend([
            f"Поставщик {s_idx}",
            f"ИНН {s_idx}",
            f"КПП {s_idx}",
            f"Контакты {s_idx}",
            f"Цена {s_idx} (руб)",
            f"Исходная цена на сайте {s_idx}",
            f"Ед. на сайте {s_idx}",
            f"Пересчет / Примечание {s_idx}",
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
                    q.company_name or "-",
                    q.inn or "-",
                    q.kpp or "-",
                    q.contacts or "-",
                    q.price_rub if q.price_rub > 0 else "по запросу",
                    q.raw_price_rub if q.raw_price_rub > 0 else "-",
                    q.site_unit or "-",
                    q.conversion_comment or q.comment or "-",
                    q.url,
                ])
            else:
                row_vals.extend(["-", "-", "-", "-", "-", "-", "-", "-", "-"])
        ws2.append(row_vals)
        for col_idx in range(1, len(headers_reg) + 1):
            cell = ws2.cell(row=row_num, column=col_idx)
            cell.font = font_calibri_regular
            cell.border = thin_border
            if col_idx == 4:
                cell.font = Font(name="Calibri", bold=True, color="008000" if item.has_prices else "808080")
            elif col_idx > 5 and (col_idx - 5) % 9 == 0:  # Ссылка
                val = str(cell.value or "")
                if val.startswith("http"):
                    cell.hyperlink = val
                    cell.font = font_link
        row_num += 1

    # Высота и ширина колонок листа 2
    ws2.row_dimensions[1].height = 26
    for r in range(2, row_num):
        ws2.row_dimensions[r].height = 24
    ws2.column_dimensions["A"].width = 6
    ws2.column_dimensions["B"].width = 46
    ws2.column_dimensions["C"].width = 14
    ws2.column_dimensions["D"].width = 12
    ws2.column_dimensions["E"].width = 18

    wb.save(output_path)
    logger.info("Saved price monitoring excel to %s", output_path)
    return output_path
