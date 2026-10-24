"""Source-preserving product rows shared by selection workflows.

This module extracts document structure, never market offers or supplier categories.
None means no authoritative product table was recognized; callers can request an
explicit document analysis instead of treating every line of legal text as goods.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any
from zipfile import BadZipFile


def _identity(value: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]", "", value.lower().replace("ё", "е"))


def _number(value: str) -> int | None:
    match = re.fullmatch(r"\s*(\d+)\s*[.)]?\s*", value)
    return int(match[1]) if match else None


def _header_columns(headers: list[str]) -> tuple[int | None, int | None, int | None, int | None]:
    name = unit = quantity = number = None
    for column, header in enumerate(headers):
        low = header.lower()
        if "наименован" in low or "номенклатур" in low or "название товара" in low:
            name = column
        elif "единиц" in low or low.strip().startswith("ед.") or low.strip() == "ед":
            unit = column
        elif "кол" in low or "количество" in low:
            quantity = column
        elif "№" in low or low.strip() in {"номер", "п/п"}:
            number = column
    return name, unit, quantity, number


def _blocks(text: str) -> list[list[tuple[int, list[str]]]]:
    blocks, current = [], []
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append((line_no, [cell.strip() for cell in stripped[1:-1].split("|")]))
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _table_rows(text: str, source_file: str) -> list[dict] | None:
    tables = _blocks(text)
    inventory: list[dict] = []
    details: list[dict] = []
    for table in tables:
        first = next((index for index, (_, cells) in enumerate(table) if cells and _number(cells[0]) is not None), len(table))
        if first == len(table):
            continue
        width = max(len(cells) for _, cells in table[:first]) if first else 0
        headers = [" ".join(cells[column] for _, cells in table[:first] if column < len(cells)) for column in range(width)]
        name_col, unit_col, quantity_col, number_col = _header_columns(headers)
        if name_col is None:
            continue
        authoritative = unit_col is not None and quantity_col is not None
        characteristic = any("показател" in header.lower() or "характеристик" in header.lower() for header in headers[2:])
        if not authoritative and not characteristic:
            continue
        current: dict | None = None

        def flush() -> None:
            nonlocal current
            if current and current["name"]:
                (inventory if authoritative else details).append(current)
            current = None

        for line_no, cells in table[first:]:
            if len(cells) < 2 or all(_number(cell) is not None for cell in cells):
                continue  # Column-number legend, not a product.
            if _number(cells[0]) is None and (_header_columns(cells)[0] is not None or cells[0].lower() in {"п/п", "№", "№ п/п"}):
                continue
            number = _number(cells[number_col if number_col is not None else 0])
            if number is not None:
                flush()
                current = {"position_no": number, "name": "", "unit": "", "quantity": "", "requirements": [],
                           "source_file": source_file, "source_row": line_no, "source_excerpt": ""}
            if current is None:
                continue
            get = lambda column: cells[column] if column is not None and column < len(cells) else ""
            name_part = get(name_col)
            if name_part:
                current["name"] = (current["name"] + " " + name_part).strip()
            current["source_excerpt"] += ("\n" if current["source_excerpt"] else "") + " | ".join(cells)
            if authoritative:
                for key, column in (("unit", unit_col), ("quantity", quantity_col)):
                    if get(column):
                        current[key] = (current[key] + " " + get(column)).strip()
            elif len(cells) == 4:
                description = cells[2]
                if description:
                    if current["requirements"] and current["requirements"][-1]["param_name"] == "Описание товара":
                        current["requirements"][-1]["tz_requirement"] += " " + description
                    else:
                        current["requirements"].append({"param_name": "Описание товара", "tz_requirement": description})
            elif len(cells) >= 5:
                param, value = cells[2], cells[3]
                if param:
                    current["requirements"].append({"param_name": param, "tz_requirement": value})
                elif value and current["requirements"]:
                    current["requirements"][-1]["tz_requirement"] += " " + value
        flush()
    if not inventory:
        return None
    # Detail-table numbering can differ. Only an unambiguous name/SKU identity joins it.
    for detail in details:
        key = _identity(detail["name"])
        matches = [item for item in inventory if _identity(item["name"]) == key]
        if not matches:
            detail_tokens = Counter(re.findall(r"[a-zа-яё0-9]+", detail["name"].lower()))
            matches = [item for item in inventory if len(_identity(item["name"])) >= 6 and _identity(item["name"]) in key
                       and not (Counter(re.findall(r"[a-zа-яё0-9]+", item["name"].lower())) - detail_tokens)]
        if len(matches) == 1:
            matches[0]["requirements"].extend(detail["requirements"])
            matches[0]["requirements_source_row"] = detail["source_row"]
    return inventory


def _xlsx_rows(path: Path) -> list[dict] | None:
    import openpyxl
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    try:
        for sheet in workbook:
            headers = None
            for line_no, cells in enumerate(sheet.iter_rows(values_only=True), 1):
                values = [str(value).strip() if value is not None else "" for value in cells]
                if headers is None:
                    columns = _header_columns(values)
                    if columns[0] is not None:
                        headers = values
                    continue
                name_col, unit_col, quantity_col, number_col = columns
                get = lambda column: values[column] if column is not None and column < len(values) else ""
                if not get(name_col) or _header_columns(values)[0] is not None:
                    continue
                rows.append({"position_no": _number(get(number_col)) or len(rows) + 1, "name": get(name_col),
                             "unit": get(unit_col), "quantity": get(quantity_col), "source_file": path.name,
                             "source_sheet": sheet.title, "source_row": line_no, "source_excerpt": " | ".join(values),
                             "requirements": [{"param_name": headers[column], "tz_requirement": value}
                                              for column, value in enumerate(values)
                                              if value and column not in {name_col, unit_col, quantity_col, number_col}
                                              and column < len(headers) and headers[column]]})
    finally:
        workbook.close()
    return rows or None


def extract_structured_product_inventory(paths: list[Any], context: str = "") -> list[dict] | None:
    """Return authoritative source rows, preserving duplicate SKUs and physical units."""
    if not paths:
        return _table_rows(context, "")
    from .document_parser import extract_text
    inventory = []
    for file in paths:
        path = Path(file)
        try:
            rows = _xlsx_rows(path) if path.suffix.lower() == ".xlsx" else _table_rows(extract_text(path)[0], path.name)
        except (OSError, ValueError, BadZipFile):
            return None
        if rows is None:
            return None  # Never present a partial multi-file inventory as complete.
        inventory.extend(rows)
    return inventory
