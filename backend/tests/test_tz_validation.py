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


@pytest.mark.asyncio
async def test_analyze_exact_product_rejects_empty_or_placeholder():
    settings = SystemSettings()
    with pytest.raises(ValueError, match="нет содержимого|недостаточно данных|шаблон"):
        await analyze_exact_product(
            settings=settings,
            context="=== FILE: Органайзеры - Обнинск.docx ===\n\nВведите текст технического задания...",
            procurement_title="Органайзеры - Обнинск",
        )
