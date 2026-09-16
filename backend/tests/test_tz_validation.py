import pytest
from app.document_parser import is_substantive_tz_text
from app.exact_product import analyze_exact_product
from app.models import SystemSettings


def test_is_substantive_tz_text_empty():
    ok, err = is_substantive_tz_text("")
    assert not ok
    assert "пустой" in err.lower() or "отсутствует" in err.lower()

    ok, err = is_substantive_tz_text("   \n\t  ")
    assert not ok


def test_is_substantive_tz_text_placeholder_template():
    placeholder = "Введите текст технического задания..."
    ok, err = is_substantive_tz_text(placeholder)
    assert not ok
    assert "нет содержимого" in err.lower() or "шаблон" in err.lower()


def test_is_substantive_tz_text_placeholder_with_file_header():
    wrapped = "=== FILE: Органайзеры - Обнинск.docx ===\n\nВведите текст технического задания...\n"
    ok, err = is_substantive_tz_text(wrapped)
    assert not ok
    assert "нет содержимого" in err.lower() or "шаблон" in err.lower()


def test_is_substantive_tz_text_other_placeholders():
    samples = [
        "[Введите текст технического задания]",
        "Шаблон ТЗ",
        "Текст технического задания...",
        "В документе нет содержимого",
        "=== FILE: test.docx ===\n\n[текст тз]",
    ]
    for s in samples:
        ok, err = is_substantive_tz_text(s)
        assert not ok, f"Failed to reject placeholder: {s}"


def test_is_substantive_tz_text_real_procurement():
    real_tz = """
    ТЕХНИЧЕСКОЕ ЗАДАНИЕ
    Органайзеры - Обнинск
    Позиция 1: Органайзер для СИЗ двухсекционный настенный
    Габариты: 300х150х300 мм. Материал: прозрачный поликарбонат, устойчивый к дезинфектантам.
    """
    ok, err = is_substantive_tz_text(real_tz)
    assert ok
    assert err == "ok"


def test_is_substantive_tz_text_rejects_electronic_signature_only():
    sig_text = """
    === FILE: ЗЗК (166-1231856) Т2 - Тех. часть.pdf ===
    ДОКУМЕНТ ПОДПИСАН УКЭП ЭЛЕКТРОННОЙ ПОДПИСЬЮ
    СВЕДЕНИЯ О СЕРТИФИКАТЕ ЭП
    Акционерное общество "Гринатом",
    Сертификат: 06 DA AB D4 00 D2 B3 C4 83 4C C0 EC F5 98 AF A7 A9
    Владелец: easelezneva@vniia.ru
    Срок действия с 14.01.2026 по 14.04.2027
    """
    ok, err = is_substantive_tz_text(sig_text)
    assert not ok
    assert "электронной подписи" in err.lower() or "недостаточно данных" in err.lower()


@pytest.mark.asyncio
async def test_analyze_exact_product_rejects_empty_or_placeholder():
    settings = SystemSettings()
    with pytest.raises(ValueError, match="нет содержимого|недостаточно данных|шаблон"):
        await analyze_exact_product(
            settings=settings,
            context="=== FILE: Органайзеры - Обнинск.docx ===\n\nВведите текст технического задания...",
            procurement_title="Органайзеры - Обнинск",
        )


def test_normalize_procurement_profile_filters_generic_names():
    from app.supplier_search import _normalize_procurement_profile

    raw = {
        "summary": "предмет закупки не определен",
        "items": [
            {"id": "item-1", "name": "не определено", "category_terms": ["оборудование"]},
            {"id": "item-2", "name": "undefined", "category_terms": ["прочее"]},
            {"id": "item-3", "name": "Зачистная машина", "category_terms": ["станки"]},
        ],
    }
    profile = _normalize_procurement_profile(raw)
    assert len(profile.items) == 1
    assert profile.items[0].name == "Зачистная машина"
    assert profile.summary == ""

