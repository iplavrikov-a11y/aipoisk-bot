"""
Интеллектуальный майнер доказательств и точных товаров из документов закупки (Tender Package Evidence Miner).
Анализирует текст прикрепленных к закупке файлов (Разрешения Минпромторга, Обоснование НМЦК,
коммерческие предложения, технические спецификации, ТУ, проект контракта, разъяснения).

Извлекает:
1. Официальные разрешения Минпромторга (ПП РФ 1875 / 616 / 878 / 719) со статусом permitted_by_minprom.
2. Заложенные заказчиком или поставщиками конкретные марки, модели, заводы-изготовители и артикулы.
3. Упомянутые отечественные аналоги (для блока эквивалентов).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional

from ..ai import call_llm
from ..models import SystemSettings

logger = logging.getLogger(__name__)


def _get_call_llm():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "call_llm"):
        return getattr(mod, "call_llm")
    from ..ai import call_llm
    return call_llm

EVIDENCE_MINER_PROMPT = """Ты — ведущий эксперт по государственным закупкам (44-ФЗ, 223-ФЗ) и анализу закупочной документации.
Твоя задача — внимательно изучить приложенный текст официальных документов закупки (файлы заказчика: Разрешения Минпромторга, Обоснование НМЦК, коммерческие предложения поставщиков, техническую часть, ТУ, проект договора, протоколы) и выявить ТОЧНЫЙ ТОВАР, МОДЕЛЬ, ЗАВОД-ИЗГОТОВИТЕЛЬ и АНАЛОГИ, которые заложены в закупку.

Наименование закупки: {procurement_title}

Текст документов закупки:
{documents_text}

ИНСТРУКЦИЯ ПО ИЗВЛЕЧЕНИЮ ДОКАЗАТЕЛЬСТВ:
1. ОФИЦИАЛЬНЫЕ РАЗРЕШЕНИЯ МИНПРОМТОРГА РФ:
   - Если в документах есть Разрешение Минпромторга (или Заявка на выдачу разрешения по ПП РФ 1875, 616, 878, 719):
     * Извлеки: номер разрешения, дату выдачи, номер заявки, нормативное постановление.
     * Заявленный товар, фирму-производителя, точную марку/модель, страну происхождения.
     * Поставщика/заявителя в РФ (наименование, ИНН, ОГРН).
     * Указанные в документе отечественные аналоги (завод, модель, ТУ), по которым проводилось сравнение.
     * Все технические параметры и характеристики из таблицы сравнения.

2. ОБОСНОВАНИЕ НМЦК И КОММЕРЧЕСКИЕ ПРЕДЛОЖЕНИЯ:
   - Если в расчете цен или приложенных коммерческих предложениях названы конкретные модели, производители, торговые марки или артикулы, на основе которых сформирована цена — извлеки их.

3. ТУ И СПЕЦИФИКАЦИЯ:
   - Если в спецификации или договоре указаны конкретные ТУ заводов (например "ТУ 5433-002-..."), чертежи или заводские шифры — извлеки производителя и марку.

4. СТРОГИЙ ЗАПРЕТ ВЫДУМЫВАНИЯ И СЧИТЫВАНИЯ ПРЕДЫДУЩИХ ДОГАДОК ИИ:
   - Извлекай ТОЛЬКО то, что прямо и дословно зафиксировано в оригинальных документах заказчика (файлы смет, разрешений Минпромторга, обоснований НМЦК, КП поставщиков)!
   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО извлекать догадки и приписки ИИ вида «Для позиции...», «Точный товар:», «Аналог 1:»!
   - Если прямых указаний на конкретную модель/производителя в оригинальных документах нет — возвращай "found": false.

Ответь СТРОГО в формате JSON:
{{
  "found": true,
  "minprom_permit": {{
    "has_permit": true,
    "permit_number": "Номер разрешения (если есть)",
    "permit_date": "Дата разрешения",
    "application_number": "Номер заявки (если есть)",
    "resolution_pp": "ПП РФ № 1875 / ПП РФ № 616 / и т.д.",
    "status": "permitted_by_minprom",
    "declared_product": "Наименование товара",
    "manufacturer": "Завод-производитель",
    "model": "Точная модель / марка",
    "supplier_name": "Поставщик в РФ",
    "supplier_inn": "ИНН поставщика",
    "details": "Краткое описание разрешения Минпромторга"
  }},
  "evidence_products": [
    {{
      "name_in_tz": "Наименование позиции в ТЗ",
      "brand": "Выявленный бренд или завод",
      "model": "Точная модель или маркировка",
      "manufacturer": "Завод-производитель",
      "supplier": "Поставщик / заявитель (если указан)",
      "supplier_inn": "ИНН поставщика (если указан)",
      "source_type": "minprom_permit",
      "confidence": 1.0,
      "reasoning": "Обоснование: в каком официальном документе закупки прямо зафиксирован этот товар",
      "facts": {{
        "Наименование параметра": "Точное значение из документа"
      }},
      "analogs": [
        {{
          "brand": "Бренд аналога",
          "model": "Модель аналога",
          "manufacturer": "Производитель аналога",
          "standard_or_tu": "ТУ или ГОСТ аналога",
          "notes": "Пояснение из документа"
        }}
      ]
    }}
  ]
}}
"""


def extract_high_signal_evidence_text(full_text: str, max_chars: int = 40000) -> str:
    """
    Выделяет из общего текста документов закупки наиболее релевантные разделы:
    - Разрешения Минпромторга
    - Обоснование НМЦК и коммерческие предложения
    - Спецификацию и ТУ
    - Разъяснения заказчика
    """
    if not full_text:
        return ""
    text_len = len(full_text.strip())
    if text_len <= max_chars:
        return full_text.strip()

    file_chunks = re.split(r"(?=(?:=== FILE: |### Файл: ))", full_text)
    high_priority_chunks: List[str] = []
    normal_chunks: List[str] = []

    priority_keywords = (
        "разрешен", "минпромторг", "нмцк", "обоснован", "коммерческ", "предложен",
        "прайс", "спецификац", "описани", "заявк", "паспорт", "сертификат"
    )

    def chunk_score(chunk: str) -> int:
        c_low = chunk[:300].lower()
        score = 0
        if "разрешен" in c_low and "минпромторг" in c_low:
            score += 100
        elif "разрешен" in c_low:
            score += 80
        elif "нмцк" in c_low or "обоснован" in c_low:
            score += 60
        elif "коммерческ" in c_low or "предложен" in c_low:
            score += 50
        elif "спецификац" in c_low or "описани" in c_low:
            score += 40
        if "=== file:" in c_low or "### файл:" in c_low:
            score += 15
        return score

    for chunk in file_chunks:
        chunk_clean = chunk.strip()
        if not chunk_clean:
            continue
        chunk_lower = chunk_clean[:500].lower()
        if any(kw in chunk_lower for kw in priority_keywords):
            high_priority_chunks.append(chunk_clean)
        else:
            normal_chunks.append(chunk_clean)

    high_priority_chunks.sort(key=chunk_score, reverse=True)

    assembled: List[str] = []
    curr_len = 0

    for c in high_priority_chunks:
        c_sub = c[:15000]
        if curr_len + len(c_sub) > max_chars:
            remaining = max_chars - curr_len
            if remaining > 1000:
                assembled.append(c_sub[:remaining])
            break
        assembled.append(c_sub)
        curr_len += len(c_sub)

    if curr_len < max_chars:
        for c in normal_chunks:
            c_sub = c[:5000]
            if curr_len + len(c_sub) > max_chars:
                remaining = max_chars - curr_len
                if remaining > 500:
                    assembled.append(c_sub[:remaining])
                break
            assembled.append(c_sub)
            curr_len += len(c_sub)

    result = "\n\n".join(assembled).strip()
    return result if len(result) > 100 else full_text[:max_chars].strip()


def strip_under_table_ai_blocks(text: str) -> str:
    """Удаляет из текста подтабличные и приписанные догадки ИИ («Для позиции «...»», «Точный товар: ...», «Аналог 1: ...»)."""
    if not text:
        return ""
    text = re.sub(
        r"(?is)(?:^|\n)[ \t]*(?:[-*•]\s*)?\*{0,2}(?:Для позиции|Точный товар|Аналог\s*\d*)[\s:«\"'`*].+?(?=(?:#+\s*|=== TABLE|=== FILE:|### Файл:|\n\s*Условия|\Z))",
        "\n",
        text,
    )
    return text.strip()


def isolate_tz_table_content(raw_text: str) -> str:
    """
    Извлекает ИСКЛЮЧИТЕЛЬНО табличную часть технического задания.
    Полностью отсекает всё, что идет до или ниже таблицы:
    - Предшествующие догадки ИИ («Точный товар: ...», «Аналог 1: ...», «Для позиции «...»»)
    - Условия поставки, сроки, гарантию, оплату
    - Служебные примечания и комментарии
    """
    if not raw_text:
        return ""
    text = raw_text.strip()

    # 1. HTML-таблица (<table ...>...</table>)
    if "<table" in text.lower():
        end_idx = text.lower().rfind("</table>")
        if end_idx != -1:
            end_pos = end_idx + len("</table>")
            start_idx = 0
            m_title = re.search(
                r"(?i)(?:ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|#+\s*(?:4\.5\s*)?ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|##\s*Спецификация|##\s*Товары)",
                text[:end_pos],
            )
            if m_title:
                start_idx = m_title.start()
            return text[start_idx:end_pos].strip()

    # 2. Markdown / docx-таблица (| ... | или === TABLE)
    lines = text.splitlines()
    table_line_indices = [
        i for i, line in enumerate(lines)
        if (line.strip().startswith("|") and line.strip().endswith("|"))
        or " | " in line
        or line.strip().startswith("=== TABLE")
    ]
    if table_line_indices:
        first_tbl = table_line_indices[0]
        last_tbl = first_tbl
        for idx in table_line_indices[1:]:
            if idx - last_tbl <= 3:
                last_tbl = idx
            else:
                break

        start_idx = first_tbl
        for j in range(first_tbl - 1, max(-1, first_tbl - 6), -1):
            l = lines[j].strip()
            if not l:
                continue
            if any(h in l.lower() for h in ("техническое задание", "спецификация", "товары")) or l.startswith("#") or l.startswith("**"):
                start_idx = j
            elif start_idx == first_tbl:
                start_idx = j

        return "\n".join(lines[start_idx : last_tbl + 1]).strip()

    return text


def align_facts_to_requirements(
    raw_facts: Dict[str, str],
    requirements: List[Dict[str, str]],
) -> Dict[str, str]:
    aligned: Dict[str, str] = {}
    if not raw_facts:
        return {}
    if not requirements:
        return dict(raw_facts)

    from .matcher import _normalize_param_name

    exact_map = {r["param_name"].strip().lower(): r["param_name"] for r in requirements}
    norm_map = {_normalize_param_name(r["param_name"]): r["param_name"] for r in requirements}

    synonyms = {
        "описание товара": ["материал", "состав", "внешний вид", "свойства", "описание"],
        "назначение": ["функции", "область применения", "применение", "сфера применения"],
        "толщина / высота": ["толщина", "высота", "калибр"],
        "длина в рулоне": ["длина рулона", "длина", "метраж", "намотка"],
        "масса 1 м²": ["масса 1м2", "масса кв м", "плотность", "граммность", "вес 1м2"],
        "вес одного рулона": ["вес рулона", "масса рулона", "масса одного рулона", "вес бобины"],
        "ширина рулона": ["ширина", "ширина полотна", "формат"],
    }

    for k, v in raw_facts.items():
        k_clean = str(k or "").strip()
        val = str(v or "").strip()
        if not k_clean or not val:
            continue

        target = exact_map.get(k_clean.lower())
        if not target:
            target = norm_map.get(_normalize_param_name(k_clean))
        if not target:
            k_low = k_clean.lower()
            for req_name, syn_list in synonyms.items():
                canonical = exact_map.get(req_name) or norm_map.get(_normalize_param_name(req_name))
                if canonical and (any(s in k_low for s in syn_list) or any(k_low in s for s in syn_list)):
                    target = canonical
                    break
        if not target:
            k_tokens = {w for w in re.findall(r"[а-яa-z0-9]+", k_clean.lower()) if len(w) >= 2}
            if k_tokens:
                best_overlap = 0
                best_target = None
                for r in requirements:
                    r_name = r["param_name"]
                    r_tokens = {w for w in re.findall(r"[а-яa-z0-9]+", r_name.lower()) if len(w) >= 2}
                    if not r_tokens:
                        continue
                    common = len(k_tokens & r_tokens)
                    if common > best_overlap and common >= min(len(k_tokens), len(r_tokens)) * 0.5:
                        best_overlap = common
                        best_target = r_name
                if best_target:
                    target = best_target

        if target:
            aligned[target] = val
        else:
            aligned[k_clean] = val

    return aligned


async def mine_procurement_evidence_ai(
    report_text: str,
    procurement_title: str = "",
    known_requirements: Optional[List[Dict[str, str]]] = None,
    settings: Optional[SystemSettings] = None,
) -> Dict[str, Any]:
    """
    Глубокий ИИ-майнинг документов закупки (Tier 0 Evidence).
    """
    if not report_text or len(report_text.strip()) < 20:
        return {"found": False, "evidence_products": []}

    cleaned_text = strip_under_table_ai_blocks(report_text)
    targeted_text = extract_high_signal_evidence_text(cleaned_text, max_chars=35000)
    if not targeted_text or len(targeted_text) < 20:
        return {"found": False, "evidence_products": []}

    prompt = EVIDENCE_MINER_PROMPT.format(
        procurement_title=procurement_title or "Закупка",
        documents_text=targeted_text,
    )

    if known_requirements:
        reqs_lines = [f"- {r.get('param_name')}: {r.get('tz_requirement')}" for r in known_requirements[:15]]
        prompt += (
            "\n\nСПИСОК ТРЕБУЕМЫХ ХАРАКТЕРИСТИК ИЗ ТЗ (для точной привязки фактов):\n"
            + "\n".join(reqs_lines)
            + "\nВАЖНО: В словаре 'facts' используй строго эти названия параметров, если характеристика найдена в тексте!"
        )

    if settings is None:
        from ..dependencies import get_db
        from ..models import get_system_settings
        db = next(get_db())
        try:
            settings = get_system_settings(db)
        finally:
            db.close()

    try:
        call_fn = _get_call_llm()
        raw = await call_fn(
            settings,
            prompt=prompt,
            system_prompt=(
                "Ты — объективный эксперт по государственным закупкам (44-ФЗ/223-ФЗ). "
                "Извлекай только факты, подтвержденные официальными документами закупки. Отвечай только валидным JSON."
            ),
            json_mode=True,
            tier="light",
            routing_key="procurement_brand_detection",
        )
        if not raw:
            return {"found": False, "evidence_products": []}

        cleaned = str(raw).strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        data = json.loads(cleaned.strip())

        if not isinstance(data, dict):
            return {"found": False, "evidence_products": []}

        if "positions" in data and not data.get("evidence_products"):
            data["found"] = True
            ev_prods = []
            for pos in data["positions"]:
                ev_prods.append({
                    "name": pos.get("name_in_tz") or pos.get("identified_model"),
                    "brand": pos.get("identified_brand"),
                    "model": pos.get("identified_model"),
                    "manufacturer": pos.get("manufacturer"),
                    "confidence": pos.get("confidence", 0.95),
                    "reasoning": pos.get("reasoning", ""),
                    "source_url": pos.get("source_url", ""),
                    "specs_breakdown": pos.get("specs_breakdown", []),
                    "alternative_brands": pos.get("alternative_brands", []),
                    "evidence_tier": 0,
                })
            data["evidence_products"] = ev_prods

        if not data.get("found"):
            return {"found": False, "evidence_products": []}

        for prod in (data.get("evidence_products") or []):
            if isinstance(prod, dict):
                b = str(prod.get("brand") or "").strip()
                mfr = str(prod.get("manufacturer") or "").strip()
                if not b or any(w in b.lower() for w in ("не указан", "пусто", "none", "null", "по документу")):
                    if mfr:
                        prod["brand"] = mfr
                if known_requirements and prod.get("facts"):
                    prod["facts"] = align_facts_to_requirements(prod["facts"], known_requirements)

        logger.info(
            "procurement_evidence_mined: has_permit=%s, products_count=%s",
            bool((data.get("minprom_permit") or {}).get("has_permit")),
            len(data.get("evidence_products") or []),
        )
        return data

    except Exception as exc:
        logger.warning("mine_procurement_evidence_failed: %s", exc)
        return {"found": False, "evidence_products": []}


mine_tender_evidence = mine_procurement_evidence_ai

