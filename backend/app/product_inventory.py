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
        low = header.strip().lower()
        if any(w in low for w in ("№", "п/п", "номер")) or (column == 0 and low in {"", "№", "п/п"}):
            number = column
        elif any(w in low for w in ("характеристик", "показател", "параметр")):
            # Characteristic and parameter columns are never product names or product units
            continue
        elif any(w in low for w in ("наименован", "номенклатур", "название товара", "предмет")):
            if any(w in low for w in ("товар", "продукц", "объект", "работ", "услуг", "номенклатур")) or name is None:
                name = column
        elif any(w in low for w in ("кол-во", "количество", "объем")):
            quantity = column
        elif any(w in low for w in ("единиц", "ед.", "ед")) and unit is None:
            unit = column
    return name, unit, quantity, number


def _blocks(text: str) -> list[list[tuple[int, list[str]]]]:
    blocks, current = [], []
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if (stripped.startswith("|") and stripped.endswith("|")) or (" | " in stripped):
            if stripped.startswith("|") and stripped.endswith("|"):
                raw_cells = stripped[1:-1].split("|")
            else:
                raw_cells = stripped.split("|")
            current.append((line_no, [cell.strip() for cell in raw_cells]))
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
        hdr_idx = None
        for index, (_, cells) in enumerate(table):
            cols = _header_columns(cells)
            if cols[0] is not None and (cols[1] is not None or cols[2] is not None):
                hdr_idx = index
                break

        first = next((index for index, (_, cells) in enumerate(table) if cells and _number(cells[0]) is not None), len(table))

        if hdr_idx is not None:
            name_col, unit_col, quantity_col, number_col = _header_columns(table[hdr_idx][1])
            headers = table[hdr_idx][1]
            start_row = hdr_idx + 1
        elif first < len(table):
            width = max(len(cells) for _, cells in table[:first]) if first else 0
            headers = [" ".join(cells[column] for _, cells in table[:first] if column < len(cells)) for column in range(width)]
            name_col, unit_col, quantity_col, number_col = _header_columns(headers)
            start_row = first
        else:
            continue

        if name_col is None:
            continue
        authoritative = unit_col is not None or quantity_col is not None
        has_inline_chars = any(w in h.lower() for w in ("характеристик", "показател", "параметр") for h in headers[2:]) and (unit_col is not None or quantity_col is not None)
        if has_inline_chars:
            authoritative = True
        characteristic = any("показател" in header.lower() or "характеристик" in header.lower() for header in headers[2:])
        if not authoritative and not characteristic:
            continue
        current: dict | None = None

        def flush() -> None:
            nonlocal current
            if current and current["name"]:
                (inventory if authoritative else details).append(current)
            current = None

        for line_no, cells in table[start_row:]:
            if len(cells) < 2 or all(_number(cell) is not None for cell in cells):
                continue  # Column-number legend, not a product.
            if _number(cells[0]) is None and (_header_columns(cells)[0] is not None or cells[0].lower() in {"п/п", "№", "№ п/п"}):
                continue
            num_val = cells[number_col] if number_col is not None and number_col < len(cells) else ""
            number = _number(num_val) if number_col is not None else None
            get = lambda column: cells[column].strip() if column is not None and column < len(cells) else ""
            name_val = get(name_col)

            is_new = False
            if current is None:
                is_new = True
            elif number is not None:
                if current.get("position_no") != number:
                    is_new = True
            elif name_val and number_col is None:
                is_new = True

            if is_new:
                flush()
                pos_no = number if number is not None else len(inventory) + 1
                current = {"position_no": pos_no, "name": "", "unit": "", "quantity": "", "requirements": [],
                           "source_file": source_file, "source_row": line_no, "source_excerpt": ""}
            if current is None:
                continue
            name_part = get(name_col)
            if name_part and (not current["name"] or not has_inline_chars):
                current["name"] = (current["name"] + " " + name_part).strip()
            current["source_excerpt"] += ("\n" if current["source_excerpt"] else "") + " | ".join(cells)
            if authoritative:
                for key, column in (("unit", unit_col), ("quantity", quantity_col)):
                    if get(column) and not current[key]:
                        current[key] = get(column)
            # Check for inline characteristics in the same authoritative table
            char_col = next((c for c, h in enumerate(headers) if any(w in h.lower() for w in ("характеристик", "показател", "параметр")) and any(w in h.lower() for w in ("наименован", "название"))), None)
            val_col = next((c for c, h in enumerate(headers) if any(w in h.lower() for w in ("характеристик", "показател", "параметр")) and any(w in h.lower() for w in ("значен", "требован"))), None)
            unit_val_col = next((c for c, h in enumerate(headers) if any(w in h.lower() for w in ("характеристик", "показател", "параметр")) and any(w in h.lower() for w in ("единиц", "ед."))), None)
            if char_col is not None and val_col is not None:
                p_name = get(char_col)
                p_val = get(val_col)
                p_u = get(unit_val_col) if unit_val_col is not None else ""
                if p_name and p_val:
                    req_str = f"{p_val} {p_u}".strip() if p_u else p_val
                    current["requirements"].append({"param_name": p_name, "tz_requirement": req_str})
            elif not authoritative:
                if len(cells) == 4:
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
