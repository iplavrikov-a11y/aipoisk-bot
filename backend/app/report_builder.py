from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


SUPPLIER_HEADERS = [
    "Наименование компании",
    "Регион",
    "Статус",
    "Уровень совпадения",
    "Продукция",
    "Контактное лицо",
    "Телефон",
    "Email",
    "Сайт",
    "Источник поиска",
    "Search Query",
    "Комментарии",
    "Contact URL",
    "Evidence URL",
]


MATCH_LEVEL_LABELS = {
    "exact": "точное совпадение",
    "adjacent": "смежная категория",
    "profile": "профильный поставщик",
    "reject": "не подтверждено",
}


def write_supplier_xlsx(path: str | Path, rows: list[dict], *, title: str, target: int) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "поиск поставщиков"
    ws.append([f"Отчёт по ТЗ: {title or 'без названия'}"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(SUPPLIER_HEADERS))
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(wrap_text=True)
    ws.append([f"Найдено и проверено: {len(rows)}/{target}. В XLSX включены сайты с открытой страницей-доказательством и контактами."])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(SUPPLIER_HEADERS))
    ws.append(SUPPLIER_HEADERS)
    header_fill = PatternFill("solid", fgColor="E5E7EB")
    for cell in ws[3]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in rows:
        ws.append(
            [
                row.get("company_name", ""),
                row.get("region", ""),
                row.get("status", ""),
                _match_level_label(row.get("match_level", "")),
                row.get("product", ""),
                row.get("contact_person", ""),
                row.get("phone", ""),
                row.get("email", ""),
                row.get("site", ""),
                row.get("source", ""),
                row.get("search_query", ""),
                row.get("comments", ""),
                row.get("contact_url", ""),
                row.get("evidence_url", ""),
            ]
        )
    for column in range(1, len(SUPPLIER_HEADERS) + 1):
        width = 18
        if column in {1, 5, 11, 12, 13, 14}:
            width = 34
        if column in {7, 8, 9, 10}:
            width = 24
        ws.column_dimensions[get_column_letter(column)].width = width
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(out)
    return out


def _match_level_label(value: object) -> str:
    raw = str(value or "").strip()
    return MATCH_LEVEL_LABELS.get(raw, raw)


def write_procurement_docx(path: str | Path, markdown: str, *, title: str) -> Path:
    from docx import Document
    from docx.shared import Pt

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for section in doc.sections:
        section.top_margin = Pt(28)
        section.bottom_margin = Pt(28)
        section.left_margin = Pt(34)
        section.right_margin = Pt(34)
    heading = doc.add_heading(title or "Отчёт анализа закупки", level=1)
    heading.alignment = 1
    lines = str(markdown or "").splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        if not line:
            index += 1
            continue
        if _is_markdown_table_start(lines, index):
            index = _add_markdown_table(doc, lines, index)
            continue
        if re.fullmatch(r"-{3,}", line):
            doc.add_paragraph("")
            index += 1
            continue
        if line.startswith("### "):
            _add_markdown_runs(doc.add_heading(level=3), line[4:])
        elif line.startswith("## "):
            _add_markdown_runs(doc.add_heading(level=2), line[3:])
        elif line.startswith("# "):
            _add_markdown_runs(doc.add_heading(level=1), line[2:])
        elif line.startswith("#### "):
            _add_markdown_runs(doc.add_heading(level=3), line[5:])
        elif line.startswith(("- ", "* ")):
            _add_markdown_runs(doc.add_paragraph(style="List Bullet"), line[2:])
        else:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(3)
            _add_markdown_runs(paragraph, line)
        index += 1
    doc.save(out)
    return out


def _is_markdown_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    current = lines[index].strip()
    separator = lines[index + 1].strip()
    return current.startswith("|") and current.endswith("|") and bool(re.fullmatch(r"\|[\s:\-|]+\|", separator))


def _parse_table_row(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return [
        cell.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        for cell in cells
    ]


def _add_markdown_table(doc, lines: list[str], index: int) -> int:
    rows: list[list[str]] = [_parse_table_row(lines[index])]
    index += 2
    while index < len(lines) and lines[index].strip().startswith("|") and lines[index].strip().endswith("|"):
        rows.append(_parse_table_row(lines[index]))
        index += 1
    width = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    for row_index, row in enumerate(rows):
        for col_index in range(width):
            cell = table.rows[row_index].cells[col_index]
            cell.text = ""
            paragraph = cell.paragraphs[0]
            value = row[col_index] if col_index < len(row) else ""
            _add_markdown_runs(paragraph, value)
            if row_index == 0:
                for run in paragraph.runs:
                    run.bold = True
    doc.add_paragraph("")
    return index


def _add_markdown_runs(paragraph, text: str) -> None:
    parts = re.split(r"(\*\*[^*]+\*\*)", str(text or ""))
    for part in parts:
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**")
        value = part[2:-2] if bold else part
        for line_index, segment in enumerate(value.split("\n")):
            if line_index:
                paragraph.add_run().add_break()
            run = paragraph.add_run(segment)
            run.bold = bold


def write_evidence(path: str | Path, payload: dict) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def zip_paths(zip_path: str | Path, files: list[Path]) -> Path:
    out = Path(zip_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=file_path.name)
    return out
