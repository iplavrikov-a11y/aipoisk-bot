from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .procurement_sources import normalize_source_url

_RUB_RE = re.compile(
    r"([+\-\u2212\u2013]?\s*[~≈]?\s*\d[\d\s\xa0]*(?:[.,]\d+)?)\s*(?:₽|руб\.?)",
    re.IGNORECASE,
)
_PCT_RE = re.compile(
    r"([+\-\u2212\u2013]?\s*[~≈]?\s*\d+(?:[.,]\d+)?)\s*%",
)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_UTM_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_referrer"}


def clean_kontur_url(raw_url: str) -> str:
    """Normalize a Kontur.Zakupki URL and strip noisy UTM tracking params."""
    normalized = normalize_source_url(str(raw_url or "").strip())
    if not normalized:
        return ""
    try:
        parsed = urlparse(normalized)
        if "kontur.ru" not in (parsed.hostname or "").lower():
            return ""
        clean_host = (parsed.hostname or "").lower()
        clean_netloc = clean_host
        if parsed.port and not (
            (parsed.scheme == "https" and parsed.port == 443)
            or (parsed.scheme == "http" and parsed.port == 80)
        ):
            clean_netloc = f"{clean_host}:{parsed.port}"
        kept_query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in _UTM_KEYS
        ]
        cleaned = urlunparse(
            (
                parsed.scheme or "https",
                clean_netloc,
                parsed.path,
                "",
                urlencode(kept_query, doseq=True),
                "",
            )
        )
        return cleaned[:1000]
    except Exception:
        return normalized[:1000]


def _parse_signed_number(raw: str) -> float | None:
    text = (
        str(raw or "")
        .replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\xa0", " ")
        .strip()
    )
    text = re.sub(r"[~≈+]|\s+", "", text).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_margin_rub(val: float | None) -> str:
    if val is None:
        return ""
    rounded = round(val)
    sign = "−" if rounded < 0 else ("+" if rounded > 0 else "")
    formatted = f"{abs(rounded):,}".replace(",", " ")
    return f"{sign}{formatted} ₽"


def _format_margin_pct(val: float | None) -> str:
    if val is None:
        return ""
    rounded = round(val, 1)
    sign = "−" if rounded < 0 else ""
    body = f"{abs(rounded):.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{sign}{body}%"


def extract_margin_from_markdown(markdown: str) -> dict[str, Any]:
    """Extract estimated margin in RUB and % from a structured markdown report."""
    text = str(markdown or "")
    if not text.strip():
        return {
            "margin_rub": "",
            "margin_pct": "",
            "margin_rub_value": None,
            "margin_pct_value": None,
        }

    candidates: list[tuple[int, int, float | None, float | None]] = []
    for line_idx, line in enumerate(text.splitlines()):
        if not re.search(r"марж|прибыл", line, re.IGNORECASE):
            continue
        clean = re.sub(r"[*_`]+", "", line).strip()
        if not clean:
            continue

        if "|" in clean:
            parts = [p.strip() for p in clean.strip("|").split("|")]
            if len(parts) < 2:
                continue
            label_part = parts[0]
            val_part = parts[1]
        else:
            if ":" not in clean:
                continue
            label_part, val_part = clean.split(":", 1)

        if not re.search(r"марж|прибыл", label_part, re.IGNORECASE):
            continue
        if re.search(
            r"прочие расходы|безубыточ|запас прочност|ориентир для|резерв на торг|налог на прибыл",
            label_part,
            re.IGNORECASE,
        ):
            continue

        m_rub = _RUB_RE.search(val_part)
        m_pct = _PCT_RE.search(val_part)
        if not m_rub and not m_pct:
            continue

        rub_val = _parse_signed_number(m_rub.group(1)) if m_rub else None
        pct_val = _parse_signed_number(m_pct.group(1)) if m_pct else None
        if rub_val is None and pct_val is None:
            continue

        if re.search(r"валов", label_part, re.IGNORECASE):
            prio = 1
        elif re.search(r"расч[её]тн.*марж|итогов.*марж|^маржа", label_part, re.IGNORECASE) and not re.search(
            r"чист", label_part, re.IGNORECASE
        ):
            prio = 2
        elif re.search(r"чист", label_part, re.IGNORECASE):
            prio = 3
        else:
            prio = 4

        completeness = 0 if (rub_val is not None and pct_val is not None) else 1
        candidates.append((prio, completeness, rub_val, pct_val))

    if not candidates:
        return {
            "margin_rub": "",
            "margin_pct": "",
            "margin_rub_value": None,
            "margin_pct_value": None,
        }

    candidates.sort(key=lambda row: (row[0], row[1]))
    _, _, best_rub, best_pct = candidates[0]
    return {
        "margin_rub": _format_margin_rub(best_rub),
        "margin_pct": _format_margin_pct(best_pct),
        "margin_rub_value": best_rub,
        "margin_pct_value": best_pct,
    }


def _strip_markdown_inline(text: str) -> str:
    out = _MD_LINK_RE.sub(r"\1 (\2)", str(text or ""))
    out = re.sub(r"[*_`]+", "", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def extract_verdict_info(markdown: str) -> dict[str, Any]:
    """Extract the ИТОГОВЫЙ ВЕРДИКТ paragraph and detect whether it is already at the top."""
    text = str(markdown or "")
    if not text.strip():
        return {"verdict_text": "", "verdict_is_at_top": False}

    m = re.search(
        r"(?:^|\n)[ \t>*-]*\*{0,2}(?:ИТОГОВЫЙ ВЕРДИКТ|ВЕРДИКТ)\*{0,2}\s*:\*{0,2}\s*(.+?)(?=\n\s*\n|\n#{1,6}\s|\n\|)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return {"verdict_text": "", "verdict_is_at_top": False}

    verdict_body = _strip_markdown_inline(" ".join(line.strip() for line in m.group(1).splitlines() if line.strip()))
    # Consider verdict "at top" if it appears before the second top-level section or within the first 900 chars.
    pos = m.start()
    headings = list(re.finditer(r"(?m)^#{2,4}\s+\d+\.", text))
    second_section_pos = headings[1].start() if len(headings) >= 2 else 900
    is_at_top = pos < min(max(second_section_pos, 400), 1400)
    return {
        "verdict_text": verdict_body[:900],
        "verdict_is_at_top": is_at_top,
    }


def _split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    """Split markdown into (heading_text, body_text) pairs by ## / ### / #### headings."""
    text = str(markdown or "")
    matches = list(re.finditer(r"(?m)^(#{2,4})\s+(.+?)\s*$", text))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        heading = _strip_markdown_inline(match.group(2))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((heading, body))
    return sections


def _clean_section_to_plain_text(body: str) -> str:
    lines: list[str] = []
    for raw_line in str(body or "").splitlines():
        s = raw_line.strip()
        if not s or s in {"---", "***", "___"}:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if re.match(r"^```", s):
            continue
        if s.startswith("|") and s.endswith("|"):
            cells = [_strip_markdown_inline(c) for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells):
                continue
            if len(cells) >= 2 and cells[0] and cells[1]:
                if cells[0].lower() in {"показатель", "характеристика", "параметр", "характеристика / параметр из тз"}:
                    continue
                lines.append(f"• {cells[0]}: {cells[1]}")
            continue
        bullet_match = re.match(r"^[-*•]\s+(.+)$", s)
        if bullet_match:
            lines.append(f"• {_strip_markdown_inline(bullet_match.group(1))}")
            continue
        lines.append(_strip_markdown_inline(s))
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip()


def _extract_table_kv(section_body: str, key_patterns: tuple[str, ...]) -> str:
    for raw_line in str(section_body or "").splitlines():
        s = raw_line.strip()
        if not s:
            continue
        label = ""
        val = ""
        if "|" in s:
            parts = [_strip_markdown_inline(c) for c in s.strip("|").split("|")]
            if len(parts) >= 2:
                label, val = parts[0], parts[1]
        elif ":" in s:
            left, right = s.split(":", 1)
            label = _strip_markdown_inline(re.sub(r"^[-*•]\s*", "", left))
            val = _strip_markdown_inline(right)
        if not label or not val:
            continue
        if any(re.search(pat, label, re.IGNORECASE) for pat in key_patterns):
            return val
    return ""


def _extract_compliance_requirements(section_body: str) -> list[str]:
    rows: list[str] = []
    for raw_line in str(section_body or "").splitlines():
        s = raw_line.strip()
        if not (s.startswith("|") and "|" in s[1:]):
            continue
        cells = [_strip_markdown_inline(c) for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells):
            continue
        first_low = cells[0].lower()
        if any(
            hdr in first_low
            for hdr in ("характеристика", "параметр из тз", "наименование параметра", "№")
        ):
            continue
        param_name = cells[0].strip()
        req_val = cells[1].strip()
        if not param_name or not req_val or req_val in {"—", "-"}:
            continue
        rows.append(f"• {param_name}: {req_val}")
    return rows


def extract_copy_blocks(
    markdown: str,
    *,
    title: str = "",
    notice_number: str = "",
    nmck_raw: str = "",
    deadline_date: str = "",
) -> tuple[str, str]:
    """Return (copy_specs_text, copy_supplier_email_text) ready for 1-click plain-text copy."""
    text = str(markdown or "").strip()
    if not text:
        return "", ""

    sections = _split_markdown_sections(text)
    explicit_specs = ""
    explicit_email = ""

    for heading, body in sections:
        if not explicit_specs and re.search(
            r"ключевые\s+технические\s+характеристики|технические\s+характеристики\s+и\s+требования|характеристики.*для\s+копирования",
            heading,
            re.IGNORECASE,
        ):
            explicit_specs = _clean_section_to_plain_text(body)
        elif not explicit_email and re.search(
            r"готовое\s+письмо|письмо\s+производителю|письмо\s+поставщику|шаблон\s+письма|текст\s+письма",
            heading,
            re.IGNORECASE,
        ):
            explicit_email = _clean_section_to_plain_text(body)

    if explicit_specs and explicit_email:
        return explicit_specs, explicit_email

    # Synthesize clean plain-text fallbacks for legacy reports that do not yet have dedicated copy sections.
    summary_body = ""
    comparison_body = ""
    for heading, body in sections:
        if not summary_body and re.search(r"резюме|условия\s+закупки", heading, re.IGNORECASE):
            summary_body = body
        if not comparison_body and re.search(r"подбор\s+товара|таблица\s+соответствия|сравнительн", heading, re.IGNORECASE):
            comparison_body = body

    subject = _extract_table_kv(summary_body, (r"наименование\s+объекта", r"предмет\s+закупки")) or title
    essence = _extract_table_kv(summary_body, (r"суть\s+поставки",))
    delivery_place = _extract_table_kv(summary_body, (r"место\s+поставки",))
    delivery_term = _extract_table_kv(summary_body, (r"срок\s+поставки",))
    pitfalls = _extract_table_kv(summary_body, (r"подводные\s+камни", r"ключевые.*требования"))
    spec_rows = _extract_compliance_requirements(comparison_body)

    if not explicit_specs:
        spec_lines: list[str] = []
        if subject:
            spec_lines.append(f"Объект закупки: {subject}")
        if notice_number:
            spec_lines.append(f"Извещение №: {notice_number}")
        if essence:
            spec_lines.append(f"Суть поставки: {essence}")
        if spec_rows:
            spec_lines.append("")
            spec_lines.append("Ключевые технические характеристики и требования:")
            spec_lines.extend(spec_rows[:25])
        if delivery_place:
            spec_lines.append("")
            spec_lines.append(f"Место поставки: {delivery_place}")
        if delivery_term:
            spec_lines.append(f"Срок поставки: {delivery_term}")
        if pitfalls:
            spec_lines.append(f"Особые требования / риски: {pitfalls}")
        explicit_specs = "\n".join(spec_lines).strip()

    if not explicit_email:
        short_subject = (subject or title or f"закупка № {notice_number}").strip()
        if len(short_subject) > 120:
            short_subject = short_subject[:117].rstrip() + "..."
        email_lines: list[str] = [
            f"Тема: Запрос КП — {short_subject}",
            "",
            "Добрый день!",
            "",
            "Просим рассчитать оптовую стоимость и направить коммерческое предложение на поставку следующей продукции:",
            f"{subject or title}",
        ]
        if essence:
            email_lines.append("")
            email_lines.append(f"Описание и объём: {essence}")
        if spec_rows:
            email_lines.append("")
            email_lines.append("Требуемые характеристики:")
            email_lines.extend(spec_rows[:12])
        if delivery_place or delivery_term:
            email_lines.append("")
            if delivery_place:
                email_lines.append(f"Место доставки: {delivery_place}")
            if delivery_term:
                email_lines.append(f"Требуемый срок поставки: {delivery_term}")
        email_lines.extend(
            [
                "",
                "Просим указать в ответе:",
                "1. Актуальную оптовую цену (с НДС / без НДС) и возможную скидку на объём.",
                "2. Наличие на складе или срок изготовления и отгрузки.",
                "3. Соответствие указанным характеристикам, наличие паспорта/сертификатов и, если применимо, реестровой записи ГИСП (РРПП).",
                "",
                "Будем признательны за оперативный расчёт!",
            ]
        )
        explicit_email = "\n".join(email_lines).strip()

    return explicit_specs, explicit_email


def enrich_batch_result_item(
    item: dict[str, Any],
    *,
    spec_item: dict[str, Any] | None = None,
    job_title: str = "",
    spec_filename: str = "",
) -> dict[str, Any]:
    """Attach Kontur/EIS/ETP links, extracted margin, verdict, and 1-click copy texts."""
    enriched = dict(item)
    spec = spec_item if isinstance(spec_item, dict) else {}

    notice_num = str(enriched.get("notice_number") or spec.get("notice_number") or "").strip()
    eis_url = normalize_source_url(str(enriched.get("eis_url") or spec.get("eis_url") or "").strip())
    etp_url = normalize_source_url(str(enriched.get("etp_url") or spec.get("etp_url") or "").strip())
    kontur_url = clean_kontur_url(str(enriched.get("kontur_url") or spec.get("kontur_url") or "").strip())

    # Legacy fallback: Kontur.Zakupki exports of 11/19-digit EIS notices have deterministic URLs https://zakupki.kontur.ru/{notice_number}
    if not kontur_url and notice_num:
        digits = re.sub(r"\D+", "", notice_num)
        is_kontur_origin = (
            "kontur" in etp_url.lower()
            or "контур" in str(spec_filename or "").lower()
            or "контур" in str(job_title or "").lower()
            or "kontur" in str(spec_filename or "").lower()
            or "kontur" in str(job_title or "").lower()
        )
        if is_kontur_origin and digits == notice_num and len(digits) in {11, 19}:
            kontur_url = f"https://zakupki.kontur.ru/{digits}"

    enriched["kontur_url"] = kontur_url
    enriched["eis_url"] = eis_url
    enriched["etp_url"] = etp_url

    md = str(enriched.get("report_markdown") or "")
    if enriched.get("status") == "completed" and md.strip():
        if not enriched.get("margin_rub") and not enriched.get("margin_pct"):
            margin = extract_margin_from_markdown(md)
            enriched.update(margin)
        if not enriched.get("verdict_text"):
            verdict = extract_verdict_info(md)
            enriched.update(verdict)
        if not enriched.get("copy_specs_text") or not enriched.get("copy_supplier_email_text"):
            specs_txt, email_txt = extract_copy_blocks(
                md,
                title=str(enriched.get("title") or ""),
                notice_number=notice_num,
                nmck_raw=str(enriched.get("nmck_raw") or ""),
                deadline_date=str(enriched.get("deadline_date") or ""),
            )
            if not enriched.get("copy_specs_text"):
                enriched["copy_specs_text"] = specs_txt
            if not enriched.get("copy_supplier_email_text"):
                enriched["copy_supplier_email_text"] = email_txt

    return enriched
