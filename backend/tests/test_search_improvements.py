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
