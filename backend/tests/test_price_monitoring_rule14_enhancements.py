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


def test_glued_dot_abbreviations_separation():
    """Проверка разделения точек сокращений 1C/ERP от характеристик и артикулов (Правило 14)."""
    from app.price_monitoring.cleaner import clean_nomenclature_name

    assert clean_nomenclature_name("Хомут ремонтный оцин.D101-110 L1") == "Хомут ремонтный оцин. D101-110 L1"
    assert clean_nomenclature_name("Пластина вакуум.10-7889-45-60 700х1500") == "Пластина вакуум. 10-7889-45-60 700х1500"
    assert clean_nomenclature_name("Датчик давл.EJX530A-ECS9N-014NL/QREP/s") == "Датчик давл. EJX530A-ECS9N-014NL/QREP/s"
    assert clean_nomenclature_name("Шайба прямоуг.8ВК.951.075") == "Шайба прямоуг. 8ВК.951.075"
    assert clean_nomenclature_name("Преобр.изм.ИП43хВх10х35х7") == "Преобр. изм. ИП43хВх10х35х7"
    # Сохранение десятичных дробей и двухбуквенных чертежей
    assert clean_nomenclature_name("Прокладка ЭГ.059.00.00-02") == "Прокладка ЭГ.059.00.00-02"
    assert clean_nomenclature_name("Кабель ВВГ 3х1.5") == "Кабель ВВГ 3х1.5"


def test_dimension_ranges_not_treated_as_drawings():
    """Проверка того, что инженерные диапазоны размеров и физические величины не путаются с чертежами (Правило 14)."""
    from app.price_monitoring.cleaner import is_drawing_or_part_code
    from app.price_monitoring.extractor import _is_complex_identifier

    non_drawings = [
        "D101-110", "D140-149", "D21-24", "L70", "L1", "H=3м",
        "200г", "3мм", "50м", "1т", "6-5м", "40/20", "DN50-100", "PN16"
    ]
    for nd in non_drawings:
        assert is_drawing_or_part_code(nd) is False, f"Expected {nd} NOT to be a drawing code"
        assert _is_complex_identifier(nd) is False, f"Expected {nd} NOT to be a complex identifier"

    drawings = [
        "D-08660", "2.607.019.435", "SPGA4270-200-01", "ЦЧ-4", "130539",
        "ЭГ.059.00.00-02", "5ВК.568.007.2", "ИП43хВх10х35х7"
    ]
    for d in drawings:
        assert is_drawing_or_part_code(d) is True, f"Expected {d} to be recognized as drawing/part"
        assert _is_complex_identifier(d) is True, f"Expected {d} to be recognized as complex identifier"


def test_drawing_query_preserves_brand_and_context_words():
    """Проверка того, что поиск по чертежам сохраняет бренды и определяющие существительные (Правило 14)."""
    from app.price_monitoring.cleaner import build_commercial_search_queries

    # Набор сверл Makita D-08660
    q1 = build_commercial_search_queries("Набор сверл D-08660 Makita", "шт")
    assert any("Makita" in q and "D-08660" in q for q in q1)
    assert any("сверл" in q for q in q1)

    # Набор сверл Bosch 2.607.019.435
    q2 = build_commercial_search_queries("Набор сверл 2.607.019.435 Bosch", "шт")
    assert any("Bosch" in q and "2.607.019.435" in q for q in q2)

    # Блок питания Элметро-ИПТ-2
    q3 = build_commercial_search_queries("Блок питания Элметро-ИПТ-2", "шт")
    assert any("питания" in q and "Элметро-ИПТ-2" in q for q in q3)


def test_deterministic_conflict_short_codes_and_decimal_zeros():
    """Проверка отсутствия ложных конфликтов для коротких кодов (ЦЧ-4) и дробей (СТП 2.0/3000)."""
    from app.price_monitoring.extractor import _has_deterministic_identifier_conflict

    # ЦЧ-4 (длина 3 в нормализованном виде)
    page_text_cch = "Электроды сварочные ЦЧ-4 диаметр 3мм по цене 1020 руб в наличии"
    assert _has_deterministic_identifier_conflict("Электрод ЦЧ-4 3мм", [], page_text_cch, "https://centermetiz.ru/item") is False

    # СТП 2.0/3000 vs СТП1-2/3000
    page_text_stp = "Строп текстильный петлевой СТП 2.0/3000 цена 850 руб"
    assert _has_deterministic_identifier_conflict("Строп СТП1-2/3000", [], page_text_stp, "https://rucranes.ru/item") is False

    # Чужой товар (конфликт сохраняется)
    page_text_other = "Электроды сварочные МР-3С диаметр 3мм цена 450 руб"
    assert _has_deterministic_identifier_conflict("Электрод ЦЧ-4 3мм", [], page_text_other, "https://example.com/item") is True


def test_deterministic_conflict_slash_and_modular_series():
    """Проверка отсутствия ложных конфликтов для блочно-модульных артикулов с модификациями (ИРТ-5922-МВ/В/t1050)."""
    from app.price_monitoring.extractor import _has_deterministic_identifier_conflict

    # Поставщик указывает базовую модель ИРТ-5922-МВ
    page_text_irt = "Измеритель-регулятор технологический ИРТ-5922-МВ в наличии на складе в Москве"
    assert _has_deterministic_identifier_conflict(
        "Измеритель-регулятор ИРТ-5922-МВ/В/t1050", [], page_text_irt, "https://propribory.ru/catalog/irt"
    ) is False

    # Поставщик указывает семейство ИРТ-5922
    page_text_base = "Приборы серии ИРТ-5922 измерители-регуляторы купить по оптовой цене"
    assert _has_deterministic_identifier_conflict(
        "Измеритель-регулятор ИРТ-5922-МВ/В/t1050", [], page_text_base, "https://tps21mag.ru/catalog/irt-5922"
    ) is False

    # Клапан Hoerbiger 385RF-NG-SPT63B
    page_text_valve = "Клапан компрессорный 385RF Hoerbiger оригинальные запчасти"
    assert _has_deterministic_identifier_conflict(
        "Клапан P8 385RF-NG-SPT63B PS11048-630A01", [], page_text_valve, "https://alnext.ru/item"
    ) is False


def test_html_tag_delimited_contacts_and_inn():
    """Проверка извлечения ИНН и контактов, разделенных HTML-тегами (<dt>/<dd>, <td>/<td>)."""
    from app.price_monitoring.extractor import _extract_inn_kpp_contacts

    sample_html = """
    <div class="company-details">
      <dl>
        <dt>ИНН</dt>
        <dd>4705076091</dd>
        <dt>КПП</dt>
        <dd>470501001</dd>
      </dl>
      <div class="phone">Тел: +7 (812) 309-29-49</div>
      <div class="email">zakaz@4-20.ru</div>
    </div>
    """
    inn, kpp, contacts = _extract_inn_kpp_contacts(sample_html)
    assert inn == "4705076091"
    assert kpp == "470501001"
    assert contacts is not None
    assert "+7 (812) 309-29-49" in contacts
    assert "zakaz@4-20.ru" in contacts


