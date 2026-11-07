import pytest
from pathlib import Path
from app.price_monitoring.cleaner import (
    is_classifier_code,
    is_drawing_or_part_code,
    is_closed_factory_drawing,
    clean_nomenclature_name,
    build_commercial_search_queries,
)
from app.price_monitoring.extractor import (
    is_valid_domain,
    is_public_institution_buyer,
    is_reference_price_url,
)
from app.product_inventory import extract_structured_product_inventory
from app.exact_product.pipeline import prepare_exact_product_positions
from app.models import SystemSettings


def test_smeta_codes_classified_and_not_drawings():
    smeta_samples = [
        "ФСБЦ-12.1.01.05-0038",
        "12.1.01.03-0039",
        "08.1.02.07",
        "11.3.02.01",
        "09.4.03.01",
        "ФЕР-2001",
        "01.7.15.14-1046",
        "14.5.01.01-0012",
        "04.3.01.09-0015",
    ]
    for code in smeta_samples:
        assert is_classifier_code(code) is True, f"{code} should be classifier code"
        assert is_drawing_or_part_code(code) is False, f"{code} must NOT be treated as part drawing"
        assert is_closed_factory_drawing(code) is False, f"{code} must NOT be closed drawing"


def test_genuine_factory_drawings_still_recognized():
    drawings = [
        "ЭГ.059.00.00-02",
        "1085.05.02",
        "SPGA4270-200-01",
        "D-08660",
        "2.607.019.435",
    ]
    for drw in drawings:
        assert is_classifier_code(drw) is False, f"{drw} is not classifier"
        assert is_drawing_or_part_code(drw) is True, f"{drw} must be drawing/part"


def test_clean_nomenclature_strips_smeta_prefixes():
    cases = [
        (
            "11.3.02.01 Блок оконный ПВХ, двустворчатый, глухая и поворотно-откидная створки",
            "Блок оконный ПВХ, двустворчатый, глухая и поворотно-откидная створки",
        ),
        (
            "ФСБЦ-12.1.01.05-0038 Желоб оцинкованный Ø185 мм, длина 3000 мм (Позиции 44 и 50: 50 + 8)",
            "Желоб оцинкованный Ø185 мм, длина 3000 мм",
        ),
        (
            "Код сметы: ФСБЦ-08.1.02.07-0034 Планка ендовы верхняя с покрытием",
            "Планка ендовы верхняя с покрытием",
        ),
        (
            "12.1.01.03-0039 Плёнка подкровельная гидроизоляционная антиконденсатная",
            "Плёнка подкровельная гидроизоляционная антиконденсатная",
        ),
    ]
    for raw, expected in cases:
        assert clean_nomenclature_name(raw) == expected


def test_commercial_queries_do_not_quote_smeta_codes():
    raw = "11.3.02.01 Блок оконный ПВХ, двустворчатый"
    clean = clean_nomenclature_name(raw)
    queries = build_commercial_search_queries(clean, "шт")
    assert clean == "Блок оконный ПВХ, двустворчатый"
    assert all("11.3.02.01" not in q for q in queries)
    assert any("Блок оконный" in q for q in queries)


def test_smeta_and_gov_domains_blocked():
    blocked_urls = [
        "https://cs.smetnoedelo.ru/fsbcm/fsbcm11.3.02.01-0018.html",
        "https://fgisrf.ru/fsscm/fsscm12.1.01.03-0039.html",
        "https://classinform.ru/ksr2/23.99.12.html",
        "https://fixedassets.ru/Classificators/KSR/2024",
        "https://szvo.gov35.ru/files/file_download.jsp",
        "https://zakaz.etp-region.ru/fx/gpms/etpGetFile",
        "https://kapremontkbr.ru/docs/smeta.xlsx",
        "https://minfin09.ru/wp-content/uploads/doc.pdf",
    ]
    for url in blocked_urls:
        assert is_valid_domain(url) is False, f"{url} must be blocked"
        assert is_reference_price_url(url) is True or is_valid_domain(url) is False


def test_public_institutions_rejected_as_suppliers():
    institutions = [
        'ООО "БУЗ ВО "ЦЕНТР ПО ПРОФИЛАКТИКЕ ИНФЕКЦИОННЫХ ЗАБОЛЕВАНИЙ"',
        'ООО "НФ "РОКРМД КБР"',
        'БУЗ УР "Глазовская РБ МЗ УР"',
        'ГАУ РБ "Молочная кухня"',
        'Фонд капитального ремонта МКД',
    ]
    for name in institutions:
        assert is_public_institution_buyer(name) is True, f"{name} must be detected as public institution"

    commercial = [
        'ООО "ДЖИФЛЕКС"',
        'ООО ГК "ИЗОЛ-ПРОФИ"',
        'ООО "ПАРТНЕР"',
        'ООО "ЛАКОЛЮКС"',
    ]
    for name in commercial:
        assert is_public_institution_buyer(name) is False, f"{name} is commercial company"


def test_structured_inventory_extracts_smeta_table_docx():
    kitchen_path = Path("/root/projects/tenderlex/storage/jobs/7ea9ddb65b184c0583d64655852f5a1c/input/spisok_zakupok_kukhnya _1.docx")
    if kitchen_path.exists():
        rows = extract_structured_product_inventory([kitchen_path])
        assert rows is not None
        assert len(rows) >= 100
        first_row = rows[0]
        assert "Желоб оцинкованный" in first_row["name"]
        assert first_row["unit"] == "шт"
        assert first_row["quantity"] == "58"


@pytest.mark.asyncio
async def test_prepare_exact_product_positions_short_text():
    settings = SystemSettings()
    # 20 characters, exactly like task 1037
    short_query = "Окна пластиковые ПВХ"
    positions = await prepare_exact_product_positions(settings, context=short_query, input_files=None)
    assert len(positions) >= 1
    assert "Окна пластиковые ПВХ" in positions[0]["name"]
    assert positions[0].get("is_short_prompt") is True


def test_build_selection_snapshot_short_prompt_flag():
    import json
    from app.position_selection import build_selection_snapshot

    # Короткий запрос без характеристик (кейс клиента 80 / задача 1037)
    items = [{"position_no": 1, "name": "Окна пластиковые ПВХ", "requirements": []}]
    raw_snapshot = build_selection_snapshot(items, price_kopeks=4900, mode="exact_product")
    snapshot = json.loads(raw_snapshot)
    assert snapshot.get("has_short_prompt") is True
    assert snapshot["items"][0].get("is_short_prompt") is True

    # Полноценная позиция со спецификацией
    full_items = [{
        "position_no": 1,
        "name": "Окно ПВХ двухстворчатое 1300х1400",
        "requirements": [{"param_name": "Ширина", "tz_requirement": "1300 мм"}]
    }]
    full_raw = build_selection_snapshot(full_items, price_kopeks=4900, mode="exact_product")
    full_snap = json.loads(full_raw)
    assert full_snap.get("has_short_prompt") is False


