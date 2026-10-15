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
            {"id": "item-3", "name": "Товары по техническому заданию", "category_terms": ["материальные ресурсы"]},
            {"id": "item-4", "name": "Техническое предложение", "category_terms": ["форма"]},
            {"id": "item-5", "name": "Зачистная машина", "category_terms": ["станки"]},
        ],
    }
    profile = _normalize_procurement_profile(raw)
    assert len(profile.items) == 1
    assert profile.items[0].name == "Зачистная машина"
    assert profile.summary == ""


def test_is_substantive_tz_text_rejects_empty_form_template():
    form_text = """
    Приложение № 1.3 к извещению
    Инструкция по заполнению формы технического предложения:
    Техническое предложение оформляется участником отдельно по каждому лоту и предоставляется в составе заявки на участие в закупке в формате MS Word.
    Техническое предложение заполняется участником с учетом требований технического задания.
    Характеристики товаров, работ, услуг должны быть изложены таким образом, чтобы при рассмотрении и оценке заявок не допускалось их неоднозначное толкование.
    
    === TABLE 1 ===
    Наименование товара | Ед.изм. | Количество (Объем) | Производитель/Изготовитель
    Указать наименование товара с указанием марки, и/или модели, и/или артикула, и/или технические условия. | Указать ед. изм. | Указать количество | Указать организационно-правовую форму
    Применяемая участником ставка НДС | Указать применяемую ставку
    Характеристики предлагаемых товаров | Участник должен перечислить характеристики товаров... Например: «длина товара: составляет ___ см».
    """
    ok, err = is_substantive_tz_text(form_text)
    assert not ok
    assert "нет закупаемых позиций" in err.lower() or "шаблон" in err.lower()


def test_normalize_procurement_profile_returns_empty_when_all_generic():
    from app.supplier_search import _normalize_procurement_profile

    raw = {
        "summary": "Товары по техническому заданию",
        "items": [
            {"id": "item-1", "name": "Товары по техническому заданию", "category_terms": ["материальные ресурсы"]},
            {"id": "item-2", "name": "Техническое предложение", "category_terms": ["форма"]},
            {"id": "item-3", "name": "Материальные ресурсы", "category_terms": ["снабжение"]},
        ],
    }
    profile = _normalize_procurement_profile(raw)
    assert len(profile.items) == 0


def test_is_substantive_tz_text_job_889_real_file():
    from pathlib import Path
    from app.document_parser import extract_text

    file_path = Path("/root/projects/tenderlex/storage/jobs/10908638692042789e67aeb0d94cf2db/input/Приложение _1.3 _Техническое предложение.docx")
    if not file_path.exists():
        pytest.skip("Job 889 input file not found on disk")
    text, status = extract_text(file_path)
    assert status == "ok"
    ok, err = is_substantive_tz_text(text)
    assert not ok
    assert "нет закупаемых позиций" in err.lower() or "шаблон" in err.lower()


def test_process_supplier_search_aborts_and_refunds_on_zero_items_profile(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.models import Job
    from app.supplier_search import ProcurementProfile
    from app.jobs import MODE_SUPPLIER_SEARCH, _process_supplier_search

    async def fake_build_profile(settings, context):
        return ProcurementProfile(summary="", items=(), excluded_terms=(), raw={})

    search_called = False

    async def fake_discover(*args, **kwargs):
        nonlocal search_called
        search_called = True
        return [], {}

    refund_called = False

    def fake_release(db, job, note=""):
        nonlocal refund_called
        refund_called = True

    monkeypatch.setattr("app.jobs.build_procurement_profile", fake_build_profile)
    monkeypatch.setattr("app.jobs.discover_suppliers", fake_discover)
    monkeypatch.setattr("app.jobs.release_job_reservation", fake_release)

    db = MagicMock()
    job = Job(id="test_job_123", mode=MODE_SUPPLIER_SEARCH, status="running", target_suppliers=10)
    settings = SimpleNamespace(has_active_ai_provider=True)

    _process_supplier_search(db, job, settings, "Текст документа без товаров")

    assert not search_called, "discover_suppliers should NOT have been called!"
    assert refund_called, "release_job_reservation should have been called!"
    assert job.status == "failed"
    assert "нет позиций" in (job.message or "").lower()
    assert "не найдено закупаемых товаров" in (job.error or "").lower()



