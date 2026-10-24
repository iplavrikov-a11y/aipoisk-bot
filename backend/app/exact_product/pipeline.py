"""
Главный оркестратор подбора точного товара и аналогов (TenderLex Engine v2).
100% архитектурный паритет с EmailAgent (Rule 14).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..models import SystemSettings
from .deep import (
    auto_fill_ai_recommendations,
    auto_rotate_clean_analogs,
    detect_exact_products_deep,
    drop_nonconforming_analogs,
    sanitize_shops_from_positions,
)
from .models import (
    MAX_EXACT_POSITIONS_PER_JOB,
    AlternativeProduct,
    ExactProductPosition,
    ExactProductReport,
    GispRegistryMatch,
    SpecParameterMatch,
)

logger = logging.getLogger(__name__)


async def prepare_exact_product_positions(
    settings: SystemSettings,
    context: str,
    input_files: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """Extract the complete selection inventory, without market search or result reuse."""
    from pathlib import Path
    import openpyxl
    rows: List[Dict[str, Any]] = []
    for file in input_files or []:
        path = Path(file)
        if path.suffix.lower() != ".xlsx":
            continue
        workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
        try:
            for sheet in workbook:
                headers = None
                name_column = None
                for source_row, cells in enumerate(sheet.iter_rows(values_only=True), 1):
                    values = [str(value or "").strip() for value in cells]
                    if headers is None:
                        for column, value in enumerate(values):
                            if any(word in value.lower() for word in ("наименован", "номенклатур", "название товара")):
                                headers, name_column = values, column
                                break
                        continue
                    name = values[name_column] if name_column < len(values) else ""
                    if not name or any(word in name.lower() for word in ("наименование", "номенклатура")):
                        continue
                    row = {"position_no": len(rows) + 1, "name": name, "requirements": [],
                           "source_file": path.name, "source_sheet": sheet.title,
                           "source_row": source_row, "source_excerpt": " | ".join(values)}
                    for column, value in enumerate(values):
                        if not value or column == name_column:
                            continue
                        header = headers[column] if column < len(headers) else ""
                        low = header.lower()
                        if low in {"№", "п/п", "№ п/п", "номер"} and value.isdigit():
                            row["position_no"] = int(value)
                        elif any(word in low for word in ("колич", "кол-во")):
                            row["quantity"] = value
                        elif any(word in low for word in ("ед.", "единиц")):
                            row["unit"] = value
                        elif header and low not in {"№", "п/п", "№ п/п", "номер"}:
                            row["requirements"].append({"param_name": header, "tz_requirement": value})
                    rows.append(row)
        finally:
            workbook.close()
    if rows and not any(Path(file).suffix.lower() != ".xlsx" for file in input_files or []):
        return rows
    from .matcher import parse_tz_structure
    # Parse non-spreadsheet documents separately so their rows do not replace,
    # or duplicate a text rendering of, the workbook inventory already extracted.
    text_sources = []
    for file in input_files or []:
        path = Path(file)
        if path.suffix.lower() == ".xlsx":
            continue
        from ..document_parser import extract_text
        text, _status = extract_text(path)
        if text.strip():
            text_sources.append((path.name, text))
    if not input_files:
        text_sources.append(("", context))
    elif not rows and not text_sources:
        text_sources.append(("", context))
    for source_file, source_text in text_sources:
        chunks, current = [], ""
        for line in source_text.splitlines(keepends=True):
            if len(line) > 120000:
                raise ValueError("Слишком длинная строка ТЗ: разделите документ на читаемые строки")
            if current and len(current) + len(line) > 100000:
                chunks.append(current)
                current = ""
            current += line
        if current:
            chunks.append(current)
        for chunk in chunks:
            structure = await parse_tz_structure(chunk, preserve_empty_positions=True)
            for position in (structure or {}).get("positions") or []:
                row = dict(position)
                row.setdefault("position_no", len(rows) + 1)
                row["source_file"] = source_file
                rows.append(row)
    return rows



async def _analyze_exact_product(
    settings: SystemSettings,
    context: str,
    procurement_title: str = "",
    progress_callback: Any = None,
    selected_positions: Optional[List[Dict[str, Any]]] = None,
) -> ExactProductReport:
    """
    Главная входная точка подбора точного товара и аналогов (TenderLex-паритет с EmailAgent).
    100% совместима с воркером jobs.py и API TenderLex.
    """
    async def _notify(pct: int, msg: str):
        if progress_callback:
            try:
                res = progress_callback(pct, msg)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    from ..document_parser import is_substantive_tz_text
    is_substantive, validation_err = is_substantive_tz_text(context)
    if not is_substantive:
        raise ValueError(validation_err)

    if selected_positions is not None:
        if not selected_positions:
            raise ValueError("Выберите хотя бы одну позицию для подбора")
        if len(selected_positions) > MAX_EXACT_POSITIONS_PER_JOB:
            raise ValueError(f"За один запуск можно выбрать не более {MAX_EXACT_POSITIONS_PER_JOB} позиций")
        from .matcher import detect_exact_products_characteristic_first
        positions_raw = []
        for index, row in enumerate(selected_positions, 1):
            outcome = None
            error = ""
            requirements = row.get("requirements") or []
            row_name = str(row.get("name") or row.get("name_in_tz") or "").strip()
            matcher_row = dict(row)
            selected_context = "Позиция исходной спецификации: " + row_name
            for requirement in requirements:
                if isinstance(requirement, dict):
                    selected_context += "\n" + str(requirement.get("param_name") or requirement.get("name") or "Характеристика") + ": " + str(requirement.get("tz_requirement") or requirement.get("value") or "")
            if row.get("source_excerpt"):
                selected_context += "\nИсходная строка: " + str(row["source_excerpt"])
            if row.get("unit"):
                selected_context += "\nЕдиница измерения: " + str(row["unit"])
            if row.get("quantity"):
                selected_context += "\nКоличество: " + str(row["quantity"])
            if not requirements and row_name:
                # The customer's literal designation is a search target, not inferred specs.
                matcher_row["name"] = row_name
                matcher_row["requirements"] = [{"param_name": "Наименование из спецификации", "tz_requirement": row_name}]
            if requirements or row_name:
                try:
                    result = await detect_exact_products_characteristic_first(
                        selected_context, procurement_title, _notify,
                        full_context=selected_context, prepared_positions=[matcher_row],
                        evidence_data={},
                    )
                    if result and result[0]:
                        from .validation import validate_exact_products
                        candidates = validate_exact_products(result[0], result[1], has_doc_text=True)
                        candidates = drop_nonconforming_analogs(auto_rotate_clean_analogs(candidates))
                        outcome = dict(candidates[0]) if candidates else None
                    if outcome:
                        outcome["verified_documents"] = result[1]
                        specs = outcome.get("specs_breakdown") or []
                        if not requirements or not specs or any(spec.get("status") != "match" for spec in specs):
                            outcome["status"] = "needs_clarification"
                        if not requirements:
                            outcome["reasoning"] = "Кандидат найден по наименованию из исходной строки. Для подтверждения взаимозаменяемости необходимо уточнить технические характеристики."
                except Exception as exc:
                    logger.exception("Selected product position failed")
                    error = "Не удалось завершить проверку позиции; требуется повторный поиск"
            outcome = outcome or {
                "name_in_tz": row.get("name") or row.get("name_in_tz") or f"Позиция {index}",
                "identified_brand": "", "identified_model": "", "manufacturer": "",
                "confidence": 0, "specs_breakdown": [],
                "status": "needs_clarification" if not requirements else "not_found",
                "reasoning": "Недостаточно характеристик для подбора" if not requirements else "Подходящая модель в этом поиске не найдена",
            }
            outcome["position_no"] = row.get("position_no") or index
            outcome["position_id"] = str(row.get("position_id") or row.get("id") or "")
            if error:
                outcome["status"] = "error"
                outcome["error"] = error
            positions_raw.append(outcome)
    else:
        positions_raw = await detect_exact_products_deep(
            report_text=context, procurement_title=procurement_title,
            progress_callback=_notify,
        ) or []
        if not positions_raw:
            positions_raw = [{
                "position_no": 1, "name_in_tz": procurement_title or "Позиции технического задания",
                "identified_brand": "", "identified_model": "", "manufacturer": "",
                "confidence": 0, "status": "not_found",
                "reasoning": "Подходящая модель в этом поиске не найдена; уточните характеристики",
                "specs_breakdown": [],
            }]

    # Преобразование в типизированные структуры данных TenderLex
    typed_positions: List[ExactProductPosition] = []
    web_sources_collected: List[str] = []
    verified_docs_collected: List[Dict[str, Any]] = []

    for idx, p in enumerate(positions_raw[:MAX_EXACT_POSITIONS_PER_JOB], 1):
        specs_list: List[SpecParameterMatch] = []
        for s in (p.get("specs_breakdown") or []):
            if isinstance(s, dict):
                specs_list.append(SpecParameterMatch(
                    param_name=s.get("param_name") or "Параметр",
                    tz_requirement=s.get("tz_requirement") or "",
                    product_fact=s.get("product_fact") or "Нет подтвержденных данных",
                    status=s.get("status") or "clarify",
                    comment=s.get("comment") or "",
                    source_url=s.get("source_url") or "",
                ))

        alts_list: List[AlternativeProduct] = []
        for a in (p.get("alternative_brands") or []):
            if isinstance(a, dict):
                alt_specs = [
                    SpecParameterMatch(
                        param_name=aspec.get("param_name") or "Параметр",
                        tz_requirement=aspec.get("tz_requirement") or "",
                        product_fact=aspec.get("product_fact") or "Нет подтвержденных данных",
                        status=aspec.get("status") or "clarify",
                        comment=aspec.get("comment") or "",
                        source_url=aspec.get("source_url") or "",
                    )
                    for aspec in (a.get("specs_breakdown") or [])
                    if isinstance(aspec, dict)
                ]
                alts_list.append(AlternativeProduct(
                    brand=a.get("brand") or "Аналог",
                    model=a.get("model") or "",
                    manufacturer=a.get("manufacturer") or a.get("brand") or "",
                    confidence=float(a.get("confidence") or 0.85),
                    notes=a.get("notes") or "",
                    specs_breakdown=alt_specs,
                    source_url=a.get("source_url") or "",
                ))

        gisp_obj = None
        if p.get("gisp_match") and isinstance(p["gisp_match"], dict):
            gm = p["gisp_match"]
            gisp_obj = GispRegistryMatch(
                registry_number=gm.get("registry_number") or "",
                manufacturer=gm.get("manufacturer") or "",
                product=gm.get("product") or "",
                inn=gm.get("inn") or "",
                conclusion_number=gm.get("conclusion_number") or "",
                valid_until=gm.get("valid_until") or "",
                source_url=gm.get("source_url") or "",
                matched=True,
            )
        elif p.get("minprom_registry_number"):
            gisp_obj = GispRegistryMatch(
                registry_number=str(p.get("minprom_registry_number")),
                manufacturer=str(p.get("minprom_manufacturer") or p.get("manufacturer") or ""),
                product=str(p.get("minprom_product") or p.get("identified_model") or ""),
                inn="",
                conclusion_number=str(p.get("minprom_conclusion_number") or ""),
                valid_until="",
                source_url=str(p.get("minprom_source_url") or "https://gisp.gov.ru/pp719v2/pub/prod/"),
                matched=True,
            )

        typed_positions.append(ExactProductPosition(
            position_no=int(p.get("position_no") or idx),
            position_id=str(p.get("position_id") or ""),
            status=str(p.get("status") or ("found" if p.get("identified_model") and p.get("identified_brand") else "needs_clarification")),
            error=str(p.get("error") or ""),
            name_in_tz=p.get("name_in_tz") or f"Позиция {idx}",
            identified_brand=p.get("identified_brand") or "",
            identified_model=p.get("identified_model") or "",
            manufacturer=p.get("manufacturer") or p.get("identified_brand") or "",
            confidence=float(p.get("confidence") or 0.0),
            reasoning=p.get("reasoning") or "Проверьте подтверждение характеристик в источниках.",
            specs_breakdown=specs_list,
            alternative_brands=alts_list,
            gisp_match=gisp_obj,
            source_url=p.get("source_url") or "",
        ))

        for d in p.get("verified_documents") or []:
            if isinstance(d, dict):
                if d not in verified_docs_collected:
                    verified_docs_collected.append(d)
                if d.get("domain") and d["domain"] not in web_sources_collected:
                    web_sources_collected.append(d["domain"])

    try:
        await auto_fill_ai_recommendations(
            settings=settings,
            positions=[p for p in typed_positions if p.status == "found"],
        )
    except Exception as auto_exc:
        logger.debug("auto_fill_recommendations_failed: %s", auto_exc)

    raw_count = max(len(positions_raw), max((int(p.get("total_tz_positions") or 0) for p in positions_raw if isinstance(p, dict)), default=0))
    found_count = sum(p.status == "found" for p in typed_positions)
    summary_text = f"Обработано позиций: {len(typed_positions)}. Найдены модели: {found_count}. Остальные позиции требуют уточнения или повторного поиска."
    if raw_count > MAX_EXACT_POSITIONS_PER_JOB:
        limit_note = (
            f"В исходном ТЗ обнаружено {raw_count} позиций. "
            f"Сформирован детальный инженерный анализ и Форма 2 по топ-{MAX_EXACT_POSITIONS_PER_JOB} ключевым позициям оборудования/материалов "
            f"(работы и мелкий крепеж исключены). Для анализа остальных позиций выполните отдельный запуск."
        )
        summary_text = f"{limit_note}\n\n{summary_text}".strip()

    return ExactProductReport(
        procurement_title=procurement_title or (typed_positions[0].name_in_tz if typed_positions else "Подбор товара и аналогов"),
        total_positions=len(typed_positions),
        positions=typed_positions,
        summary=summary_text,
        yandex_requests_count=0,
        yandex_cost_rub=0.0,
        search_metrics_available=False,
        web_sources=web_sources_collected[:10],
        verified_documents=verified_docs_collected[:10],
    )


async def analyze_exact_product(
    settings: SystemSettings,
    context: str,
    procurement_title: str = "",
    progress_callback: Any = None,
    selected_positions: Optional[List[Dict[str, Any]]] = None,
) -> ExactProductReport:
    from .search_metrics import SearchMetrics, active_search_metrics
    metrics = SearchMetrics()
    token = active_search_metrics.set(metrics)
    try:
        report = await _analyze_exact_product(settings, context, procurement_title, progress_callback, selected_positions)
        report.yandex_requests_count = metrics.requests
        unit_price = getattr(settings, "yandex_search_price_per_request", None)
        report.yandex_cost_rub = round(metrics.requests * float(0.04 if unit_price is None else unit_price), 2)
        report.search_metrics_available = True
        return report
    finally:
        active_search_metrics.reset(token)
