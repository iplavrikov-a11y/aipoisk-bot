import pytest
from app.price_monitoring.cleaner import clean_nomenclature_name
from app.price_monitoring.pipeline import cluster_and_reconcile_item_quotes
from app.price_monitoring.models import ItemPriceResult, SupplierQuote
from app.price_monitoring.extractor import is_listing_url, is_valid_domain, is_foreign_source
from app.price_monitoring.excel_report import _extract_phones_and_emails
from app.dadata_client import _parse_dadata_suggestion


def test_1c_cleaning_prefixes_and_suffixes():
    """Проверка очистки служебных префиксов и суффиксов 1C/ERP (Правило 14)."""
    assert clean_nomenclature_name("#Удлинитель силовый КГ 3х2.5") == "Удлинитель силовый КГ 3х2.5"
    assert clean_nomenclature_name("№Шайба 12 ГОСТ 11371") == "Шайба 12 ГОСТ 11371"
    assert clean_nomenclature_name("*Датчик давления Rosemount") == "Датчик давления Rosemount"
    assert clean_nomenclature_name("Кабель ВВГнг /СНЯТ") == "Кабель ВВГнг"
    assert clean_nomenclature_name("Труба 40х20 /АРХИВ") == "Труба 40х20"
    assert clean_nomenclature_name("Редуктор Ч-100 /УСТАРЕЛО") == "Редуктор Ч-100"
    assert clean_nomenclature_name("Лампа ДРЛ /ДУБЛЬ") == "Лампа ДРЛ"
    assert clean_nomenclature_name("Масло гидравлическое /НЕ ИСП (л)") == "Масло гидравлическое"


def test_multiplier_boundary_no_false_division_on_1000():
    """Проверка: размер '1000' не должен вызывать ложный пересчет кратности по 100 шт."""
    item = ItemPriceResult(
        row_number=1,
        raw_name="Фильтр 130539 Filter Size 1000 10MY",
        clean_name="Фильтр 130539 Filter Size 1000 10MY",
        unit="шт",
        quotes=[
            SupplierQuote(company_name="Поставщик 1", price_rub=1230.0, raw_price_rub=1230.0, unit="шт"),
            SupplierQuote(company_name="Поставщик 2 (Оригинал)", price_rub=123020.0, raw_price_rub=123020.0, unit="шт"),
        ],
    )
    # Ratio is ~100x, but "1000" in name is NOT 100-pack
    cluster_and_reconcile_item_quotes(item, cluster_ratio=2.0)
    # Price must NOT have been divided by 100 (which would be 1230.20)
    orig_q = next(q for q in item.quotes if "Оригинал" in q.company_name)
    assert orig_q.price_rub == 123020.0
    assert "Авто-пересчет кратности" not in (orig_q.conversion_comment or "")


def test_multiplier_boundary_valid_100_pack():
    """Проверка: упаковка по 100 шт корректно пересчитывается при наличии маркера штук."""
    item = ItemPriceResult(
        row_number=1,
        raw_name="Стяжка кабельная 100 шт",
        clean_name="Стяжка кабельная 100 шт",
        unit="шт",
        quotes=[
            SupplierQuote(company_name="Поставщик Поштучно", price_rub=1.5, raw_price_rub=1.5, unit="шт"),
            SupplierQuote(company_name="Поставщик Пачка", price_rub=150.0, raw_price_rub=150.0, unit="шт"),
        ],
    )
    cluster_and_reconcile_item_quotes(item, cluster_ratio=2.0)
    pack_q = next(q for q in item.quotes if "Пачка" in q.company_name)
    assert pack_q.price_rub == 1.50
    assert "Авто-пересчет кратности" in (pack_q.conversion_comment or "")


def test_listing_url_patterns_and_tags():
    """Проверка детекции листингов и страниц тегов (кувалда и аналоги)."""
    assert is_listing_url("https://kuvalda.ru/catalog/tag-1500m/") is True
    assert is_listing_url("https://kuvalda.ru/catalog/tag-60sm/") is True
    assert is_listing_url("https://kuvalda.ru/catalog/tag_heavy_duty/") is True
    assert is_listing_url("https://site.ru/popular/") is True
    assert is_listing_url("https://site.ru/catalog/product-12345.html") is False


def test_domains_doski_flagma_china():
    """Проверка новых стоп-маркетплейсов и кроссбордерных форвардеров."""
    assert is_valid_domain("https://doski.ru/post/123", filter_marketplaces=True) is False
    assert is_valid_domain("https://flagma.ru/item/456", filter_marketplaces=True) is False
    assert is_foreign_source("https://china.org.ru/catalog/item") is True
    assert is_valid_domain("https://china.org.ru/catalog/item", filter_foreign=True) is False


def test_email_sanitizer_removes_sentry_and_noreply():
    """Проверка фильтрации технических адресов (sentry, noreply)."""
    raw_contacts = (
        "Тел: +7 (343) 123-45-67, "
        "5da8dce271c9453f9d8d91ef89d64eaf@sentry.planetavto.ru, "
        "noreply@planetavto.ru, "
        "sales@planetavto.ru"
    )
    phones, emails = _extract_phones_and_emails(raw_contacts)
    assert "sentry" not in emails
    assert "noreply" not in emails
    assert "sales@planetavto.ru" in emails
    assert "+7 (343) 123-45-67" in phones


def test_dadata_non_commercial_filtering():
    """Проверка распознавания и отсева некоммерческих учреждений (МКОУ, школы, администрации)."""
    school_payload = {
        "value": 'МКОУ "Хомутовская средняя общеобразовательная школа № 1"',
        "data": {
            "inn": "4626002130",
            "kpp": "462601001",
            "opf": {
                "type": "LEGAL",
                "code": "75104",
                "full": "Муниципальное казенное общеобразовательное учреждение",
                "short": "МКОУ",
            },
            "name": {
                "full_with_opf": 'Муниципальное казенное общеобразовательное учреждение "Хомутовская средняя школа № 1"',
                "short_with_opf": 'МКОУ "Хомутовская СОШ № 1"',
            },
            "state": {"status": "ACTIVE"},
        },
    }
    parsed = _parse_dadata_suggestion(school_payload)
    assert parsed["is_non_commercial"] is True
    assert parsed["opf_short"] == "МКОУ"

    commercial_payload = {
        "value": 'ООО "Энергомаш"',
        "data": {
            "inn": "7701234567",
            "kpp": "770101001",
            "opf": {
                "type": "LEGAL",
                "code": "12300",
                "full": "Общество с ограниченной ответственностью",
                "short": "ООО",
            },
            "name": {
                "short_with_opf": 'ООО "Энергомаш"',
            },
            "state": {"status": "ACTIVE"},
        },
    }
    parsed_comm = _parse_dadata_suggestion(commercial_payload)
    assert parsed_comm["is_non_commercial"] is False
    assert parsed_comm["opf_short"] == "ООО"


@pytest.mark.asyncio
async def test_compare_then_match_conflict_and_dummy_price(monkeypatch):
    """Проверка отсечения конфликтов категории/параметров и фиктивных цен-заглушек 1.00 ₽."""
    from app.price_monitoring.extractor import extract_supplier_quote
    from app.models import SystemSettings

    settings = SystemSettings()

    # 1. Category conflict rejection
    async def fake_llm_category_conflict(s, prompt, **kwargs):
        return """{
            "target_identifiers": ["ИП43хВх10х35х7 Вибробит"],
            "site_identifiers": ["БИС ВИБРОБИТ"],
            "identifier_conflict": false,
            "category_conflict": true,
            "specification_conflict": false,
            "material_conflict": false,
            "nomenclature_class": "Вихретоковый датчик вибрации vs перчатки антивибрационные",
            "semantic_match_reason": "Несоответствие физического класса: датчик vs спецодежда",
            "is_relevant": false,
            "is_price_found": false,
            "raw_price_rub": 756.0,
            "price_rub": 756.0
        }"""

    monkeypatch.setattr("app.price_monitoring.extractor.call_llm", fake_llm_category_conflict)
    res = await extract_supplier_quote(
        url="https://supplier.ru/item1",
        page_text="Перчатки антивибрационные БИС ВИБРОБИТ 756 руб",
        target_item_name="Преобр.изм.ИП43хВх10х35х7 Вибробит",
        target_unit="шт",
        settings=settings,
    )
    assert res is None

    # 2. Specification conflict rejection
    async def fake_llm_spec_conflict(s, prompt, **kwargs):
        return """{
            "target_identifiers": ["Строп 15 тонн"],
            "site_identifiers": ["Строп 1 тонна"],
            "identifier_conflict": false,
            "category_conflict": false,
            "specification_conflict": true,
            "material_conflict": false,
            "semantic_match_reason": "Несовпадение грузоподъемности в 15 раз",
            "is_relevant": false,
            "is_price_found": false,
            "raw_price_rub": 1200.0,
            "price_rub": 1200.0
        }"""

    monkeypatch.setattr("app.price_monitoring.extractor.call_llm", fake_llm_spec_conflict)
    res_spec = await extract_supplier_quote(
        url="https://supplier.ru/item2",
        page_text="Строп 1 тонна 1200 руб",
        target_item_name="Строп текстильный 15 тонн",
        target_unit="шт",
        settings=settings,
    )
    assert res_spec is None

    # 3. Dummy placeholder price (1.00 ₽) rejection
    async def fake_llm_dummy_price(s, prompt, **kwargs):
        return """{
            "target_identifiers": ["Элметро-ИПТ-2"],
            "site_identifiers": ["Элметро-ИПТ-2"],
            "identifier_conflict": false,
            "category_conflict": false,
            "specification_conflict": false,
            "material_conflict": false,
            "is_relevant": true,
            "is_price_found": true,
            "raw_price_rub": 1.0,
            "price_rub": 1.0
        }"""

    monkeypatch.setattr("app.price_monitoring.extractor.call_llm", fake_llm_dummy_price)
    res_dummy = await extract_supplier_quote(
        url="https://otc.ru/item3",
        page_text="Блок питания Элметро-ИПТ-2 Цена 1 руб",
        target_item_name="Блок питания Элметро-ИПТ-2",
        target_unit="шт",
        settings=settings,
    )
    assert res_dummy is None

    # 4. Pair unit ('пар') rejection for non-wearable items
    async def fake_llm_pair_unit(s, prompt, **kwargs):
        return """{
            "target_identifiers": ["ИП43хВх10х35х7 Вибробит"],
            "site_identifiers": ["БИС ВИБРОБИТ"],
            "identifier_conflict": false,
            "category_conflict": false,
            "specification_conflict": false,
            "material_conflict": false,
            "nomenclature_class": "Датчик вибрации",
            "is_relevant": true,
            "is_price_found": true,
            "raw_price_rub": 756.0,
            "price_rub": 756.0,
            "site_unit": "пар"
        }"""

    monkeypatch.setattr("app.price_monitoring.extractor.call_llm", fake_llm_pair_unit)
    res_pair = await extract_supplier_quote(
        url="https://inter-safety.ru/item4",
        page_text="Перчатки антивибрационные БИС ВИБРОБИТ 756 руб",
        target_item_name="Преобр.изм.ИП43хВх10х35х7 Вибробит",
        target_unit="шт",
        settings=settings,
    )
    assert res_pair is None

    # 5. Deterministic drawing / part identifier conflict (oven gasket vs turbine drawing)
    # Even if LLM erroneously returned identifier_conflict: false
    async def fake_llm_hallucinated_match(s, prompt, **kwargs):
        return """{
            "target_identifiers": ["ЭГ.059.00.00-02"],
            "site_identifiers": ["ПКА20-11ПМ.7556.59.00.002", "120000020352"],
            "identifier_conflict": false,
            "category_conflict": false,
            "specification_conflict": false,
            "material_conflict": false,
            "nomenclature_class": "Прокладка уплотнительная",
            "site_product_name": "Прокладка ПКА20-11ПМ.7556.59.00.002 120000020352",
            "semantic_match_reason": "Совпадение по артикулу 59.00.002",
            "is_relevant": true,
            "is_price_found": true,
            "raw_price_rub": 350.0,
            "price_rub": 350.0,
            "site_unit": "шт"
        }"""

    monkeypatch.setattr("app.price_monitoring.extractor.call_llm", fake_llm_hallucinated_match)
    res_hallucinated = await extract_supplier_quote(
        url="https://www.corm.ru/catalog/zip/k-parokonvektomatam/pka/prokladka-pka20-11pm-7556-59-00-002-120000020352/",
        page_text="Прокладка ПКА20-11ПМ.7556.59.00.002 120000020352 цена 350 руб",
        target_item_name="Прокладка ЭГ.059.00.00-02",
        target_unit="шт",
        settings=settings,
    )
    assert res_hallucinated is None


def test_drawing_query_cascade_and_detection():
    """Проверка универсального распознавания заводских чертежей и генерации точных запросов в кавычках (Правило 14)."""
    from app.price_monitoring.cleaner import is_drawing_or_part_code, build_commercial_search_queries, build_fallback_broad_queries

    # 1. Распознавание чертежей vs габаритов и стандартов
    assert is_drawing_or_part_code("ЭГ.059.00.00-02") is True
    assert is_drawing_or_part_code("SPGA4270-200-01") is True
    assert is_drawing_or_part_code("1085.05.02") is True
    assert is_drawing_or_part_code("130539") is True
    assert is_drawing_or_part_code("3х2.5") is False  # геометрический размер
    assert is_drawing_or_part_code("1000х2000") is False  # геометрический размер
    assert is_drawing_or_part_code("7798-70", "ГОСТ 7798-70") is False  # ГОСТ

    # 2. Формирование запросов: чертеж обязательно в строгих кавычках
    queries = build_commercial_search_queries("Прокладка ЭГ.059.00.00-02", "шт")
    assert any('"ЭГ.059.00.00-02"' in q for q in queries)
    # Запрещены размытые запросы, где чертеж выброшен
    assert not any(q == "Прокладка купить цена в наличии" for q in queries)

    # 3. Фоллбэк волны 2: также строго сохраняет чертеж
    fb_queries = build_fallback_broad_queries("Прокладка ЭГ.059.00.00-02", "шт")
    assert any('"ЭГ.059.00.00-02"' in q for q in fb_queries)
    assert not any(q == "Прокладка купить цена" for q in fb_queries)


def test_deterministic_unit_math_engine():
    """Проверка детерминированного математического движка пересчета единиц (Правило 14)."""
    from app.price_monitoring.extractor import compute_deterministic_normalized_price, reconcile_quote_unit
    from app.price_monitoring.models import SupplierQuote

    # 1. Вес: кг <-> т
    p_ton, u_ton, comm_ton = compute_deterministic_normalized_price(45.0, "кг", "т")
    assert p_ton == 45000.0
    assert u_ton == "т"
    assert "Пересчитано в тонны (x1000)" in (comm_ton or "")

    p_kg, u_kg, comm_kg = compute_deterministic_normalized_price(45000.0, "т", "кг")
    assert p_kg == 45.0
    assert u_kg == "кг"
    assert "Пересчитано в кг (/1000)" in (comm_kg or "")

    # 2. Объем: л <-> м³
    p_m3, u_m3, comm_m3 = compute_deterministic_normalized_price(25.0, "л", "м3")
    assert p_m3 == 25000.0
    assert u_m3 == "м3"

    p_l, u_l, comm_l = compute_deterministic_normalized_price(25000.0, "м3", "л")
    assert p_l == 25.0
    assert u_l == "л"

    # 3. Тара / фасовка: бочка 200 л
    p_drum, _, comm_drum = compute_deterministic_normalized_price(
        raw_price=50601.0,
        site_unit="бочка 200л",
        target_unit="л",
        pack_quantity=200.0,
        pack_base_unit="л",
        is_price_for_whole_pack=True,
    )
    assert p_drum == 253.01
    assert "253.01 ₽/л" in (comm_drum or "")

    # 4. Фасовка: пачка 5 кг
    p_pack, _, comm_pack = compute_deterministic_normalized_price(
        raw_price=1200.0,
        site_unit="пачка 5 кг",
        target_unit="кг",
        pack_quantity=5.0,
        pack_base_unit="кг",
        is_price_for_whole_pack=True,
    )
    assert p_pack == 240.0
    assert "240.00 ₽/кг" in (comm_pack or "")

    # 5. Мешок 50 кг -> тонны (т)
    p_bag, _, comm_bag = compute_deterministic_normalized_price(
        raw_price=525.0,
        site_unit="мешок 50 кг",
        target_unit="т",
        pack_quantity=50.0,
        pack_base_unit="кг",
        is_price_for_whole_pack=True,
    )
    assert p_bag == 10500.0
    assert "10,500 ₽/т" in (comm_bag or "")

    # 6. Проверка через reconcile_quote_unit без товарных ключевых слов
    q = SupplierQuote(
        company_name="Поставщик ТМЦ",
        price_rub=55000.0,
        raw_price_rub=55000.0,
        site_unit="т",
        unit="т",
    )
    # Любой произвольный товар X без слова 'сталь' или 'арматура'
    reconciled = reconcile_quote_unit(q, target_item_name="Полимерные гранулы ПНД-273", target_unit="кг")
    assert reconciled.price_rub == 55.0
    assert reconciled.unit == "кг"


def test_schema_org_offers_and_out_of_stock_guard():
    """Проверка извлечения данных Schema.org JSON-LD и отсева отсутствующих/архивных товаров."""
    from bs4 import BeautifulSoup
    from app.price_monitoring.extractor import extract_schema_org_product_data, DISCONTINUED_PATTERN

    # 1. Валидный товар в наличии
    html_instock = """
    <html><head>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "Прокладка уплотнительная 1085.05.02",
      "sku": "1085.05.02",
      "offers": {
        "@type": "Offer",
        "price": "450.00",
        "priceCurrency": "RUB",
        "availability": "https://schema.org/InStock"
      }
    }
    </script>
    </head><body><h1>Каталог</h1></body></html>
    """
    soup1 = BeautifulSoup(html_instock, "html.parser")
    prod1, is_oos1 = extract_schema_org_product_data(soup1)
    assert prod1 is not None
    assert prod1["price"] == 450.0
    assert prod1["sku"] == "1085.05.02"
    assert is_oos1 is False

    # 2. Товар со статусом OutOfStock
    html_oos = """
    <html><head>
    <script type="application/ld+json">
    {
      "@type": "Product",
      "name": "Старый блок питания",
      "offers": {
        "price": "1200",
        "priceCurrency": "RUB",
        "availability": "http://schema.org/OutOfStock"
      }
    }
    </script>
    </head><body></body></html>
    """
    soup2 = BeautifulSoup(html_oos, "html.parser")
    prod2, is_oos2 = extract_schema_org_product_data(soup2)
    assert is_oos2 is True

    # 3. Текстовый паттерн снятия с производства
    assert bool(DISCONTINUED_PATTERN.search("Внимание: данный товар снят с производства!")) is True
    assert bool(DISCONTINUED_PATTERN.search("Товар в архиве, заказ невозможен")) is True
    assert bool(DISCONTINUED_PATTERN.search("Товар в наличии на складе")) is False
