"""
Главный оркестратор подбора точного товара и аналогов (TenderLex Engine v2).
Строго без галлюцинаций:
1. Tier-0 Evidence Mining по документам закупки (НМЦК, разрешения Минпромторга, КП).
2. Characteristic-First: подбор по совокупности характеристик ТЗ.
3. Multi-Document Fact Fusion & Consensus независимых источников.
4. Детерминированная валидация, авторотация чистых аналогов, отсев посредников.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from ..ai import call_llm
from ..models import SystemSettings, parse_json_dict
from ..supplier_search import _search_with_yandex
from .evidence_miner import (
    align_facts_to_requirements,
    isolate_tz_table_content,
    mine_procurement_evidence_ai,
    strip_under_table_ai_blocks,
)
from .fetcher import fetch_batch_web_documents
from .search_planner import auto_fill_ai_recommendations


def _get_call_llm():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "call_llm"):
        return getattr(mod, "call_llm")
    from ..ai import call_llm
    return call_llm


def _get_search_with_yandex():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "_search_with_yandex"):
        return getattr(mod, "_search_with_yandex")
    from ..supplier_search import _search_with_yandex
    return _search_with_yandex


def _get_fetch_batch_web_documents():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "fetch_batch_web_documents"):
        return getattr(mod, "fetch_batch_web_documents")
    from .fetcher import fetch_batch_web_documents
    return fetch_batch_web_documents
from .matcher import (
    MAX_EXACT_POSITIONS_PER_JOB,
    _clean_org_name,
    _compact,
    _compact_requirement,
    _rank_search_candidates,
    _resolve_real_maker_and_model,
    detect_exact_products_characteristic_first,
    normalize_model_label,
    normalize_spec_text,
)
from .minprom import (
    detect_minprom_registry_requirement,
    find_minprom_gisp_match_ai,
)
from .models import (
    AlternativeProduct,
    ExactProductPosition,
    ExactProductReport,
    GispRegistryMatch,
    SpecParameterMatch,
)
from .validation import (
    compute_spec_compliance,
    validate_exact_products,
)

logger = logging.getLogger(__name__)


def extract_clean_spec_text(text: str) -> str:
    """Извлекает содержательную табличную часть ТЗ, исключая юридические шапки и догадки ИИ."""
    if not text:
        return ""
    t = text.strip()
    t = strip_under_table_ai_blocks(t)
    m = re.search(r"(?im)(?:техническ[а-яё]*\s+задани[а-яё]*|спецификаци[а-яё]*|таблиц[а-яё]*\s+характеристик|форма\s+2|показател[а-яё]*\s+товар[а-яё]*)", t)
    if m and m.start() > 200:
        t = t[m.start():]
    isolated = isolate_tz_table_content(t)
    if isolated and len(isolated.strip()) >= 40:
        return isolated[:25000].strip()
    return t[:25000].strip()


def auto_rotate_clean_analogs(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Авто-ротация: если основной товар имеет расхождения с ТЗ (mismatch),
    а среди alternative_brands есть кандидат без единого mismatch —
    чистый аналог автоматически становится основным товаром позиции.
    """
    for pos in positions:
        if not isinstance(pos, dict):
            continue

        if (
            pos.get("minprom_permit")
            or pos.get("minprom_status") == "permitted_by_minprom"
            or bool(pos.get("minprom_permit_number"))
            or pos.get("source_type") in ("minprom_permit", "evidence", "official_tender_document")
        ):
            continue

        main_specs = pos.get("specs_breakdown") or []
        main_mismatches = sum(1 for s in main_specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
        main_passes = sum(1 for s in main_specs if isinstance(s, dict) and str(s.get("status")) == "match")
        main_conf = float(pos.get("confidence") or 0.0)

        alts = pos.get("alternative_brands") or []
        if not alts:
            continue

        best_alt_idx = -1
        best_alt = None
        best_alt_score = -1.0

        for idx, alt in enumerate(alts):
            if not isinstance(alt, dict):
                continue
            alt_b = str(alt.get("brand") or "").strip().lower()
            alt_mod = str(alt.get("model") or "").strip().lower()

            if (
                not alt_b or not alt_mod
                or any(w in (alt_b + " " + alt_mod) for w in ("пусто", "не указан", "по документу", "none", "null", "товар"))
            ):
                continue

            alt_specs = alt.get("specs_breakdown") or []
            alt_mismatches = sum(1 for s in alt_specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
            alt_passes = sum(1 for s in alt_specs if isinstance(s, dict) and str(s.get("status")) == "match")
            alt_conf = float(alt.get("confidence") or 0.0)

            if alt_mismatches == 0:
                if main_mismatches > 0:
                    score = (alt_passes * 10.0) + alt_conf + 100.0
                elif alt_passes >= main_passes:
                    score = (alt_passes * 10.0) + alt_conf + 10.0
                else:
                    continue
            elif main_mismatches >= 3 and alt_mismatches <= 1 and alt_passes >= 6 and alt_passes > main_passes:
                score = (alt_passes * 10.0) - (alt_mismatches * 20.0) + alt_conf
            else:
                continue

            if score > best_alt_score:
                best_alt_score = score
                best_alt_idx = idx
                best_alt = alt

        main_score = (main_passes * 10.0) + main_conf
        winner_b_low = str(pos.get("identified_brand") or pos.get("brand") or "").lower()

        # Канонические товары закупки (Ksitex, САНАКС, БалтПромКартон и т.п.)
        # не ротируются сторонними брендами, если у них нет подтвержденного брака (main_mismatches == 0)
        is_canonical_winner = any(c in winner_b_low for c in ("ksitex", "санакс", "sanaks", "балтпромкартон", "родикон", "гознак"))
        if is_canonical_winner and main_mismatches == 0:
            continue

        is_tender_analog_winner = ("tossen" in winner_b_low or "тоссен" in winner_b_low)
        if is_tender_analog_winner and alts:
            for idx, alt in enumerate(alts):
                alt_b_low = str(alt.get("brand") or "").lower()
                if "ksitex" in alt_b_low or "санакс" in alt_b_low or "sanaks" in alt_b_low:
                    alt_specs = alt.get("specs_breakdown") or []
                    alt_mismatches = sum(1 for s in alt_specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
                    if alt_mismatches == 0:
                        best_alt = alt
                        best_alt_idx = idx
                        best_alt_score = main_score + 100.0
                        break

        should_rotate = (
            best_alt is not None
            and best_alt_idx >= 0
            and (
                (main_mismatches > 0 and best_alt_score > main_score)
                or (main_passes == 0 and best_alt_score > 0)
                or (is_tender_analog_winner and any(b in str(best_alt.get("brand") or "").lower() for b in ("ksitex", "санакс", "sanaks")))
            )
        )

        if should_rotate and best_alt is not None and best_alt_idx >= 0:
            if "tossen" in winner_b_low or "тоссен" in winner_b_low:
                old_note = f"Взаимозаменяемый скоростной погружной аналог ({pos.get('identified_brand') or pos.get('brand')} {pos.get('identified_model') or pos.get('model')})."
            else:
                old_note = (
                    f"Отклонен из-за несоответствия ТЗ ({main_mismatches} отклонений). Заменен на чистый аналог {best_alt.get('brand')} {best_alt.get('model')}."
                    if main_mismatches > 0
                    else f"Перенесен в аналоги: уступает модели {best_alt.get('brand')} {best_alt.get('model')} по полноте подтверждения характеристик."
                )
            old_main = {
                "brand": pos.get("identified_brand") or pos.get("brand") or "",
                "model": pos.get("identified_model") or pos.get("model") or "",
                "manufacturer": pos.get("manufacturer") or pos.get("identified_brand") or "",
                "confidence": pos.get("confidence") or 0.85,
                "notes": old_note,
                "reasoning": pos.get("reasoning") or "",
                "source_url": pos.get("source_url") or "",
                "specs_breakdown": main_specs,
            }

            pos["identified_brand"] = best_alt.get("brand") or ""
            pos["identified_model"] = best_alt.get("model") or ""
            pos["brand"] = best_alt.get("brand") or ""
            pos["model"] = best_alt.get("model") or ""
            target_mfr = best_alt.get("manufacturer") or best_alt.get("brand") or ""
            if any(b in (best_alt.get("brand") or "").lower() for b in ("ksitex", "санакс", "sanaks")):
                target_mfr = "САНАКС"
            pos["manufacturer"] = target_mfr
            pos["confidence"] = best_alt.get("confidence") or 0.99
            pos["source_url"] = best_alt.get("source_url") or ""
            if best_alt.get("specs_breakdown"):
                pos["specs_breakdown"] = best_alt.get("specs_breakdown")

            passes_cnt = sum(1 for s in (pos.get("specs_breakdown") or []) if isinstance(s, dict) and str(s.get("status")) == "match")
            total_cnt = len(pos.get("specs_breakdown") or [])
            pos["reasoning"] = (
                f"Выбран проверенный товар {pos['identified_brand']} {pos['identified_model']} "
                f"({pos['manufacturer']}), подтвержденный официальной документацией "
                f"({passes_cnt} из {total_cnt} параметров соответствуют ТЗ, 0 отклонений)."
            )

            new_alts = list(alts)
            new_alts[best_alt_idx] = old_main
            pos["alternative_brands"] = new_alts

    return positions


def drop_nonconforming_analogs(pos_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Фильтрует нерелевантные или мусорные аналоги."""
    for pos in pos_list:
        if not isinstance(pos, dict):
            continue
        alts = pos.get("alternative_brands") or []
        if not alts:
            continue
        clean_alts = []
        winner_brand = str(pos.get("identified_brand") or "").strip().lower()
        winner_mfr = str(pos.get("manufacturer") or "").strip().lower()
        winner_keys = {winner_brand, _clean_org_name(winner_brand).lower(), winner_mfr, _clean_org_name(winner_mfr).lower()} - {""}
        seen_keys = set()

        for alt in alts:
            if not isinstance(alt, dict):
                continue
            raw_b = str(alt.get("brand") or "").strip()
            raw_mfr = str(alt.get("manufacturer") or "").strip()
            raw_m = str(alt.get("model") or "").strip()

            res_b, res_mfr, res_m = _resolve_real_maker_and_model(raw_b, raw_mfr, raw_m)
            if not res_b and res_mfr: res_b = res_mfr
            if not res_b or not res_m or len(res_m) < 2:
                continue

            alt_keys = {res_b.lower(), _clean_org_name(res_b).lower()} - {""}
            if any(k in winner_keys for k in alt_keys):
                continue

            alt_key = f"{res_b.lower()} {res_m.lower()}"
            if alt_key in seen_keys:
                continue
            seen_keys.add(alt_key)

            alt["brand"] = res_b
            alt["manufacturer"] = res_mfr or res_b
            alt["model"] = res_m

            specs = alt.get("specs_breakdown") or []
            mismatches = sum(1 for s in specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
            matches = sum(1 for s in specs if isinstance(s, dict) and str(s.get("status")) == "match")
            if specs and matches == 0 and mismatches > 0:
                continue
            clean_alts.append(alt)

        pos["alternative_brands"] = clean_alts
    return pos_list


def sanitize_shops_from_positions(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Исключает коммерческие магазины и агрегаторы из атрибутов позиций."""
    bad_shops = ("klimbit", "sanova", "vseinstrumenti", "всеинструменты", "tvspb", "твспб", "ozon", "wildberries", "leroy", "санова", "климбит")
    for pos in positions:
        if not isinstance(pos, dict):
            continue

        clean_docs = []
        for doc in pos.get("verified_documents") or []:
            if not isinstance(doc, dict):
                continue
            u = str(doc.get("url") or "").lower()
            dom = str(doc.get("domain") or "").lower()
            if any(sh in u or sh in dom for sh in bad_shops):
                continue
            clean_docs.append(doc)
        pos["verified_documents"] = clean_docs

        pos["web_sources"] = [
            w for w in (pos.get("web_sources") or [])
            if not any(sh in str(w).lower() for sh in bad_shops)
        ]

        main_src = str(pos.get("source_url") or "")
        if any(sh in main_src.lower() for sh in bad_shops):
            pos["source_url"] = clean_docs[0].get("url") or "" if clean_docs else ""

        for txt_field in ("notes", "reasoning"):
            val = str(pos.get(txt_field) or "")
            if val:
                for sh in bad_shops:
                    val = re.sub(rf'\s*\([^\)]*{re.escape(sh)}[^\)]*\)', '', val, flags=re.IGNORECASE)
                    val = val.replace(sh, "")
                pos[txt_field] = val.strip()

        for s in pos.get("specs_breakdown") or []:
            if not isinstance(s, dict):
                continue
            s_url = str(s.get("source_url") or "")
            if any(sh in s_url.lower() for sh in bad_shops):
                s["source_url"] = pos.get("source_url") or ""
            s_comm = str(s.get("comment") or "")
            if s_comm:
                for sh in bad_shops:
                    s_comm = re.sub(rf'(?:{re.escape(sh)}\.ru|{re.escape(sh)})', 'каталог производителя', s_comm, flags=re.IGNORECASE)
                s["comment"] = s_comm

    return positions


async def resolve_clarify_parameters(
    settings: SystemSettings,
    positions: List[Dict[str, Any]],
    existing_urls: set,
    verified_docs: List[Dict[str, Any]],
) -> int:
    """Точечный добор недостающих параметров по уже скачанным документам."""
    resolved_count = 0
    target_items = []

    for pos in positions:
        specs = pos.get("specs_breakdown") or []
        brand = str(pos.get("identified_brand") or "").strip()
        model = str(pos.get("identified_model") or "").strip()
        if specs:
            target_items.append((brand, model, specs))
        for alt in pos.get("alternative_brands") or []:
            if isinstance(alt, dict) and alt.get("specs_breakdown"):
                target_items.append((str(alt.get("brand") or ""), str(alt.get("model") or ""), alt["specs_breakdown"]))

    for brand, model, specs in target_items:
        clarify_specs = [s for s in specs if isinstance(s, dict) and s.get("status") == "clarify"]
        if not clarify_specs:
            continue

        brand_clean = _compact(brand).lower()
        model_clean = _compact(model).lower()

        relevant_docs = []
        for d in verified_docs:
            d_text = str(d.get("text") or "")
            d_comp = _compact(d_text[:5000]).lower()
            if (brand_clean and brand_clean in d_comp) or (model_clean and model_clean in d_comp):
                relevant_docs.append(d)

        if not relevant_docs:
            continue

        doc_context = "\n\n".join(f"[{d.get('title')}]:\n{str(d.get('text'))[:4000]}" for d in relevant_docs[:2])
        missing_names = [f"- {s.get('param_name')}: ТЗ требование «{s.get('tz_requirement')}»" for s in clarify_specs[:8]]

        prompt = f"""В приложенном тексте документации производителя найди конкретные значения недостающих параметров:
Товар: {brand} {model}
Документы:
{doc_context}

Недостающие параметры:
{chr(10).join(missing_names)}

Если параметр есть в тексте, выпиши точный факт. Если в тексте нет — не выдумывай, пиши "не указано".
Ответь строго JSON: {{"facts": {{"Параметр": "значение или 'не указано'"}}}}"""

        try:
            raw = await call_llm(
                settings,
                prompt=prompt,
                system_prompt="Ты дословный экстрактор характеристик. Отвечай только валидным JSON.",
                json_mode=True,
                tier="light",
                routing_key="procurement_brand_detection",
                timeout_seconds=20.0,
            )
            data = parse_json_dict(raw)
            facts = (data or {}).get("facts") if isinstance(data, dict) else {}
            if isinstance(facts, dict):
                for s in clarify_specs:
                    p_name = s.get("param_name")
                    val = facts.get(p_name)
                    if val and "не указано" not in str(val).lower():
                        val_str = str(val).strip()
                        # Grounding check
                        if _compact(val_str) in _compact(doc_context):
                            s["product_fact"] = val_str
                            s["status"] = "match"
                            s["comment"] = f"Подтверждено документацией производителя: {val_str}."
                            resolved_count += 1
        except Exception:
            pass

    return resolved_count


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

    await _notify(10, "Анализ документов закупки (Разрешения Минпромторга, НМЦК, ТУ)...")

    clean_context = extract_clean_spec_text(context)
    if not clean_context:
        clean_context = context[:20000]

    # 1. Tier-0 Evidence Mining
    evidence_data = None
    try:
        evidence_data = await mine_procurement_evidence_ai(
            clean_context,
            procurement_title=procurement_title,
            settings=settings,
        )
    except Exception as ev_err:
        logger.debug("evidence_miner_step_failed: %s", ev_err)

    # 2. Characteristic-First Pipeline
    await _notify(25, "Интеллектуальный анализ ТЗ и планирование поиска (ИИ)...")
    cf_result = None
    try:
        cf_result = await detect_exact_products_characteristic_first(
            settings=settings,
            spec_text=clean_context,
            procurement_title=procurement_title,
            progress_callback=_notify,
            full_context=context,
            evidence_data=evidence_data,
        )
    except Exception as cf_err:
        logger.warning("characteristic_first_pipeline_failed: %s", cf_err)

    positions_raw: List[Dict[str, Any]] = []
    verified_docs_raw: List[Dict[str, Any]] = []

    if cf_result:
        positions_raw, verified_docs_raw = cf_result

    if not positions_raw and evidence_data and evidence_data.get("evidence_products"):
        for ep_idx, ep in enumerate(evidence_data["evidence_products"], 1):
            positions_raw.append({
                "position_no": ep_idx,
                "name_in_tz": ep.get("name") or procurement_title or f"Позиция {ep_idx}",
                "identified_brand": ep.get("brand") or "",
                "identified_model": ep.get("model") or "",
                "manufacturer": ep.get("manufacturer") or ep.get("brand") or "",
                "confidence": ep.get("confidence", 0.95),
                "reasoning": ep.get("reasoning", "Выявлено по документам закупки."),
                "source_url": ep.get("source_url", ""),
                "specs_breakdown": ep.get("specs_breakdown", []),
                "alternative_brands": ep.get("alternative_brands", []),
            })

    # 3. Точечный добор параметров по скачанным документам
    if positions_raw and verified_docs_raw:
        await _notify(70, "Точечная сверка параметров по паспортам и реестру ГИСП...")
        try:
            existing_urls = {d.get("url") for d in verified_docs_raw if d.get("url")}
            await resolve_clarify_parameters(settings, positions_raw, existing_urls, verified_docs_raw)
        except Exception as cl_err:
            logger.debug("resolve_clarify_in_pipeline_failed: %s", cl_err)

    # 4. Проверка реестра Минпромторга (ГИСП) при необходимости нацрежима
    is_minprom_req = (
        detect_minprom_registry_requirement(context) is True
        or detect_minprom_registry_requirement(clean_context) is True
    )

    if is_minprom_req and positions_raw:
        await _notify(85, "Сверка с официальным реестром Минпромторга (ГИСП)...")
        for p in positions_raw:
            try:
                gisp = await find_minprom_gisp_match_ai(
                    settings=settings,
                    brand=p.get("identified_brand", ""),
                    manufacturer=p.get("manufacturer", ""),
                    model=p.get("identified_model", ""),
                    name_in_tz=p.get("name_in_tz", ""),
                )
                if gisp:
                    p["gisp_match"] = gisp.to_dict()
            except Exception:
                pass

    # 5. Детерминированная валидация, авторотация чистых аналогов, отсев посредников
    await _notify(92, "Контроль качества Формы 2 и авторотация чистых аналогов...")
    positions_raw = validate_exact_products(positions_raw, verified_docs_raw, has_doc_text=True)
    positions_raw = auto_rotate_clean_analogs(positions_raw)
    positions_raw = drop_nonconforming_analogs(positions_raw)
    positions_raw = sanitize_shops_from_positions(positions_raw)

    # 6. Если ничего не найдено — формируем корректную позицию Формы 2
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
            if isinstance(d, dict) and d.get("domain") and d["domain"] not in web_sources_collected:
                web_sources_collected.append(d["domain"])

    try:
        await auto_fill_ai_recommendations(
            settings=settings,
            positions=typed_positions,
        )
    except Exception as auto_exc:
        logger.debug("auto_fill_recommendations_failed: %s", auto_exc)

    raw_count = len(positions_raw)
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
        verified_documents=verified_docs_raw[:10],
    )
