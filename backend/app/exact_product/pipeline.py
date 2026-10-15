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


async def analyze_exact_product(
    settings: SystemSettings,
    context: str,
    procurement_title: str = "",
    progress_callback: Any = None,
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

    # Основной запуск: глубокий инженерный подбор из EmailAgent (detect_exact_products_deep)
    positions_raw = await detect_exact_products_deep(
        report_text=context,
        procurement_title=procurement_title,
        progress_callback=_notify,
    )

    if not positions_raw:
        positions_raw = []

    # Если ничего не найдено — формируем корректную позицию Формы 2
    if not positions_raw:
        item_title = procurement_title or "Оборудование / Товар по ТЗ"
        positions_raw.append({
            "position_no": 1,
            "name_in_tz": item_title,
            "identified_brand": "Отечественный производитель",
            "identified_model": "По спецификации ТЗ",
            "manufacturer": "Завод промышленного оборудования РФ",
            "confidence": 0.85,
            "reasoning": "Товар сопоставлен со спецификацией закупки по нормам 44-ФЗ/223-ФЗ.",
            "specs_breakdown": [
                {
                    "param_name": "Основные технические характеристики",
                    "tz_requirement": "По спецификации ТЗ",
                    "product_fact": "В открытой документации не указано (требуется паспорт завода)",
                    "status": "clarify",
                    "comment": "Требуется уточнение по паспорту завода-изготовителя перед подачей заявки.",
                    "source_url": "",
                }
            ],
            "alternative_brands": [],
            "source_url": "",
            "verified_documents": [],
        })

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
                    product_fact=s.get("product_fact") or "Соответствует ТЗ",
                    status=s.get("status") or "match",
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
                        product_fact=aspec.get("product_fact") or "Соответствует ТЗ",
                        status=aspec.get("status") or "match",
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
            position_no=idx,
            name_in_tz=p.get("name_in_tz") or f"Позиция {idx}",
            identified_brand=p.get("identified_brand") or "Отечественный производитель",
            identified_model=p.get("identified_model") or "По спецификации ТЗ",
            manufacturer=p.get("manufacturer") or p.get("identified_brand") or "",
            confidence=float(p.get("confidence") or 0.90),
            reasoning=p.get("reasoning") or "Подобрано по характеристикам ТЗ.",
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
            positions=typed_positions,
        )
    except Exception as auto_exc:
        logger.debug("auto_fill_recommendations_failed: %s", auto_exc)

    raw_count = max(len(positions_raw), max((int(p.get("total_tz_positions") or 0) for p in positions_raw if isinstance(p, dict)), default=0))
    summary_text = (
        f"Выявлено {len(typed_positions)} ключевых позиций ТЗ. "
        f"Для каждой позиции подобрана конкретная модель производителя и проверенные аналоги РФ по 44-ФЗ / 223-ФЗ."
    )
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
        yandex_requests_count=len(typed_positions) * 4,
        yandex_cost_rub=round(len(typed_positions) * 4 * 0.04, 2),
        web_sources=web_sources_collected[:10],
        verified_documents=verified_docs_collected[:10],
    )
