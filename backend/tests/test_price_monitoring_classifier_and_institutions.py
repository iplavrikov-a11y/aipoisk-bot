import pytest
from app.price_monitoring.cleaner import is_classifier_code, is_drawing_or_part_code, is_closed_factory_drawing
from app.price_monitoring.extractor import is_public_institution_buyer, is_valid_domain


def test_is_classifier_code():
    # Classifier names and codes must be identified
    assert is_classifier_code("ОКПД2") is True
    assert is_classifier_code("окпд") is True
    assert is_classifier_code("КТРУ") is True
    assert is_classifier_code("ТН ВЭД") is True
    assert is_classifier_code("31.01.12.160") is True
    assert is_classifier_code("31.01.12.160-00000005") is True
    assert is_classifier_code("26.51.66.120-00000001") is True

    # Real models, drawings, and SKUs must NOT be identified as classifier codes
    assert is_classifier_code("GEARSEN CD 2060") is False
    assert is_classifier_code("ВМЗ Ш-150") is False
    assert is_classifier_code("8БС.370.544-1") is False
    assert is_classifier_code("D-08660") is False
    assert is_classifier_code("S04H624101SA") is False


def test_classifier_codes_excluded_from_drawing_detection():
    # OKPD2 and KTRU strings must never be treated as factory drawings or part codes
    assert is_drawing_or_part_code("ОКПД2") is False
    assert is_drawing_or_part_code("31.01.12.160") is False
    assert is_drawing_or_part_code("31.01.12.160-00000005") is False
    assert is_closed_factory_drawing("31.01.12.160-00000005") is False

    # Real industrial part codes and drawings must still be recognized
    assert is_drawing_or_part_code("ВМЗ Ш-150") is True
    assert is_drawing_or_part_code("8БС.370.544-1") is True
    assert is_drawing_or_part_code("D-08660") is True


def test_is_public_institution_buyer():
    # Budgetary, governmental, and healthcare buyers must be blocked
    assert is_public_institution_buyer('ГБУ РО "ЦРБ" В КРАСНОСУЛИНСКОМ РАЙОНЕ') is True
    assert is_public_institution_buyer('ГБУЗ ЯНАО "МУЖЕВСКАЯ ЦРБ"') is True
    assert is_public_institution_buyer('МКУ "Управление благоустройства"') is True
    assert is_public_institution_buyer('Администрация города Казани') is True
    assert is_public_institution_buyer('ФГБУ "НМИЦ им. Алмазова"') is True
    assert is_public_institution_buyer('МБОУ СОШ № 5') is False  # school abbreviations without target markers

    # Commercial entities must NOT be flagged
    assert is_public_institution_buyer('ООО "Мебельная фабрика"') is False
    assert is_public_institution_buyer('АО "КВАРТ"') is False
    assert is_public_institution_buyer('ИП Ковалев Олег Игоревич') is False
    assert is_public_institution_buyer('ООО "СБС"') is False


def test_tender_platforms_blocked_in_price_monitoring():
    # Tender aggregators and ETPs must be rejected
    assert is_valid_domain("https://www.roseltorg.ru/procedure/0358300054026000145/1") is False
    assert is_valid_domain("https://star-pro.ru/kategorii/mebel/stulya") is False
    assert is_valid_domain("https://otc.ru/marketplace-b2b/offer/ktru-31-01-12-160-00000005-kreslo/22229639") is False
    assert is_valid_domain("https://torgkey.ru/ktru-okpd2/31.01.11.150-00000003/") is False
    assert is_valid_domain("https://sberbank-ast.ru/procedure.aspx") is False

    # Normal commercial store must be accepted
    assert is_valid_domain("https://www.kreslo-v-ofis.ru/catalog/kresla/kreslo-ofisnoe.html") is True
