from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..ai import call_llm, parse_json_object
from ..dadata_client import enrich_company_by_inn_or_query
from ..models import SystemSettings
from .cleaner import extract_package_hints, is_closed_factory_drawing, normalize_unit
from .cookie_manager import cookie_manager
from .models import SupplierQuote

logger = logging.getLogger(__name__)

# Сайты, которые не содержат коммерческих цен или являются соцсетями/видео/справочниками
BLOCKED_DOMAINS = {
    "youtube.com", "vk.com", "ok.ru", "dzen.ru", "wikipedia.org", "gosuslugi.ru",
    "zakupki.gov.ru", "consultant.ru", "garant.ru", "nalog.gov.ru", "tass.ru", "ria.ru",
    "zen.yandex.ru", "vc.ru", "drive2.ru", "pikabu.ru", "otzovik.com", "irecommend.ru",
    "habr.com", "tbank.ru", "sberbank.ru", "hh.ru", "superjob.ru", "rabota.ru", "audit-it.ru",
    "klerk.ru", "cbr.ru", "rbc.ru", "kommersant.ru", "lenta.ru", "gazeta.ru"
}


# Маркетплейсы потребительских товаров и доски объявлений
MARKETPLACE_DOMAINS = {
    "ozon.ru", "wildberries.ru", "market.yandex.ru", "megamarket.ru",
    "aliexpress.ru", "aliexpress.com", "avito.ru", "taobao.com", "1688.com",
    "temu.com", "ebay.com", "amazon.com", "lamoda.ru", "sbermegamarket.ru",
    "youla.ru", "farpost.ru", "drom.ru", "irr.ru", "doski.ru", "flagma.ru"
}

# Сайты-посредники зарубежного выкупа / мейлфорвардеры
CROSSBORDER_FORWARDERS = {
    "shopozz.ru", "cdek.shopping", "usmall.ru", "banderolka.com", "pochtaglobal.ru", "china.org.ru"
}

# Разрешенные региональные зоны для поиска поставщиков РФ
ALLOWED_DOMESTIC_TLDS = {".ru", ".рф", ".su", ".by", ".kz"}

# Общеупотребительные бизнес-зоны gTLD, часто используемые российскими дистрибьюторами и производителями
GENERIC_BUSINESS_TLDS = {
    ".com", ".net", ".org", ".biz", ".info", ".pro", ".tools", ".one",
    ".online", ".shop", ".store", ".tech", ".group", ".market", ".center",
    ".moscow", ".city", ".club", ".space", ".site", ".co", ".me", ".top"
}

# Исключительно зарубежные национальные домены верхнего уровня (ccTLD)
FOREIGN_NATIONAL_CCTLDS = {
    ".ua", ".de", ".cn", ".us", ".uk", ".pl", ".fr", ".it", ".es", ".jp",
    ".kr", ".in", ".tr", ".cz", ".nl", ".se", ".fi", ".ro", ".bg", ".hu",
    ".gr", ".at", ".ch", ".ca", ".au", ".br", ".mx", ".ar", ".vn", ".th"
}

LISTING_PATH_PATTERNS = [
    re.compile(r'/tag[-_]page/', re.I),
    re.compile(r'/tags?/', re.I),
    re.compile(r'/tag[-_][a-z0-9_-]+(?:/|$)', re.I),
    re.compile(r'/popular/', re.I),
    re.compile(r'/search(?:/|\?|$)', re.I),
    re.compile(r'/collections?/', re.I),
    re.compile(r'/find(?:/|\?|$)', re.I),
    re.compile(r'/filter/', re.I),
    re.compile(r'^/catalog/?$', re.I),
    re.compile(r'^/catalog/all/?$', re.I),
    re.compile(r'/category/(?:[a-z0-9_-]+/)*$', re.I),
]


def is_listing_url(url: str) -> bool:
    """Определяет страницы-каталоги, списки тегов и результаты внутреннего поиска без конкретной карточки."""
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        for pat in LISTING_PATH_PATTERNS:
            if pat.search(path):
                return True
        query = parsed.query.lower()
        if any(param in query for param in ("sort=", "filter=", "page=", "search=")):
            return True
        return False
    except Exception:
        return False


def is_foreign_source(url: str, text: str = "") -> bool:
    """Определяет иностранные сайты, зарубежные TLD и сервисы трансграничного выкупа."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # Проверка посредников зарубежного выкупа
        for fwd in CROSSBORDER_FORWARDERS:
            if domain == fwd or domain.endswith("." + fwd):
                return True

        # Проверка TLD
        parts = domain.split(".")
        if len(parts) >= 2:
            tld = "." + parts[-1]
            # Явные зарубежные национальные зоны
            if tld in FOREIGN_NATIONAL_CCTLDS:
                return True
            # Специальные gTLD, активно используемые российскими дистрибьюторами и интернет-магазинами
            if tld in {".tools", ".pro", ".one", ".online", ".shop", ".store", ".market", ".moscow", ".tech", ".group"}:
                # Разрешаем предварительный парсинг для проверки языка контента
                if text and len(text) > 80:
                    cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', text))
                    latin = len(re.findall(r'[a-zA-Z]', text))
                    total = cyrillic + latin
                    if total > 40 and (cyrillic / total) < 0.20:
                        return True
                return False

            # Обычные зарубежные зоны (.com, .net, .org, .cc и прочие) без подтвержденного русскоязычного текста
            if tld not in ALLOWED_DOMESTIC_TLDS and not domain.endswith(".xn--p1ai"):
                return True

        # Проверка языка контента, если передан текст
        if text and len(text) > 80:
            cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', text))
            latin = len(re.findall(r'[a-zA-Z]', text))
            total = cyrillic + latin
            if total > 40 and (cyrillic / total) < 0.20:
                return True

        return False
    except Exception:
        return False


def is_valid_domain(
    url: str,
    target_item_name: str = "",
    filter_marketplaces: bool = True,
    filter_foreign: bool = True,
) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # Проверка глобальных стоп-доменов
        for bd in BLOCKED_DOMAINS:
            if domain == bd or domain.endswith("." + bd):
                return False

        # Фильтрация маркетплейсов
        if filter_marketplaces:
            for md in MARKETPLACE_DOMAINS:
                if domain == md or domain.endswith("." + md):
                    return False

        # Фильтрация зарубежных источников
        if filter_foreign and is_foreign_source(url):
            return False

        # Отсекаем явные страницы списков и тегов
        if is_listing_url(url):
            return False

        return True
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


DISCONTINUED_PATTERN = re.compile(
    r'\b(?:товар\s+снят\s+с\s+производства|снят(?:о|а)?\s+с\s+производства|'
    r'архивный\s+товар|товар\s+в\s+архиве|снят\s+с\s+продажи|'
    r'не\s+поставляется|снято\s+с\s+продажи|товар\s+недоступен\s+для\s+заказа)\b',
    re.IGNORECASE,
)


def extract_schema_org_product_data(soup: BeautifulSoup) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Извлекает структурированные данные Schema.org (Product, Offer) и проверяет статус наличия/архива (Правило 14).
    Возвращает (product_info_dict, is_discontinued_or_out_of_stock).
    """
    is_discontinued = False
    best_product: Optional[Dict[str, Any]] = None

    def _inspect_offer(offer_dict: dict) -> Tuple[Optional[float], Optional[str], Optional[str], bool]:
        price_val = None
        raw_price = offer_dict.get("price") or offer_dict.get("lowPrice")
        if raw_price is not None:
            try:
                c_pr = str(raw_price).replace(" ", "").replace(",", ".")
                price_val = float(c_pr)
            except Exception:
                price_val = None
        curr = offer_dict.get("priceCurrency")
        avail = str(offer_dict.get("availability") or "").lower()
        is_oos = any(bad in avail for bad in ("outofstock", "discontinued", "soldout"))
        return price_val, curr, avail, is_oos

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except Exception:
            continue

        items_to_check: List[Any] = []
        if isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items_to_check.extend(data["@graph"])
            else:
                items_to_check.append(data)
        elif isinstance(data, list):
            items_to_check.extend(data)

        for item in items_to_check:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("@type") or "")
            if "Product" in item_type or item.get("offers"):
                name = item.get("name")
                sku = item.get("sku") or item.get("mpn") or item.get("productID")
                offers = item.get("offers")
                p_val, p_curr, p_avail, p_oos = None, None, None, False
                if isinstance(offers, dict):
                    p_val, p_curr, p_avail, p_oos = _inspect_offer(offers)
                elif isinstance(offers, list) and offers:
                    for off in offers:
                        if isinstance(off, dict):
                            pv, pc, pa, po = _inspect_offer(off)
                            if pv and pv > 0:
                                p_val, p_curr, p_avail, p_oos = pv, pc, pa, po
                                break
                if p_oos:
                    is_discontinued = True

                if (name or p_val) and not best_product:
                    best_product = {
                        "name": name,
                        "sku": sku,
                        "price": p_val,
                        "currency": p_curr or "RUB",
                        "availability": p_avail,
                        "is_out_of_stock": p_oos,
                    }

    # Также проверяем мета-теги наличия
    for meta in soup.find_all("meta"):
        prop = (meta.get("property") or meta.get("name") or "").lower()
        content = (meta.get("content") or "").lower()
        if "availability" in prop and any(bad in content for bad in ("discontinued", "снят")):
            is_discontinued = True

    return best_product, is_discontinued


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
    custom_cookie = cookie_manager.get_cookie_for_url(url)
    if custom_cookie:
        headers["Cookie"] = custom_cookie
    try:
        resp = await client.get(url, headers=headers, timeout=httpx.Timeout(7.0, connect=2.5))
        if resp.status_code != 200 or not resp.text:
            return None, None, None, None

        raw_html = resp.text
        inn, kpp, contacts = _extract_inn_kpp_contacts(raw_html)

        soup = BeautifulSoup(raw_html, "html.parser")

        # 0. Извлекаем структурированные данные Schema.org и проверяем наличие до удаления скриптов
        product_info, is_oos = extract_schema_org_product_data(soup)
        schema_block = ""
        if product_info:
            schema_block = "[СТРУКТУРИРОВАННЫЕ ДАННЫЕ ТОВАРА (SCHEMA.ORG JSON-LD)]:\n"
            if product_info.get("name"):
                schema_block += f"- Товар: {product_info['name']}\n"
            if product_info.get("sku"):
                schema_block += f"- Артикул/Чертеж (SKU): {product_info['sku']}\n"
            if product_info.get("price"):
                schema_block += f"- Цена: {product_info['price']} {product_info.get('currency', 'RUB')}\n"
            avail_str = str(product_info.get("availability") or "").lower()
            if "discontinued" in avail_str or "архив" in avail_str:
                schema_block += "- Статус наличия: СНЯТ С ПРОИЗВОДСТВА (АРХИВ)\n"
            elif is_oos:
                schema_block += "- Статус наличия: НЕТ В НАЛИЧИИ НА СКЛАДЕ (ПОД ЗАКАЗ)\n"
            elif product_info.get("availability"):
                schema_block += f"- Наличие: {product_info['availability']}\n"
            schema_block += "\n"
        elif is_oos:
            schema_block = "[ВНИМАНИЕ]: СТАТУС НАЛИЧИЯ: НЕТ В НАЛИЧИИ НА СКЛАДЕ (ПОД ЗАКАЗ)\n\n"

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

        # Объединяем структурированные данные Schema.org, основной текст и реквизиты подвала
        combined_text = (schema_block + main_text)[:3500] if schema_block else main_text[:3500]
        if footer_text:
            combined_text += "\n\n[РЕКВИЗИТЫ И ПОДВАЛ САЙТА]:\n" + footer_text[:1000]

        # Если ИНН всё ещё нет, но есть ссылка на контакты, пробуем быстро подтянуть реквизиты
        if not inn and contacts_suburl:
            try:
                c_resp = await client.get(contacts_suburl, headers=headers, timeout=httpx.Timeout(3.0, connect=1.5))
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


def compute_deterministic_normalized_price(
    raw_price: float,
    site_unit: str,
    target_unit: str,
    pack_quantity: Optional[float] = None,
    pack_base_unit: Optional[str] = None,
    is_price_for_whole_pack: bool = False,
    existing_comment: str = "",
) -> Tuple[float, str, Optional[str]]:
    """
    Детерминированный математический движок пересчета цен по правилам размерного анализа (Правило 14).
    Возвращает (normalized_price, target_unit, conversion_comment).
    100% универсален для любых ТМЦ без жестко зашитых товарных категорий.
    """
    if raw_price <= 0:
        return 0.0, target_unit, None

    norm_target = normalize_unit(target_unit)
    norm_site = normalize_unit(site_unit)

    # 1. Единицы полностью совпадают
    if norm_target == norm_site or (norm_target in ("шт", "штука") and norm_site in ("шт", "штука")):
        return round(raw_price + 1e-9, 2), norm_target, None

    # 2. Метрические размерные преобразования (Вес, Объем, Длина, Площадь)
    # ВЕС:
    if norm_site in ("кг", "килограмм") and norm_target in ("т", "тонна"):
        p = round((raw_price * 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.2f} ₽/кг. Пересчитано в тонны (x1000): {p:,.0f} ₽/т"
    if (norm_site in ("т", "тонна") or (not norm_site and raw_price > 20000)) and norm_target in ("кг", "килограмм"):
        p = round((raw_price / 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.0f} ₽/т. Пересчитано в кг (/1000): {p:,.2f} ₽/кг"
    if norm_site in ("г", "грамм") and norm_target in ("кг", "килограмм"):
        p = round((raw_price * 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.2f} ₽/г. Пересчитано в кг (x1000): {p:,.2f} ₽/кг"
    if norm_site in ("кг", "килограмм") and norm_target in ("г", "грамм"):
        p = round((raw_price / 1000.0) + 1e-9, 4)
        return p, norm_target, f"На сайте: {raw_price:,.2f} ₽/кг. Пересчитано в г (/1000): {p:,.4f} ₽/г"

    # ОБЪЕМ:
    if norm_site in ("л", "литр") and norm_target in ("м3", "куб", "кубометр"):
        p = round((raw_price * 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.2f} ₽/л. Пересчитано в м³ (x1000): {p:,.0f} ₽/м³"
    if norm_site in ("м3", "куб", "кубометр") and norm_target in ("л", "литр"):
        p = round((raw_price / 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.0f} ₽/м³. Пересчитано в л (/1000): {p:,.2f} ₽/л"

    # ДЛИНА:
    if norm_site in ("м", "метр") and norm_target in ("км", "километр"):
        p = round((raw_price * 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.2f} ₽/м. Пересчитано в км (x1000): {p:,.0f} ₽/км"
    if norm_site in ("км", "километр") and norm_target in ("м", "метр"):
        p = round((raw_price / 1000.0) + 1e-9, 2)
        return p, norm_target, f"На сайте: {raw_price:,.0f} ₽/км. Пересчитано в м (/1000): {p:,.2f} ₽/м"

    # 3. Фасовка, упаковки, тара (бочки, канистры, мешки, коробки, пачки, рулоны, бухты)
    # Авто-извлечение количества из строки site_unit, если не было передано в pack_quantity
    qty = pack_quantity
    base_u = normalize_unit(pack_base_unit or "")
    if not qty or qty <= 0:
        m_q = re.search(r'(\d+(?:[.,]\d+)?)\s*(кг|т|л|мл|м3|м|см|мм|шт|пар)\b', site_unit.lower())
        if m_q:
            try:
                qty = float(m_q.group(1).replace(",", "."))
                base_u = normalize_unit(m_q.group(2))
                is_price_for_whole_pack = True
            except Exception:
                pass
        if not qty or qty <= 0:
            m_pcs = re.search(r'(\d+)\s*(?:шт|штук)\b', site_unit.lower())
            if m_pcs:
                try:
                    qty = float(m_pcs.group(1))
                    base_u = "шт"
                    is_price_for_whole_pack = True
                except Exception:
                    pass

    pack_keywords = ("уп", "пач", "кор", "мешок", "бочк", "канистр", "рулон", "бухт", "ведр", "банк", "компл")
    is_pack_unit = any(k in site_unit.lower() for k in pack_keywords)
    is_cylinder = "баллон" in site_unit.lower()

    if not is_cylinder and qty and qty > 0 and (is_price_for_whole_pack or is_pack_unit):
        # Случай А: На сайте цена за тару/упаковку Q базовых единиц, а требуется базовая единица (или кратная ей)
        if norm_target == (base_u or norm_target):
            p = round((raw_price / qty) + 1e-9, 2)
            lbl = site_unit if site_unit else "упаковку/тару"
            return p, norm_target, f"На сайте: {raw_price:,.2f} ₽ за {lbl} ({qty} {norm_target}). Пересчитано за 1 {norm_target}: {p:,.2f} ₽/{norm_target}"

        # Случай Б: Тара в кг (например, мешок 50 кг), а заказчику нужны тонны (т)
        if base_u in ("кг", "килограмм") and norm_target in ("т", "тонна"):
            p = round(((raw_price / qty) * 1000.0) + 1e-9, 2)
            return p, norm_target, f"На сайте: {raw_price:,.2f} ₽ за тару ({qty} кг). Пересчитано в тонны (x1000/{qty}): {p:,.0f} ₽/т"

        # Случай В: Тара в литрах (например, бочка 200 л), а заказчику нужны кубометры (м³)
        if base_u in ("л", "литр") and norm_target in ("м3", "куб", "кубометр"):
            p = round(((raw_price / qty) * 1000.0) + 1e-9, 2)
            return p, norm_target, f"На сайте: {raw_price:,.2f} ₽ за тару ({qty} л). Пересчитано в м³ (x1000/{qty}): {p:,.0f} ₽/м³"

    # Случай Г: Заказчик просит упаковку из Q штук/кг, а на сайте цена за 1 штуку/кг
    if not is_cylinder and qty and qty > 1 and is_pack_unit and not is_price_for_whole_pack:
        if norm_site == (base_u or "шт"):
            p = round((raw_price * qty) + 1e-9, 2)
            return p, norm_target, f"На сайте: {raw_price:,.2f} ₽/{norm_site}. Пересчитано за упаковку ({qty} {norm_site}): {p:,.2f} ₽/{norm_target}"

    # Если детерминированный пересчет не потребовался, возвращаем исходную цену
    return round(raw_price + 1e-9, 2), norm_target, (existing_comment or None)


def reconcile_quote_unit(
    quote: SupplierQuote,
    target_item_name: str,
    target_unit: str,
) -> SupplierQuote:
    """
    Приводит цену к единице измерения заказчика (Правило 14: приоритет универсального размерного анализа).
    """
    norm_target = normalize_unit(target_unit)
    price = quote.raw_price_rub if quote.raw_price_rub > 0 else quote.price_rub
    site_u = quote.site_unit or quote.unit or ""

    # 1. Газ в баллонах (Пропан, Кислород, Азот, Аргон, Углекислота по физике ГОСТ 949-73)
    hints = extract_package_hints(target_item_name, target_unit)
    gas_type = hints.get("gas_type")
    cyl_vol = hints.get("cylinder_volume_l")

    # ПРОПАН: при запросе в КГ (баллон 50л содержит ~21 кг газа)
    if gas_type == "propane" or "пропан" in target_item_name.lower():
        if norm_target in ("кг", "к-г"):
            if price > 400 or "баллон" in (quote.site_unit or "").lower() or (cyl_vol == 50):
                converted_p = round(price / 21.0, 2)
                quote.price_rub = converted_p
                quote.unit = norm_target
                quote.conversion_comment = f"На сайте: {price:,.0f} ₽ за баллон 50л (21 кг газа). Пересчитано в кг: {converted_p:,.2f} ₽/кг"
                return quote

    # КИСЛОРОД, АЗОТ, АРГОН: при запросе в М3 (баллон 40л содержит ~6.3 м³ газа при 150 атм)
    if gas_type in ("oxygen", "nitrogen", "argon") or any(g in target_item_name.lower() for g in ("кислород", "азот", "аргон")):
        if norm_target in ("м3", "куб"):
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

    # 2. Детерминированный математический расчет для всех остальных ТМЦ
    calc_price, calc_unit, calc_comment = compute_deterministic_normalized_price(
        raw_price=price,
        site_unit=site_u,
        target_unit=norm_target,
        existing_comment=quote.conversion_comment,
    )
    if calc_comment and calc_price > 0:
        quote.price_rub = calc_price
        quote.unit = norm_target
        quote.conversion_comment = calc_comment
        return quote

    # Если ИИ уже успешно выполнил семантический пересчет в требуемую единицу (Правило 14):
    if quote.unit == norm_target and quote.conversion_comment and quote.price_rub > 0:
        is_suspicious_ton = norm_target in ("т", "тонна") and quote.price_rub < 3000
        is_suspicious_m3 = norm_target in ("м3", "куб") and quote.price_rub < 1500
        if not is_suspicious_ton and not is_suspicious_m3:
            return quote

    # 2. Штуки и упаковки
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


# Быстрый фильтр наличия ценовых сигналов на странице перед вызовом дорогостоящей LLM
PRICE_SIGNAL_PATTERN = re.compile(
    r'(?:'
    r'\d+[\s\xa0]*(?:[.,]\d{1,2})?[\s\xa0]*(?:₽|руб\.?|рублей|rur|rub)\b|'
    r'(?:цена|стоимость|прайс|от)[\s:№#«"\'\xa0]{1,10}\d+[\s\xa0]*(?:[.,]\d{1,2})?|'
    r'\b(?:купить|в\s+корзину|заказать|в\s+наличии|прайс-лист|розница|опт)\b'
    r')',
    re.IGNORECASE,
)


def has_price_signals(text: str) -> bool:
    """Быстрая детерминированная проверка наличия признаков цен без вызова LLM."""
    if not text or len(text) < 20:
        return False
    return bool(PRICE_SIGNAL_PATTERN.search(text))


def is_price_grounded_in_text(raw_price: float, text: str) -> bool:
    """Проверяет, что извлеченная цена физически присутствует в тексте страницы (защита от галлюцинаций LLM)."""
    if raw_price <= 0:
        return False
    int_p = int(round(raw_price))
    if int_p <= 0:
        return False
    str_int = str(int_p)
    if str_int in text:
        return True
    if len(str_int) > 3:
        # Проверка с разделителями тысяч (пробел, неразрывный пробел, точка)
        parts = []
        rem = len(str_int) % 3
        if rem:
            parts.append(str_int[:rem])
        for i in range(rem, len(str_int), 3):
            parts.append(str_int[i : i + 3])
        spaced = r'[\s\xa0.,]'.join(parts)
        if re.search(spaced, text):
            return True
    # Проверка исходного числа с плавающей точкой
    str_float = f"{raw_price:.2f}".replace(".", ",")
    if str_float in text or f"{raw_price:.2f}" in text:
        return True
    return False


HOMOGLYPHS = str.maketrans({
    "a": "а", "c": "с", "e": "е", "k": "к", "m": "м", "o": "о", "p": "р", "t": "т", "x": "х", "y": "у"
})


def _is_complex_identifier(token: str) -> bool:
    """Определяет, является ли токен чертежом, децимальным номером или артикулом детали."""
    token = token.strip("()[]{}<>\"'*#№!, =")
    if len(token) < 4:
        return False
    # Исключаем составные словосочетания с пробелами (наименования ТМЦ, а не компактные коды/артикулы)
    if " " in token:
        return False
    # Исключаем инженерные габариты и геометрические размеры (3х2.5, 50х150, 1000х2000)
    if re.fullmatch(r'\d+(?:[.,]\d+)?\s*[xхXХ*]\s*\d+(?:[.,]\d+)?(?:\s*[xхXХ*]\s*\d+(?:[.,]\d+)?)?', token):
        return False
    # Исключаем инженерные параметры диаметров/длин/высот (D101-110, D21-24, L70, H=3м, DN50-100, PN10-16, ДУ100)
    if re.fullmatch(r'(?:[dDдДlLлЛhHвВwWшШ]|dn|pn|ду|ру)\s*=?\s*\d+(?:[.,]\d+)?\s*(?:[мm]|мм|см|г|кг|т|л|мл)?(?:[-–/]\d+(?:[.,]\d+)?)?', token, re.IGNORECASE):
        return False
    # Исключаем физические величины с единицами измерения (200г, 3мм, 50м, 1т, 6-5м, 50л)
    if re.fullmatch(r'\d+(?:[-–/]\d+)?\s*(?:г|кг|мг|т|л|мл|м|см|мм|км|шт|в|вт|квт|а|ма|v|w|kw|hz|гц)\b', token, re.IGNORECASE):
        return False
    # Исключаем простые дроби и соотношения двух чисел без букв (40/20, 2.5, 3/4)
    if re.fullmatch(r'\d+(?:[.,/]\d+)+', token) and not re.search(r'\d{1,4}\.\d{2,}\.\d{1,}', token):
        return False
    # Децимальный чертеж с цифрами и точками/дефисами (например 1085.05.02, 059.00.00-02, 2.607.019.435)
    if re.search(r'\d{1,4}\.\d{2,}\.\d{1,}', token) or re.search(r'\d+[.\-_/]\d+[.\-_/]\d+', token):
        return True
    # Чертеж с буквенным префиксом серии (например ЭГ.059.00.00-02, ВР30.02.000-01)
    if re.search(r'[a-zA-Zа-яА-ЯёЁ]+[.\-_/]\d+[.\-_/]', token):
        return True
    # Буквенно-цифровые коды модификаций и артикулов: буквы + цифры (например SPGA4270-200-01, ИП43хВх10х35х7, D-08660, ЦЧ-4)
    has_letters = bool(re.search(r"[a-zA-Zа-яА-ЯёЁ]", token))
    has_digits = bool(re.search(r"\d", token))
    if has_letters and has_digits:
        return True
    # Длинные числовые артикулы деталей (5+ цифр, например '130539')
    if re.fullmatch(r"\d{5,}", token):
        return True
    return False


def _has_deterministic_identifier_conflict(
    target_item_name: str,
    target_ids: list[Any],
    page_text: str,
    url: str,
) -> bool:
    """
    Детерминированная проверка соответствия чертежей и артикулов (Правило 14: Compare-then-Match).
    Если в запросе указан конкретный сложный чертеж или артикул, он ОБЯЗАН присутствовать в реальном тексте страницы или URL.
    Проверка выполняется по физическому контенту (ground truth), а не по галлюцинациям модели.
    """
    raw_corpus = f"{url} {page_text}".lower()
    # Нормализуем десятичные нули (2.0 -> 2, 2_0 -> 2), чтобы 'СТП 2.0/3000' совпадало с 'СТП 2/3000'
    cleaned_corpus = re.sub(r'(?<=\d)[.,_]0(?!\d)', '', raw_corpus)
    site_corpus = cleaned_corpus.translate(HOMOGLYPHS)
    norm_corpus = re.sub(r"[^a-zа-яё0-9]", "", site_corpus)

    candidates: list[str] = []
    all_raw_tokens: list[str] = []
    for tid in target_ids:
        tid_str = str(tid).strip()
        if " " in tid_str:
            all_raw_tokens.extend(tid_str.split())
        else:
            all_raw_tokens.append(tid_str)
    for tok in re.split(r"[\s,;]+", target_item_name):
        all_raw_tokens.append(tok)

    for tok in all_raw_tokens:
        c_tok = tok.strip("()[]{}<>\"'*#№!, =")
        if _is_complex_identifier(c_tok) and c_tok not in candidates:
            candidates.append(c_tok)

    if not candidates:
        return False

    for c in candidates:
        # Проверяем точное вхождение в исходный текст или URL
        if re.search(r'\b' + re.escape(c) + r'\b', raw_corpus, re.IGNORECASE):
            return False
        # Нормализованное сравнение (минимальная длина 3 для кодов типа ЦЧ-4 -> цч4)
        c_clean = re.sub(r'(?<=\d)[.,_]0(?!\d)', '', c.lower())
        norm_c = re.sub(r"[^a-zа-яё0-9]", "", c_clean.translate(HOMOGLYPHS))
        if len(norm_c) >= 3 and norm_c in norm_corpus:
            return False  # Найдено точное совпадение чертежа/артикула в реальном тексте
        norm_c_no_zero = re.sub(r"(?<=[a-zа-яё])0+(\d+)", r"\1", norm_c)
        if len(norm_c_no_zero) >= 3 and norm_c_no_zero in norm_corpus:
            return False
        # Также проверяем вариант без единичного префикса ветви/слоя (например СТП1-2 -> СТП 2)
        norm_c_no_single = re.sub(r"(?<=[а-яa-z])1(?=\d)", "", norm_c)
        if len(norm_c_no_single) >= 3 and norm_c_no_single in norm_corpus:
            return False

    return True  # В запросе есть конкретный чертеж/артикул, но в реальном тексте страницы его нет


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
    if not has_price_signals(page_text):
        logger.debug("Skip LLM extraction for %s: no price signals found on page", url)
        return None

    # Детерминированная проверка чертежей и артикулов перед вызовом LLM (Правило 14: Compare-then-Match)
    if _has_deterministic_identifier_conflict(target_item_name, [], page_text, url):
        logger.debug("Skip LLM extraction for %s: deterministic identifier conflict for %s", url, target_item_name)
        return None

    domain = urlparse(url).netloc
    norm_unit = normalize_unit(target_unit)

    prompt = f'''Ты ведущий эксперт по закупкам и коммерческому анализу цен (ПРАВИЛО 14: СЕМАНТИЧЕСКИЙ АНАЛИЗ И ФИЗИЧЕСКИЙ ПЕРЕСЧЕТ ЦЕН).
Твоя задача — внимательно изучить страницу поставщика и извлечь актуальную цену с точной привязкой к требуемой единице измерения.

Искомый товар: "{target_item_name}"
Требуемая единица измерения заказчика: "{norm_unit}"
URL страницы: {url}
Предварительно обнаруженные данные с сайта:
- ИНН: {pre_inn or "не обнаружен"}
- КПП: {pre_kpp or "не обнаружен"}
- Контакты: {pre_contacts or "не обнаружены"}

Текст страницы товара и реквизитов:
{page_text}

КРИТИЧЕСКИЕ ПРАВИЛА (АРХИТЕКТУРА COMPARE-THEN-MATCH, ПРАВИЛО 14):
1. ДЕКОМПОЗИЦИЯ ИДЕНТИФИКАТОРОВ И ПРОВЕРКА КОНФЛИКТОВ:
   - Исходный товар: выдели ключевые артикулы, чертежи, индексы, марки, материалы.
   - Товар на странице: определи точную марку, артикул, чертеж и функционал на странице.
   - КОНФЛИКТ ФУНКЦИОНАЛЬНОГО КЛАССА И КАТЕГОРИИ (category_conflict):
     * Товар на найденной странице обязан относиться к ТОМУ ЖЕ функциональному классу и назначению, что и запрос!
     * КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО сопоставлять товары принципиально разных классов при совпадении отдельных слов или бренда:
       - Измерительные приборы, датчики, преобразователи, КИПиА НЕЛЬЗЯ заменять на спецодежду/СИЗ (перчатки, обувь, очки), даже если бренд или корень слова совпадает!
       - Узлы промышленного оборудования, ветрогенераторов, турбин НЕЛЬЗЯ заменять на запчасти садовой техники (газонокосилки, триммеры) или бытовых приборов!
       - Заказные промышленные детали по чертежам НЕЛЬЗЯ заменять на уплотнения/детали кухонной бытовой техники (пароконвектоматы, духовки)!
     * Если функциональный класс принципиально не совпадает -> СТРОГО установи category_conflict: true, is_relevant: false, is_price_found: false!
   - КОНФЛИКТ ИДЕНТИФИКАТОРОВ И ЧЕРТЕЖЕЙ (identifier_conflict):
     * Если в запросе есть конкретный код, чертеж, децимальный номер или марка, а на странице продается ДРУГАЯ марка или общий товар без этого кода — СТРОГО установи identifier_conflict: true, is_relevant: false, is_price_found: false!
     * ЗАПРЕТ ЧАСТИЧНЫХ СОВПАДЕНИЙ ЦИФР В ЧЕРТЕЖАХ И АРТИКУЛАХ: случайное совпадение группы цифр (например '59-00-002' в номере чертежа бытовой плиты при поиске чертежа генератора) НЕ является совпадением! Идентификатор должен совпадать полностью.
     * Запрещены смысловые подмены и омонимы:
       - Промышленная футеровка/броня vs бронежилеты/плиты защиты человека -> conflict!
       - Била/молотки промышленных дробилок vs автомобильные колодки/диски/фильтры -> conflict!
       - Муфтовые/крановые пальцы vs поршневые пальцы двигателей автомобилей -> conflict!
   - КОНФЛИКТ КЛЮЧЕВЫХ ПАРАМЕТРОВ И МАСШТАБА (specification_conflict):
     * Если в запросе указана грузоподъемность, класс напряжения/мощности или критический типоразмер (например, 15 тонн, 10 кВ, 250 кВт), а на сайте найден товар принципиально другого масштаба (1 тонна, 220 В, 1.5 кВт) -> СТРОГО установи specification_conflict: true, is_relevant: false!
   - КОНФЛИКТ МАТЕРИАЛА (material_conflict):
     * Безасбестовые уплотнения нельзя заменять на асбестовые!
     * Конструкционные легированные стали нельзя заменять на углеродистый рядовой прокат без указания марки.
   - Если identifier_conflict, category_conflict, specification_conflict или material_conflict: true -> is_relevant: false, is_price_found: false.
2. ЦЕНА НА САЙТЕ (raw_price_rub) И ЕДИНИЦА (site_unit):
   - Найди реальную коммерческую цену в рублях, которая ЯВНО указана на странице.
   - ФИКТИВНЫЕ ЦЕНЫ-ЗАГЛУШКИ (1 руб, 0.01 руб) И СНЯТИЕ С ПРОИЗВОДСТВА:
     * Если на странице указана формальная заглушка (1.00 ₽, 0.01 ₽) вместо реальной стоимости ('уточняйте цену', 'по запросу', 'договорная'), либо товар помечен 'снят с производства' / 'архивный товар' — СТРОГО установи is_price_found: false, is_relevant: false!
     * ВНИМАНИЕ: Если указана реальная цена в рублях (например 890 ₽, 1 500 ₽), но на складе статус 'под заказ', 'уточняйте наличие' или 'нет на складе' — ЭТО ДЕЙСТВУЮЩАЯ ЦЕНА КАТАЛОГА ДЛЯ ЗАКУПКИ! Установи is_price_found: true, is_relevant: true!
3. СЕМАНТИЧЕСКИЙ ФИЗИЧЕСКИЙ ПЕРЕСЧЕТ В ЕДИНИЦУ ЗАКАЗЧИКА "{norm_unit}" (ПРАВИЛО 14):
   - Если единица на сайте уже совпадает с "{norm_unit}", price_rub = raw_price_rub.
   - Если отличается, выполни математический пересчет исходя из физических характеристик товара:
     а) Тара (бочки, канистры, мешки, ведра, банки, упаковки):
        - Если заказчик просит единицу (л, кг, т, шт), а на сайте цена за всю тару — раздели цену на объем/вес/кол-во тары (например, бочка 200 л по 50 601 руб -> 50 601 / 200 = 253.01 руб/л; канистра 10 л по 2 182 руб -> 218.20 руб/л).
        - Если заказчик просит в тоннах (т), а цена за мешок M кг: цена за тонну = (цена_мешка / M) * 1000 (например, мешок 50 кг по 525 руб -> 525 * 20 = 10 500 руб/т).
     б) Пиломатериалы и объемные изделия:
        - Если заказчик просит в м³, а цена на сайте за 1 штуку (доска, брус с указанными размерами): рассчитай физический объем 1 штуки в м³ (толщина * ширина * длина в метрах) и определи цену за 1 м³ = цена_штуки / объем_штуки (например, доска 50х150х6000 мм: объем 0.045 м³, цена 841 руб / 0.045 = 18 688.89 руб/м³).
     в) Металлопрокат и весовые товары:
        - Если заказчик просит в тоннах (т), а на сайте цена за 1 метр погонный: пересчитай в тонну по весу метра. Если вес метра неизвестен, отклони (is_price_found: false), так как цена за метр (~50-500 руб) не может быть ценой за тонну.
        - Если на сайте за кг, а заказчик просит в тоннах: умножь на 1000.
     г) Технические газы (сжатые и сжиженные):
        - Пропан в баллоне 50л содержит ~21.2 кг сжиженного газа (при запросе в кг: цена_баллона / 21.2).
        - Кислород, азот, аргон в сжатом виде под рабочим давлением 150 атм:
          * Баллон 40 л содержит 6.3 м³ нормального газа (при запросе в м³: цена / 6.3).
          * Баллон 10 л содержит 1.5 м³ нормального газа (при запросе в м³: цена / 1.5).
          * Баллон 5 л содержит 0.75 м³ нормального газа (при запросе в м³: цена / 0.75).
          * ВНИМАНИЕ: 1 м³ = 1 000 литров свободного газа! Не путай геометрический объем баллона в литрах с кубометрами газа!
        - Углекислота в баллоне 40л содержит ~24 кг жидкой CO2 (при запросе в кг: делить на 24).
   - В поле price_rub запиши ИТОГОВУЮ цену СТРОГО за 1 единицу "{norm_unit}".
   - В conversion_comment запиши подробную математическую формулу расчета.
4. РЕКВИЗИТЫ ПОСТАВЩИКА:
   - company_name: Официальное название (например, ООО "Металлсервис", ForOffice, Завод Уралтехгаз).
   - inn: ИНН организации (10 цифр для юрлиц, 12 для ИП). Если найден в тексте или предварительно — укажи обязательно!
   - kpp: КПП организации (9 цифр), если есть.
   - contacts: Телефон(ы), email, город поставщика.

Ответь СТРОГО JSON-объектом:
{{
  "target_identifiers": ["код/чертеж/марка из запроса"],
  "site_identifiers": ["код/чертеж/марка со страницы"],
  "identifier_conflict": false,
  "category_conflict": false,
  "specification_conflict": false,
  "material_conflict": false,
  "nomenclature_class": "Класс и назначение искомого товара",
  "site_product_name": "Точное наименование товара на найденной странице",
  "semantic_match_reason": "Семантическое обоснование совпадения или причина конфликта",
  "is_relevant": true,
  "is_price_found": true,
  "company_name": "ООО Название",
  "inn": "{pre_inn or ''}",
  "kpp": "{pre_kpp or ''}",
  "contacts": "{pre_contacts or ''}",
  "raw_price_rub": 2400.0,
  "site_unit": "баллон 50л",
  "pack_quantity": 21.0,
  "pack_base_unit": "кг",
  "is_price_for_whole_pack": true,
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

        # Проверка конфликтов Compare-then-Match (Правило 14)
        if (
            parsed.get("identifier_conflict")
            or parsed.get("category_conflict")
            or parsed.get("specification_conflict")
            or parsed.get("material_conflict")
        ):
            logger.debug("Rejected quote for %s: conflict detected: %s", url, parsed.get("semantic_match_reason"))
            return None

        # Детерминированная проверка соответствия чертежей и артикулов (Правило 14: Compare-then-Match)
        target_ids = parsed.get("target_identifiers") or []
        if _has_deterministic_identifier_conflict(target_item_name, target_ids, page_text, url):
            logger.debug("Rejected quote for %s: deterministic identifier conflict for %s", url, target_item_name)
            return None

        # Проверка снятия с производства / отсутствия на складе (защита от устаревших цен-призраков)
        if DISCONTINUED_PATTERN.search(page_text) or "СТАТУС НАЛИЧИЯ: СНЯТ С ПРОИЗВОДСТВА" in page_text:
            logger.debug("Rejected quote for %s: item is discontinued or out of stock", url)
            return None

        # Запрет подмены единицы "пар" (парные носимые изделия/СИЗ) для непарных промышленных ТМЦ (Правило 14)
        norm_site_u = str(parsed.get("site_unit") or "").lower().strip()
        if "пар" in norm_site_u and not any(w in target_item_name.lower() for w in ("перчат", "рукавиц", "краг", "обув", "ботинок", "сапог", "носк", "пар")):
            logger.debug("Rejected quote for %s: site unit is 'пар' for non-wearable item %s", url, target_item_name)
            return None

        # Семантическая проверка несовпадения классов прибора и СИЗ/одежды (Правило 14)
        nom_class = str(parsed.get("nomenclature_class") or "").lower()
        if nom_class and any(k in nom_class for k in ("перчат", "одежд", "обув")) and not any(k in target_item_name.lower() for k in ("перчат", "одежд", "обув")):
            logger.debug("Rejected quote for %s: nomenclature class indicates wearable/PPE %s for item %s", url, nom_class, target_item_name)
            return None

        if not parsed.get("is_relevant") or not parsed.get("is_price_found"):
            return None

        # Исходная цена
        raw_p = parsed.get("raw_price_rub") or parsed.get("price_rub")
        if raw_p is None:
            return None
        raw_price_val = float(raw_p)
        # Фильтрация фиктивных заглушек (1.00 ₽) и нереалистичных цен
        if raw_price_val <= 1.0 or raw_price_val > 500_000_000:
            logger.debug("Rejected quote for %s: dummy or out of range price %s", url, raw_price_val)
            return None

        # Проверка заземления цены (grounding check): цена должна присутствовать в тексте страницы/сниппета
        if not is_price_grounded_in_text(raw_price_val, page_text):
            logger.debug("Rejected quote for %s: price %s not grounded in page text", url, raw_price_val)
            return None

        site_unit = str(parsed.get("site_unit") or "").strip()
        pack_quantity = parsed.get("pack_quantity")
        if pack_quantity is not None:
            try:
                pack_quantity = float(pack_quantity)
            except Exception:
                pack_quantity = None
        pack_base_unit = str(parsed.get("pack_base_unit") or "").strip() or None
        is_price_for_whole_pack = bool(parsed.get("is_price_for_whole_pack"))

        # Детерминированный математический расчет цены в целевую единицу измерения заказчика (Правило 14)
        calc_price, calc_unit, calc_comment = compute_deterministic_normalized_price(
            raw_price=raw_price_val,
            site_unit=site_unit,
            target_unit=norm_unit,
            pack_quantity=pack_quantity,
            pack_base_unit=pack_base_unit,
            is_price_for_whole_pack=is_price_for_whole_pack,
            existing_comment=str(parsed.get("conversion_comment") or ""),
        )

        final_price_val = calc_price if (calc_price > 0 and calc_comment) else (float(parsed.get("price_rub")) if parsed.get("price_rub") is not None else raw_price_val)
        conv_comment = calc_comment or str(parsed.get("conversion_comment") or "").strip()
        match_reason = str(parsed.get("semantic_match_reason") or "").strip()

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
            comment=match_reason,
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

            # Гарантируем форму собственности: приводим к ООО только если это российский поставщик
            # без указанной ОПФ, чисто русскоязычный, и не является доменным именем или иностранным брендом
            known_forms = (
                "ООО", "АО", "ЗАО", "ПАО", "НПАО", "ИП", "ОБЩЕСТВО", "АКЦИОНЕРНОЕ",
                "МУП", "ГУП", "ФГУП", "АНО", "НКО", "ТСЖ", "СПК", "КООПЕРАТИВ",
                "МКОУ", "ГБОУ", "МБУ", "ГБУ"
            )
            upper_name = quote.company_name.upper().strip(" '\"«»")
            has_form = any(upper_name.startswith(f) for f in known_forms)
            if not has_form:
                clean_c = quote.company_name.strip(" '\"«»")
                if (
                    clean_c != domain
                    and "." not in clean_c
                    and not re.search(r'[a-zA-Z]', clean_c)
                    and len(clean_c) >= 3
                ):
                    quote.company_name = f'ООО "{clean_c}"'
        except Exception as d_exc:
            logger.debug("DaData enrichment skipped for %s: %s", quote.company_name, d_exc)

        # Применяем детерминированную проверку и до-пересчет единиц
        return reconcile_quote_unit(quote, target_item_name, target_unit)
    except Exception as exc:
        logger.debug("Quote extraction failed for %s: %s", url, exc)
        return None
