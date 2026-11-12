import os
import pytest
from app.supplier_search import (
    _is_placeholder_profile_term,
    _clean_profile_terms,
    _normalize_procurement_profile,
    extract_supplier_entities_from_aggregator_snippet,
)
from app.document_parser import extract_smart_pdf_content
from app.exact_product.yandex_search import YandexSearchEngine


def test_is_placeholder_profile_term():
    # Exact placeholders
    assert _is_placeholder_profile_term("отечественный производитель") is True
    assert _is_placeholder_profile_term("по спецификации заказчика") is True
    assert _is_placeholder_profile_term("согласно тз") is True
    assert _is_placeholder_profile_term("паспорт завода") is True
    assert _is_placeholder_profile_term("в соответствии с тз") is True
    assert _is_placeholder_profile_term("не указано") is True
    assert _is_placeholder_profile_term("—") is True

    # Substrings
    assert _is_placeholder_profile_term("по спецификации заказчика от 2024") is True
    assert _is_placeholder_profile_term("в открытой документации заказчика") is True

    # Real products/models should NEVER be considered placeholders
    assert _is_placeholder_profile_term("Насос центробежный 1Д200-90") is False
    assert _is_placeholder_profile_term("Кабель ВВГнг(А)-LS 3х2.5") is False
    assert _is_placeholder_profile_term("Электропривод ГЗ-А.100/24") is False
    assert _is_placeholder_profile_term("СППК4Р-16") is False


def test_clean_profile_terms_filters_placeholders():
    raw = [
        "Отечественный производитель",
        "1Д200-90",
        "По спецификации заказчика",
        "Насос 1Д200",
        "согласно ТЗ",
    ]
    cleaned = _clean_profile_terms(raw)
    assert cleaned == ("1Д200-90", "Насос 1Д200")


def test_normalize_procurement_profile_drops_dummy_items():
    raw_data = {
        "summary": "Поставка насосов",
        "items": [
            {
                "id": "item-1",
                "name": "Насос центробежный",
                "aliases": ["Отечественный производитель", "1Д200-90"],
                "category_terms": ["насосное оборудование", "согласно тз"],
                "exact_terms": ["паспорт завода", "1Д200-90"],
            },
            {
                "id": "item-2",
                "name": "Отечественный производитель",
                "aliases": ["По спецификации заказчика"],
            },
        ],
    }
    profile = _normalize_procurement_profile(raw_data)
    assert len(profile.items) == 1
    assert profile.items[0].name == "Насос центробежный"
    assert profile.items[0].aliases == ("1Д200-90",)
    assert profile.items[0].category_terms == ("насосное оборудование",)
    assert profile.items[0].exact_terms == ("1Д200-90",)


def test_extract_supplier_entities_from_aggregator_snippet():
    snippet_1 = "Купить насос ЦНСг 38-176 по цене завода. Поставщик: ООО \"Гидромаш-Самара\", доставка по РФ."
    entities_1 = extract_supplier_entities_from_aggregator_snippet("Насосы ЦНСг", snippet_1)
    assert 'ООО "Гидромаш-Самара"' in entities_1

    snippet_aggregator_stopword = "Портал Пульс Цен. Продавец: ООО \"Пульс Цен Сервис\". Доставка."
    entities_agg = extract_supplier_entities_from_aggregator_snippet("Каталог", snippet_aggregator_stopword)
    assert len(entities_agg) == 0

    snippet_avito = "Объявления на Авито. Компания ООО \"Авито Холдинг\""
    assert len(extract_supplier_entities_from_aggregator_snippet("Авито", snippet_avito)) == 0

    snippet_factory = "Шкафы ШРН-Э. Производство Завод «Электрощит-Самара», гарантия 3 года."
    entities_fac = extract_supplier_entities_from_aggregator_snippet("Шкафы ШРН", snippet_factory)
    assert 'Завод «Электрощит-Самара»' in entities_fac


def test_extract_smart_pdf_content():
    import fitz
    doc = fitz.open()
    # Page 0: Cover
    p0 = doc.new_page()
    p0.insert_text((50, 50), "Catalog 2026. Equipment Factory.")
    # Page 1: Marketing / empty
    p1 = doc.new_page()
    p1.insert_text((50, 50), "About company: We were founded in 1990. Mission...")
    # Page 2: Technical table
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Technical parameters model VR-80-75 GOST 5976-90 pressure flow tables")
    pdf_bytes = doc.write()
    doc.close()

    result = extract_smart_pdf_content(pdf_bytes, max_pages_to_extract=5, max_chars=10000)
    assert "VR-80-75" in result
    assert "5976-90" in result
    assert "Catalog 2026" in result


def test_yandex_search_exact_product_groups_on_page():
    engine = YandexSearchEngine("test_folder", "test_key")
    # Test default environment variable setting
    os.environ["AIPOISK_YANDEX_GROUPS_ON_PAGE"] = "75"
    try:
        import inspect
        src = inspect.getsource(engine._search_v2)
        assert "groups_on_page" in src
        assert "AIPOISK_YANDEX_GROUPS_ON_PAGE" in src
    finally:
        os.environ.pop("AIPOISK_YANDEX_GROUPS_ON_PAGE", None)


def test_domestic_product_names_not_dropped_as_placeholders():
    # Standing alone generic terms must still be placeholders
    assert _is_placeholder_profile_term("отечественный производитель") is True
    assert _is_placeholder_profile_term("отечественного производства") is True

    # Real products qualified as domestic must NEVER be treated as placeholders
    assert _is_placeholder_profile_term("Серверное оборудование (серверы отечественного производства)") is False
    assert _is_placeholder_profile_term("Отечественные серверы") is False
    assert _is_placeholder_profile_term("Серверы отечественного производства") is False

    raw_data = {
        "subject_kind": "goods",
        "summary": "Поставка отечественного оборудования для модернизации ЦОД",
        "items": [
            {
                "id": "item-1",
                "item_kind": "goods",
                "name": "Серверное оборудование (серверы отечественного производства)",
                "okpd2_codes": ["26.20.14.100"],
                "category_terms": ["серверы"],
            },
            {
                "id": "item-2",
                "item_kind": "goods",
                "name": "Коммутатор",
                "category_terms": ["сетевые коммутаторы"],
            },
            {
                "id": "item-3",
                "name": "Товар по ТЗ",
            },
        ],
    }
    profile = _normalize_procurement_profile(raw_data)
    assert profile.subject_kind == "goods"
    assert len(profile.items) == 2
    assert profile.items[0].name == "Серверное оборудование (серверы отечественного производства)"
    assert profile.items[0].okpd2_codes == ("26.20.14.100",)
    assert profile.items[1].name == "Коммутатор"


def test_normalize_procurement_profile_services_and_mixed_guard():
    from app.supplier_search import build_universal_negative_keywords

    # Pure services without goods -> subject_kind='services', item_kind='service'
    pure_service = _normalize_procurement_profile(
        {
            "subject_kind": "services",
            "summary": "Комплексная уборка помещений на объектах ГБУЗ",
            "items": [
                {
                    "id": "item-1",
                    "item_kind": "service",
                    "name": "Комплексная уборка помещений",
                    "category_terms": ["клининговые услуги", "уборка медицинских учреждений"],
                    "required_terms": ["Москва"],
                }
            ],
        }
    )
    assert pure_service.subject_kind == "services"
    assert len(pure_service.items) == 1
    assert pure_service.items[0].item_kind == "service"
    assert build_universal_negative_keywords("Демонтаж и вывоз строительного мусора", subject_kind="services") == []
    assert "б/у" in build_universal_negative_keywords("Поставка серверов", subject_kind="goods")

    # Mixed TZ safety net: even if AI returned both goods and ancillary service items, keep ONLY physical goods
    mixed_data = {
        "subject_kind": "services",
        "summary": "Поставка стеллажей, доставка и монтаж",
        "items": [
            {
                "id": "item-1",
                "item_kind": "goods",
                "name": "Стеллажи металлические",
                "category_terms": ["металлические стеллажи"],
            },
            {
                "id": "item-2",
                "item_kind": "service",
                "name": "Доставка и разгрузка",
                "category_terms": ["грузоперевозки"],
            },
            {
                "id": "item-3",
                "item_kind": "service",
                "name": "Монтаж стеллажей",
                "category_terms": ["монтажные работы"],
            },
        ],
    }
    mixed_profile = _normalize_procurement_profile(mixed_data)
    assert mixed_profile.subject_kind == "goods"
    assert [it.name for it in mixed_profile.items] == ["Стеллажи металлические"]
    assert all(it.item_kind == "goods" for it in mixed_profile.items)


@pytest.mark.asyncio
async def test_extract_supplier_search_context_preserves_concise_spec(monkeypatch):
    from types import SimpleNamespace
    from app import supplier_search

    called = False

    async def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        return "{}"

    monkeypatch.setattr(supplier_search, "call_llm", fail_if_called)
    settings = SimpleNamespace(has_active_ai_provider=True)
    concise_spec = (
        "Регион поставки: г. Москва\n\n"
        "Поставка отечественного оборудования для модернизации ЦОД\n"
        "Позиции:\n"
        "1. Серверы, 1 усл. ед, ОКПД2 26.20.14.100"
    )
    extracted = await supplier_search.extract_supplier_search_context(settings, concise_spec)
    assert called is False
    assert "1. Серверы, 1 усл. ед, ОКПД2 26.20.14.100" in extracted


@pytest.mark.asyncio
async def test_services_mode_queries_verify_minprom_skip_and_quote_request(monkeypatch):
    from types import SimpleNamespace
    from app import supplier_search
    from app.quote_request import build_quote_request_markdown

    service_profile = supplier_search._normalize_procurement_profile(
        {
            "subject_kind": "services",
            "summary": "Оказание услуг по комплексной уборке помещений на объектах ГБУЗ ГП 212 ДЗМ",
            "items": [
                {
                    "id": "item-1",
                    "item_kind": "service",
                    "name": "Комплексная уборка помещений",
                    "category_terms": ["клининговые услуги", "уборка медицинских помещений"],
                    "exact_terms": ["ежедневная комплексная уборка"],
                    "required_terms": ["клининг для организаций"],
                }
            ],
        }
    )

    prompts_seen: list[str] = []

    async def fake_call_llm(settings, prompt, **kwargs):
        prompts_seen.append(prompt)
        routing_key = kwargs.get("routing_key")
        if routing_key == "supplier_query_generation":
            return '{"queries": ["клининговая компания Москва для организаций", "комплексная уборка медицинских помещений подрядчик"]}'
        if routing_key == "supplier_candidate_reranker":
            return '{"ranked": [{"id": "0", "keep": true, "confidence": 85, "procurement_item_id": "item-1", "reason": "профильная клининговая компания"}]}'
        if routing_key == "supplier_candidate_verifier":
            return (
                '{"action": "accept", "confidence": 90, "site_type": "service_company", "product_fit": "exact", '
                '"procurement_item_id": "item-1", "procurement_item_name": "Комплексная уборка помещений", '
                '"company_name": "ООО Чистый Мир", "inn": "7701234567", "region": "Москва", '
                '"status": "исполнитель", "product": "Комплексная уборка медицинских и офисных помещений", '
                '"email": "info@clean-world.ru", "phone": "+7 495 123-45-67", '
                '"evidence_url": "https://clean-world.ru/uslugi", "contact_url": "https://clean-world.ru/contacts", '
                '"evidence_snippet": "Выполняем ежедневную комплексную уборку помещений для клиник и коммерческих объектов.", '
                '"contact_evidence_snippet": "Контакты: +7 495 123-45-67, info@clean-world.ru", '
                '"comments": "Профильная клининговая компания, выполняет уборку коммерческих и медицинских объектов."}'
            )
        raise AssertionError(f"Unexpected routing_key: {routing_key}")

    monkeypatch.setattr(supplier_search, "call_llm", fake_call_llm)
    settings = SimpleNamespace(has_active_ai_provider=True)

    queries = await supplier_search.build_supplier_queries(
        settings,
        "Оказание услуг по комплексной уборке помещений ГБУЗ ГП 212 ДЗМ",
        10,
        profile=service_profile,
        delivery_city="Москва",
    )
    assert any("компания исполнитель" in q for q in queries)
    assert not any("официальный дилер" in q for q in queries)
    assert not any("купить оптом склад" in q for q in queries)

    cand = supplier_search.Candidate(
        url="https://clean-world.ru/uslugi",
        domain="clean-world.ru",
        title="ООО Чистый Мир — клининговая компания в Москве",
        snippet="Комплексная уборка помещений и медицинских центров по договору.",
        query=queries[0],
    )
    pages = [
        {
            "url": "https://clean-world.ru/uslugi",
            "text": "ООО Чистый Мир оказывает услуги по комплексной уборке помещений для организаций и медучреждений. Расчёт стоимости КП, договор, телефон +7 495 123-45-67, info@clean-world.ru.",
        }
    ]
    local_match = supplier_search.assess_candidate_match(cand, service_profile.summary, pages, subject_kind="services")
    assert local_match.accepted is True

    decision = await supplier_search.ai_verify(
        settings,
        cand,
        service_profile.summary,
        pages,
        ["info@clean-world.ru"],
        ["+7 495 123-45-67"],
        local_match,
        profile=service_profile,
    )
    assert decision["action"] == "accept"
    assert decision["site_type"] == "service_company"
    assert supplier_search._ai_rejection_reason(decision) == ""
    assert any("компанию-исполнителя" in p for p in prompts_seen)

    # Minprom should be skipped under SUPPLIER_POLICY_NORMAL for pure services
    minprom_called = False

    async def fail_minprom(*args, **kwargs):
        nonlocal minprom_called
        minprom_called = True
        raise AssertionError("assess_minprom_registry_requirement must be skipped for pure services")

    async def fake_discover_candidates(*args, **kwargs):
        return [cand], {"provider_order": ["yandex"], "yandex_requests_count": 1, "yandex_cost_rub": 0.03}

    async def fake_verify_candidate(*args, **kwargs):
        return {
            "company_name": "ООО Чистый Мир",
            "site": "https://clean-world.ru/uslugi",
            "evidence_url": "https://clean-world.ru/uslugi",
            "contact_url": "https://clean-world.ru/contacts",
            "phone": "+7 495 123-45-67",
            "email": "info@clean-world.ru",
            "status": "исполнитель",
            "site_type": "service_company",
            "product_fit": "exact",
            "match_level": "exact",
            "evidence_status": "verified",
            "quality_score": 92,
            "quality_tier": "high",
            "product": "Комплексная уборка помещений",
            "comments": "Профильная клининговая компания.",
            "procurement_item_id": "item-1",
            "procurement_item": "Комплексная уборка помещений",
        }

    async def fake_dadata(rows):
        return rows

    monkeypatch.setattr(supplier_search, "assess_minprom_registry_requirement", fail_minprom)
    monkeypatch.setattr(supplier_search, "discover_candidates", fake_discover_candidates)
    monkeypatch.setattr(supplier_search, "verify_candidate", fake_verify_candidate)
    monkeypatch.setattr(supplier_search, "_enrich_accepted_suppliers_with_dadata", fake_dadata)

    accepted, evidence = await supplier_search.discover_suppliers(
        settings,
        service_profile.summary,
        1,
        cached_procurement_profile=supplier_search.profile_to_dict(service_profile),
        delivery_city="Москва",
    )
    assert minprom_called is False
    assert evidence["procurement_profile"]["subject_kind"] == "services"
    assert evidence["minprom_registry"]["status"] == "not_required"
    assert len(accepted) == 1
    assert accepted[0]["status"] == "исполнитель"

    quote_md = build_quote_request_markdown(
        service_profile.summary,
        subject="Комплексная уборка помещений",
        procurement_profile=supplier_search.profile_to_dict(service_profile),
        delivery_city="Москва",
    )
    assert "### Условия оказания услуг" in quote_md
    assert "**Место оказания услуг:** г. Москва" in quote_md
    assert "по указанным ниже товарам" not in quote_md
    assert "Упаковка/тара" not in quote_md
