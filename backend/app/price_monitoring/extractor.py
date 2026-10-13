from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..ai import call_llm, parse_json_object
from ..dadata_client import enrich_company_by_inn_or_query
from ..models import SystemSettings
from .cleaner import extract_package_hints, normalize_unit
from .models import SupplierQuote

logger = logging.getLogger(__name__)

# Сайты, которые не содержат коммерческих цен или являются соцсетями/видео
BLOCKED_DOMAINS = {
    "youtube.com", "vk.com", "ok.ru", "dzen.ru", "wikipedia.org", "gosuslugi.ru",
    "zakupki.gov.ru", "consultant.ru", "garant.ru", "nalog.gov.ru", "tass.ru", "ria.ru"
}


def is_valid_domain(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain not in BLOCKED_DOMAINS
    except Exception:
        return False


def _extract_inn_kpp_contacts(html: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Извлекает ИНН, КПП и базовые контакты из HTML регулярными выражениями."""
    inn: Optional[str] = None
    kpp: Optional[str] = None
    contacts_list: list[str] = []

    # ИНН (10 цифр для юрлиц, 12 для ИП)
    m_inn = re.findall(r'(?:ИНН|инн|taxid|inn)[\s:№#«"\'\xa0]{0,10}(\d{10}|\d{12})\b', html)
    if m_inn:
        inn = m_inn[0]

    # КПП (9 цифр)
    m_kpp = re.findall(r'(?:КПП|кпп)[\s:№#«"\'\xa0]{0,10}(\d{9})\b', html)
    if m_kpp:
        kpp = m_kpp[0]

    # Телефоны РФ
    phones = re.findall(r'(?:(?:\+7|8)[\s\-\(]{0,2}\d{3,4}[\s\-\)]{0,2}\d{2,3}[\s\-]?\d{2}[\s\-]?\d{2})', html)
    if phones:
        # фильтруем слишком короткие/длинные или явно мусорные
        valid_phones = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) in (11, 10)]
        if valid_phones:
            contacts_list.append(valid_phones[0])

    # Email
    emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', html)
    if emails:
        clean_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.webp', '.js', '.css'))]
        if clean_emails:
            contacts_list.append(clean_emails[0])

    contacts_str = ", ".join(contacts_list) if contacts_list else None
    return inn, kpp, contacts_str


async def fetch_page_content_and_meta(
    client: httpx.AsyncClient,
    url: str,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Скачивает страницу, извлекает текст, ИНН, КПП и контакты (включая подвал).
    Возвращает (текст_страницы, inn, kpp, contacts).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        resp = await client.get(url, headers=headers, timeout=8.0)
        if resp.status_code != 200 or not resp.text:
            return None, None, None, None

        raw_html = resp.text
        inn, kpp, contacts = _extract_inn_kpp_contacts(raw_html)

        soup = BeautifulSoup(raw_html, "html.parser")

        # Находим ссылку на страницу контактов/реквизитов, если ИНН не найден в теле страницы
        contacts_suburl: Optional[str] = None
        if not inn:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if re.search(r'(?:contacts|kontakty|rekvizit|requisites|about|o-kompanii)', href, re.I):
                    full_c_url = urljoin(url, href)
                    if urlparse(full_c_url).netloc == urlparse(url).netloc:
                        contacts_suburl = full_c_url
                        break

        # Извлекаем отдельно текст футера (реквизиты, телефоны)
        footer_text = ""
        footer_tag = soup.find("footer")
        if footer_tag:
            footer_text = " ".join(footer_tag.stripped_strings)

        # Удаляем скрипты и стили
        for tag in soup(["script", "style", "iframe", "noscript"]):
            tag.decompose()

        main_text = " ".join(soup.stripped_strings)

        # Объединяем основной текст и реквизиты подвала
        combined_text = main_text[:3500]
        if footer_text:
            combined_text += "\n\n[РЕКВИЗИТЫ И ПОДВАЛ САЙТА]:\n" + footer_text[:1000]

        # Если ИНН всё ещё нет, но есть ссылка на контакты, пробуем быстро подтянуть реквизиты
        if not inn and contacts_suburl:
            try:
                c_resp = await client.get(contacts_suburl, headers=headers, timeout=4.0)
                if c_resp.status_code == 200:
                    c_inn, c_kpp, c_contacts = _extract_inn_kpp_contacts(c_resp.text)
                    if c_inn:
                        inn = c_inn
                    if c_kpp and not kpp:
                        kpp = c_kpp
                    if c_contacts and not contacts:
                        contacts = c_contacts
            except Exception:
                pass

        return combined_text, inn, kpp, contacts
    except Exception:
        return None, None, None, None


async def fetch_page_content(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Обратная совместимость: возвращает только текст страницы."""
    text, _, _, _ = await fetch_page_content_and_meta(client, url)
    return text


def reconcile_quote_unit(
    quote: SupplierQuote,
    target_item_name: str,
    target_unit: str,
) -> SupplierQuote:
    """
    Приводит цену к единице измерения заказчика (КГ, М3, Т, УП, ШТ)
    и формирует прозрачный понятный комментарий.
    """
    norm_target = normalize_unit(target_unit)
    hints = extract_package_hints(target_item_name, target_unit)
    price = quote.raw_price_rub if quote.raw_price_rub > 0 else quote.price_rub
    site_u = normalize_unit(quote.site_unit or quote.unit or "")

    # 1. Газ в баллонах (Пропан, Кислород, Азот, Аргон, Углекислота)
    gas_type = hints.get("gas_type")
    cyl_vol = hints.get("cylinder_volume_l")

    # ПРОПАН: при запросе в КГ (баллон 50л содержит ~21 кг газа)
    if gas_type == "propane" or "пропан" in target_item_name.lower():
        if norm_target in ("кг", "к-г"):
            # Если цена указана за баллон 50л целиком (обычно 1800 - 3500 руб), а нужна за кг (~80-130 руб)
            if price > 400 or "баллон" in (quote.site_unit or "").lower() or (cyl_vol == 50):
                converted_p = round(price / 21.0, 2)
                quote.price_rub = converted_p
                quote.unit = norm_target
                quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за баллон 50л (21 кг газа). Пересчитано в кг: {converted_p:,.2f} ₽/кг"
                return quote

    # КИСЛОРОД, АЗОТ, АРГОН: при запросе в М3 (баллон 40л содержит ~6.3 м³ газа при 150 атм)
    if gas_type in ("oxygen", "nitrogen", "argon") or any(g in target_item_name.lower() for g in ("кислород", "азот", "аргон")):
        if norm_target in ("м3", "куб"):
            # Если цена указана за баллон целиком (обычно 700 - 3500 руб), а нужна за м³
            if price > 250 or "баллон" in (quote.site_unit or "").lower() or (cyl_vol == 40):
                converted_p = round(price / 6.3, 2)
                quote.price_rub = converted_p
                quote.unit = norm_target
                gas_label = "кислорода" if "кислород" in target_item_name.lower() else ("азота" if "азот" in target_item_name.lower() else "аргона")
                quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за баллон 40л (6.3 м³ {gas_label}). Пересчитано в м³: {converted_p:,.2f} ₽/м³"
                return quote

    # УГЛЕКИСЛОТА: при запросе в КГ (баллон 40л содержит ~24 кг углекислоты)
    if gas_type == "co2" or "углекислот" in target_item_name.lower():
        if norm_target in ("кг", "к-г"):
            if price > 300 or "баллон" in (quote.site_unit or "").lower() or (cyl_vol == 40):
                converted_p = round(price / 24.0, 2)
                quote.price_rub = converted_p
                quote.unit = norm_target
                quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за баллон 40л (24 кг углекислоты). Пересчитано в кг: {converted_p:,.2f} ₽/кг"
                return quote

    # 2. МЕТАЛЛОПРОКАТ / ВЕС: Тонна <-> Килограмм
    if norm_target in ("т", "тонна"):
        if site_u in ("кг", "килограмм") and price < 5000:
            converted_p = round(price * 1000.0, 2)
            quote.price_rub = converted_p
            quote.unit = norm_target
            quote.conversion_comment = f"На сайте: {price:,.2f} ₽/кг. Пересчитано в тонны: {converted_p:,.0f} ₽/т"
            return quote
    elif norm_target in ("кг", "килограмм"):
        if (site_u in ("т", "тонна") or price > 20000) and any(kw in target_item_name.lower() for kw in ("лист", "полоса", "круг", "труба", "арматура", "сталь", "уголок")):
            converted_p = round(price / 1000.0, 2)
            quote.price_rub = converted_p
            quote.unit = norm_target
            quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за тонну. Пересчитано в кг: {converted_p:,.2f} ₽/кг"
            return quote

    # 3. ЭЛЕКТРОДЫ СВАРОЧНЫЕ (часто фасовка 5 кг или 5.5 кг)
    if "электрод" in target_item_name.lower() and norm_target == "кг":
        pack_kg = hints.get("pack_weight_kg")
        if not pack_kg:
            m_wt = re.search(r'(\d+(?:[.,]\d+)?)\s*кг', (quote.site_unit or "").lower())
            if m_wt:
                pack_kg = float(m_wt.group(1).replace(",", "."))
            else:
                pack_kg = 5.0
        if price > 500 and ("пач" in (quote.site_unit or "").lower() or "уп" in (quote.site_unit or "").lower() or price > 600):
            converted_p = round(price / pack_kg, 2)
            quote.price_rub = converted_p
            quote.unit = norm_target
            quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за пачку ({pack_kg} кг). Пересчитано в кг: {converted_p:,.2f} ₽/кг"
            return quote

    # 4. ШТУКИ И УПАКОВКИ: УП <-> ШТ
    pack_pcs = hints.get("pack_pieces")
    if not pack_pcs:
        m_pcs = re.search(r'(\d+)\s*(?:шт|штук)\b', (quote.site_unit or "").lower())
        if m_pcs:
            pack_pcs = int(m_pcs.group(1))

    if pack_pcs and pack_pcs > 1:
        if norm_target == "шт" and ("уп" in site_u or "пач" in site_u or price > 100):
            converted_p = round(price / pack_pcs, 2)
            quote.price_rub = converted_p
            quote.unit = norm_target
            quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за уп ({pack_pcs} шт). Пересчитано в шт: {converted_p:,.2f} ₽/шт"
            return quote
        elif norm_target in ("уп", "пач") and ("шт" in site_u or price < 50):
            converted_p = round(price * pack_pcs, 2)
            quote.price_rub = converted_p
            quote.unit = norm_target
            quote.conversion_comment = f"На сайте: {price:,.2f} ₽/шт. Пересчитано в уп ({pack_pcs} шт): {converted_p:,.2f} ₽/уп"
            return quote

    # Единица совпала или стандартная
    quote.price_rub = price
    quote.unit = norm_target
    if not quote.conversion_comment:
        if quote.site_unit and quote.site_unit != norm_target:
            quote.conversion_comment = f"Цена на сайте указана за {quote.site_unit}"
        else:
            quote.conversion_comment = f"Цена за 1 {norm_target}"

    return quote


async def extract_supplier_quote(
    settings: SystemSettings,
    target_item_name: str,
    target_unit: str,
    url: str,
    page_text: str,
    pre_inn: Optional[str] = None,
    pre_kpp: Optional[str] = None,
    pre_contacts: Optional[str] = None,
) -> Optional[SupplierQuote]:
    """Анализирует текст страницы и извлекает цену, название поставщика, ИНН, КПП и контакты."""
    domain = urlparse(url).netloc
    norm_unit = normalize_unit(target_unit)

    prompt = f'''Ты ведущий эксперт по закупкам и коммерческому анализу цен. Твоя задача — внимательно изучить страницу поставщика и извлечь актуальную цену с точной привязкой к единицам измерения.

Искомый товар: "{target_item_name}"
Требуемая единица измерения заказчика: "{norm_unit}"
URL страницы: {url}
Предварительно обнаруженные данные с сайта:
- ИНН: {pre_inn or "не обнаружен"}
- КПП: {pre_kpp or "не обнаружен"}
- Контакты: {pre_contacts or "не обнаружены"}

Текст страницы товара и реквизитов:
{page_text}

КРИТИЧЕСКИЕ ПРАВИЛА:
1. РЕЛЕВАНТНОСТЬ:
   - Проверь, что на странице продается именно этот товар (или точная марка/ГОСТ).
   - Если товар другой (лекарство, косметика, новостная статья, общая услуга) — ответь is_price_found: false.
2. ЦЕНА НА САЙТЕ (raw_price_rub) И ЕДИНИЦА (site_unit):
   - Найди реальную цену в рублях.
   - Определи, за какую ИМЕННО единицу/фасовку она указана на сайте (например: "за баллон 50л", "за баллон 40л", "за 1 тонну", "за 1 кг", "за упаковку 100 шт", "за 1 шт").
   - Если цена "по запросу", "уточняйте", 0 или "нет в наличии" — ответь is_price_found: false.
3. ПЕРЕСЧЕТ В ЕДИНИЦУ ЗАКАЗЧИКА:
   - Если единица совпадает с "{norm_unit}", price_rub = raw_price_rub.
   - Если отличается (например, пропан 50л по 2400 руб за баллон, а заказчик просит "кг"): баллон 50л содержит 21 кг газа, значит 2400 / 21 = 114.29 руб/кг.
   - Если кислород по 900 руб за баллон 40л, а заказчик просит "м3": баллон содержит 6.3 м³ газа, значит 900 / 6.3 = 142.86 руб/м³.
   - Если металлопрокат за тонну (60 000 руб), а заказчик просит "кг": 60 000 / 1000 = 60 руб/кг.
4. РЕКВИЗИТЫ ПОСТАВЩИКА:
   - company_name: Официальное название (например, ООО "Металлсервис", ForOffice, Завод Уралтехгаз).
   - inn: ИНН организации (10 цифр для юрлиц, 12 для ИП). Если найден в тексте или предварительно — укажи обязательно!
   - kpp: КПП организации (9 цифр), если есть.
   - contacts: Телефон(ы), email, город поставщика.

Ответь СТРОГО JSON-объектом:
{{
  "is_relevant": true,
  "is_price_found": true,
  "company_name": "ООО Название",
  "inn": "{pre_inn or ''}",
  "kpp": "{pre_kpp or ''}",
  "contacts": "{pre_contacts or ''}",
  "raw_price_rub": 2400.0,
  "site_unit": "баллон 50л",
  "price_rub": 114.29,
  "unit": "{norm_unit}",
  "conversion_comment": "На сайте: 2400 ₽ за баллон 50л (21 кг газа). Пересчитано в кг: 114.29 ₽/кг"
}}
'''
    try:
        raw_response = await call_llm(settings, prompt, tier="light")
        parsed = parse_json_object(raw_response)
        if not parsed or not isinstance(parsed, dict):
            return None

        if not parsed.get("is_relevant") or not parsed.get("is_price_found"):
            return None

        # Исходная цена
        raw_p = parsed.get("raw_price_rub") or parsed.get("price_rub")
        if raw_p is None:
            return None
        raw_price_val = float(raw_p)
        if raw_price_val <= 0 or raw_price_val > 500_000_000:
            return None

        # Итоговая цена (с учетом возможного пересчета LLM)
        p_val = parsed.get("price_rub")
        final_price_val = float(p_val) if p_val is not None else raw_price_val

        # Реквизиты
        comp_name = str(parsed.get("company_name") or "").strip() or domain
        inn = str(parsed.get("inn") or pre_inn or "").strip() or None
        if inn:
            inn = re.sub(r'\D', '', inn)
            if len(inn) not in (10, 12):
                inn = None

        kpp = str(parsed.get("kpp") or pre_kpp or "").strip() or None
        if kpp:
            kpp = re.sub(r'\D', '', kpp)
            if len(kpp) != 9:
                kpp = None

        contacts = str(parsed.get("contacts") or pre_contacts or "").strip() or None
        site_unit = str(parsed.get("site_unit") or "").strip()
        conv_comment = str(parsed.get("conversion_comment") or "").strip()

        quote = SupplierQuote(
            company_name=comp_name,
            inn=inn,
            kpp=kpp,
            contacts=contacts,
            price_rub=round(final_price_val, 2),
            raw_price_rub=round(raw_price_val, 2),
            unit=norm_unit,
            site_unit=site_unit,
            url=url,
            is_price_found=True,
            conversion_comment=conv_comment,
            comment="",
        )

        # Обогащение реквизитами через DaData (ИНН, КПП, официальное наименование, статус)
        try:
            detected_city = None
            if contacts:
                city_match = re.search(r'(?:г\.|город)\s*([А-Яа-я\-]{3,25})', contacts)
                if city_match:
                    detected_city = city_match.group(1)

            dadata_info = await enrich_company_by_inn_or_query(
                inn=quote.inn,
                query=quote.company_name,
                domain=domain,
                city=detected_city,
            )
            if dadata_info:
                if not quote.inn and dadata_info.get("inn"):
                    quote.inn = dadata_info["inn"]
                if not quote.kpp and dadata_info.get("kpp"):
                    quote.kpp = dadata_info["kpp"]
                official_name = dadata_info.get("company_name")
                if official_name:
                    quote.company_name = official_name
                city_or_addr = dadata_info.get("city") or dadata_info.get("legal_address")
                if city_or_addr and (not quote.contacts or city_or_addr not in quote.contacts):
                    quote.contacts = f"{quote.contacts}, {city_or_addr}".strip(", ") if quote.contacts else city_or_addr

            # Гарантируем форму собственности (ООО/АО/ИП), если поставщик корпоративный
            if not quote.company_name.startswith(("ООО", "АО", "ЗАО", "ПАО", "ИП", "Общество", "Акционерное")):
                clean_c = quote.company_name.strip(" '\"")
                if clean_c != domain and "." not in clean_c:
                    quote.company_name = f'ООО "{clean_c}"'
        except Exception as d_exc:
            logger.debug("DaData enrichment skipped for %s: %s", quote.company_name, d_exc)

        # Применяем детерминированную проверку и до-пересчет единиц
        return reconcile_quote_unit(quote, target_item_name, target_unit)
    except Exception as exc:
        logger.debug("Quote extraction failed for %s: %s", url, exc)
        return None
