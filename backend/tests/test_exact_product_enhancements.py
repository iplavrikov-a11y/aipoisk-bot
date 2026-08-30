from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from app.models import SystemSettings
from app.exact_product import (
    extract_standards_from_text,
    resolve_clarify_parameters,
    resolve_standards_parameters,
    find_minprom_gisp_match,
    fetch_web_or_pdf_document,
    SpecParameterMatch,
    ExactProductPosition,
)


def test_extract_standards_from_text():
    sample_text = (
        "Кабель изготовлен по ГОСТ 31996-2012 с жилами по ГОСТ 22483-2021. "
        "Трубы по ГОСТ 18599-2001 (ПЭ 100 SDR 17). Балка по СТО АСЧМ 20-93 или ГОСТ Р 57837-2017. "
        "Коагулянт по ТУ 2163-069-00205067-2007 и ГОСТ Р 58580-2019."
    )
    standards = extract_standards_from_text(sample_text)
    assert any("31996-2012" in s for s in standards)
    assert any("22483-2021" in s for s in standards)
    assert any("18599-2001" in s for s in standards)
    assert any("57837-2017" in s for s in standards)
    assert any("58580-2019" in s for s in standards)
    assert any("20-93" in s for s in standards)


@pytest.mark.asyncio
async def test_resolve_clarify_parameters_success():
    settings = SystemSettings()
    settings.yandex_search_api_key = "test_key"
    settings.yandex_search_folder_id = "test_folder"
    settings.custom_ai_providers_json = '[{"id": "p1", "baseUrl": "http://mock-ai", "apiKey": "token"}]'

    spec = SpecParameterMatch(
        param_name="Рабочее давление",
        tz_requirement="1.4 - 1.6 МПа",
        product_fact="В открытой документации не указано",
        status="clarify",
        comment="Требуется уточнение по паспорту завода",
    )
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Огнетушитель ОП-4",
        identified_brand="Пожтехника",
        identified_model="ОП-4(з) МИГ",
        manufacturer="ЗАО Пожтехника",
        confidence=0.95,
        reasoning="Тест",
        specs_breakdown=[spec],
    )

    mock_llm_json = '{"found": true, "product_fact": "1.5 МПа при 20°С", "status": "match", "comment": "Подтверждено паспортом изделия МИГ"}'
    mock_candidates = [MagicMock(url="https://pozhtechnika.ru/pasport.pdf", domain="pozhtechnika.ru", title="Паспорт ОП-4 МИГ")]
    mock_docs = [{"url": "https://pozhtechnika.ru/pasport.pdf", "type": "pdf", "title": "Паспорт ОП-4", "text": "Рабочее давление в корпусе: 1.5 МПа при 20 градусах"}]

    with patch("app.exact_product._search_with_yandex", AsyncMock(return_value=(mock_candidates, 1))), \
         patch("app.exact_product.fetch_batch_web_documents", AsyncMock(return_value=mock_docs)), \
         patch("app.exact_product.call_llm", AsyncMock(return_value=mock_llm_json)):
        
        resolved_count, cost = await resolve_clarify_parameters(
            settings=settings,
            positions=[pos],
            existing_urls=set(),
            web_sources=[],
            verified_docs=[],
        )

        assert resolved_count == 1
        assert spec.status == "match"
        assert spec.product_fact == "1.5 МПа при 20°С"
        assert "паспортом" in spec.comment.lower()


@pytest.mark.asyncio
async def test_resolve_standards_parameters_success():
    settings = SystemSettings()
    settings.yandex_search_api_key = "test_key"
    settings.yandex_search_folder_id = "test_folder"
    settings.custom_ai_providers_json = '[{"id": "p1", "baseUrl": "http://mock-ai", "apiKey": "token"}]'

    spec = SpecParameterMatch(
        param_name="Относительное удлинение при разрыве",
        tz_requirement="не менее 350%",
        product_fact="В открытой документации не указано",
        status="clarify",
        comment="Требуется уточнение по ГОСТ",
    )
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Труба ПЭ 100",
        identified_brand="НФ Инжиниринг",
        identified_model="ПЭ 100 SDR 17 d110 ГОСТ 18599-2001",
        manufacturer="НФ Инжиниринг",
        confidence=0.98,
        reasoning="Тест ГОСТ",
        specs_breakdown=[spec],
    )

    mock_llm_json = '{"found": true, "product_fact": "не менее 350%", "status": "match", "comment": "Соответствует ГОСТ 18599-2001 Таблица 4"}'
    mock_candidates = [MagicMock(url="https://standartgost.ru/gost_18599", domain="standartgost.ru", title="ГОСТ 18599-2001")]
    mock_docs = [{"url": "https://standartgost.ru/gost_18599", "type": "html", "title": "ГОСТ 18599", "text": "Относительное удлинение при разрыве для ПЭ 100 составляет не менее 350%"}]

    with patch("app.exact_product._search_with_yandex", AsyncMock(return_value=(mock_candidates, 1))), \
         patch("app.exact_product.fetch_batch_web_documents", AsyncMock(return_value=mock_docs)), \
         patch("app.exact_product.call_llm", AsyncMock(return_value=mock_llm_json)):
        
        resolved_count, cost = await resolve_standards_parameters(
            settings=settings,
            positions=[pos],
            context="Труба ПНД по ГОСТ 18599-2001",
            existing_urls=set(),
            web_sources=[],
            verified_docs=[],
        )

        assert resolved_count == 1
        assert spec.status == "match"
        assert spec.product_fact == "не менее 350%"


@pytest.mark.asyncio
async def test_fetch_web_or_pdf_document_antibot_browser_fallback():
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html>KillBot protected</html>"
    mock_response.url = "https://novovek.ru/dku-100"

    client = MagicMock()
    client.get = AsyncMock(return_value=mock_response)

    mock_browser_page = {
        "url": "https://novovek.ru/dku-100",
        "text": "Светильник ДКУ 100. Мощность 100 Вт. Световой поток 14200 лм. Световая отдача 142 лм/Вт. Степень защиты IP66.",
    }

    with patch("app.procurement_sources.fetch_source_page_with_browser", AsyncMock(return_value=mock_browser_page)):
        doc = await fetch_web_or_pdf_document(client, "https://novovek.ru/dku-100")
        assert doc is not None
        assert doc["type"] == "html_browser"
        assert "14200 лм" in doc["text"]


def test_extract_relevant_spec_excerpts():
    from app.exact_product import _extract_relevant_spec_excerpts

    # Create dummy long doc (30,000 chars) where target parameter is at char 20,000
    padding = "Раздел описания оборудования и истории завода. " * 300
    target_section = "Таблица 5. Световой поток светильника ДКУ составляет 14200 лм при коэффициенте мощности 0.98. Пульсация 0.8%."
    long_doc = padding[:20000] + target_section + padding[:10000]

    excerpt = _extract_relevant_spec_excerpts(long_doc, "Световой поток", max_total_chars=12000)
    assert "14200 лм" in excerpt
    assert "коэффициенте мощности" in excerpt


@pytest.mark.asyncio
async def test_resolve_clarify_pre_doc_resolution():
    from app.exact_product import resolve_clarify_parameters

    settings = SystemSettings()
    settings.yandex_search_api_key = "key"
    settings.yandex_search_folder_id = "folder"
    settings.custom_ai_providers_json = '[{"id": "p1", "baseUrl": "http://mock", "apiKey": "t"}]'

    spec = SpecParameterMatch(
        param_name="Степень защиты",
        tz_requirement="не менее IP66",
        product_fact="В открытой документации не указано",
        status="clarify",
        comment="Требуется паспорт",
    )
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Светильник уличный",
        identified_brand="Нововек",
        identified_model="ДКУ 100",
        manufacturer="ООО Нововек",
        confidence=0.95,
        reasoning="Тест",
        specs_breakdown=[spec],
    )

    verified_docs = [
        {
            "url": "https://novovek.ru/doc.pdf",
            "title": "Паспорт ДКУ",
            "text": "Технические характеристики светильника ДКУ 100: Мощность 100 Вт, Степень защиты корпуса IP66 по ГОСТ 14254.",
        }
    ]

    mock_llm_json = '{"found": true, "product_fact": "IP66", "status": "match", "comment": "Подтверждено паспортом ДКУ"}'

    with patch("app.exact_product.call_llm", AsyncMock(return_value=mock_llm_json)), \
         patch("app.exact_product._search_with_yandex") as mock_yandex:
        
        resolved, cost = await resolve_clarify_parameters(
            settings=settings,
            positions=[pos],
            existing_urls=set(),
            web_sources=[],
            verified_docs=verified_docs,
        )

        assert resolved == 1
        assert spec.status == "match"
        assert spec.product_fact == "IP66"
        # Since it was resolved from verified_docs, external search was NOT called!
        assert mock_yandex.call_count == 0


def test_is_grounded_in_text():
    from app.exact_product import _is_grounded_in_text

    doc_text = "Светильник светодиодный ДКУ 100 Вт, световой поток 14000 лм, степень защиты IP66, УХЛ1."
    
    # Positive grounding
    assert _is_grounded_in_text("14 000 лм", doc_text) is True
    assert _is_grounded_in_text("IP66", doc_text) is True
    assert _is_grounded_in_text("УХЛ1", doc_text) is True
    assert _is_grounded_in_text("100 Вт", doc_text) is True

    # Negative ungrounded hallucination
    assert _is_grounded_in_text("22 500 лм", doc_text) is False
    assert _is_grounded_in_text("IP68", doc_text) is False
    assert _is_grounded_in_text("УХЛ4", doc_text) is False


@pytest.mark.asyncio
async def test_grounded_rejection_of_hallucination():
    from app.exact_product import resolve_clarify_parameters

    settings = SystemSettings()
    settings.yandex_search_api_key = "key"
    settings.yandex_search_folder_id = "folder"
    settings.custom_ai_providers_json = '[{"id": "p1", "baseUrl": "http://mock", "apiKey": "t"}]'

    spec = SpecParameterMatch(
        param_name="Световой поток",
        tz_requirement="не менее 14000 лм",
        product_fact="В открытой документации не указано",
        status="clarify",
        comment="Требуется паспорт",
    )
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Светильник уличный",
        identified_brand="Нововек",
        identified_model="ДКУ 100",
        manufacturer="ООО Нововек",
        confidence=0.95,
        reasoning="Тест",
        specs_breakdown=[spec],
    )

    verified_docs = [
        {
            "url": "https://novovek.ru/doc.pdf",
            "title": "Паспорт ДКУ",
            "text": "Светильник ДКУ 100: Мощность 100 Вт. Напряжение 220 В.",
        }
    ]

    # LLM hallucinates 14500 lm which is NOT in verified_docs!
    mock_hallucinated_json = '{"found": true, "product_fact": "14 500 лм", "status": "match", "comment": "Выдумано"}'

    with patch("app.exact_product.call_llm", AsyncMock(return_value=mock_hallucinated_json)), \
         patch("app.exact_product._search_with_yandex", AsyncMock(return_value=([], 0))):
        
        resolved, cost = await resolve_clarify_parameters(
            settings=settings,
            positions=[pos],
            existing_urls=set(),
            web_sources=[],
            verified_docs=verified_docs,
        )

        # Must be rejected because 14500 is NOT in verified_docs!
        assert resolved == 0
        assert spec.status == "clarify"
        assert spec.product_fact == "В открытой документации не указано"


@pytest.mark.asyncio
async def test_auto_fill_ai_recommendations_with_llm():
    from app.exact_product import auto_fill_ai_recommendations

    settings = SystemSettings()
    settings.custom_ai_providers_json = '[{"id": "p1", "baseUrl": "http://mock", "apiKey": "t"}]'

    spec = SpecParameterMatch(
        param_name="Относительное удлинение при разрыве",
        tz_requirement="не менее 500%",
        product_fact="В открытой документации не указано (требуется паспорт завода)",
        status="clarify",
        comment="Требуется официальный паспорт завода",
    )
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Мастика полиуретановая",
        identified_brand="ТЕХНОНИКОЛЬ",
        identified_model="ТЕХНОНИКОЛЬ 21",
        manufacturer="ТЕХНОНИКОЛЬ",
        confidence=0.95,
        reasoning="Тест",
        specs_breakdown=[spec],
    )

    mock_res_json = json.dumps([
        {
            "param_name": "Относительное удлинение при разрыве",
            "recommended_fact": "550%",
            "comment": "Подобрано ИИ под требование ТЗ. В открытых источниках параметр не опубликован — требуется уточнить по паспорту или официальному документу производителя перед подачей заявки.",
        }
    ])

    with patch("app.exact_product.call_llm", AsyncMock(return_value=mock_res_json)):
        filled = await auto_fill_ai_recommendations(settings, [pos])

        assert filled == 1
        assert spec.product_fact == "550%"
        assert spec.status == "clarify"
        assert "уточнить по паспорту" in spec.comment.lower()


@pytest.mark.asyncio
async def test_auto_fill_ai_recommendations_fallback():
    from app.exact_product import auto_fill_ai_recommendations

    settings = SystemSettings()
    # No AI provider -> uses clean_tz fallback
    settings.custom_ai_providers_json = "[]"

    spec = SpecParameterMatch(
        param_name="Время высыхания до отлипа",
        tz_requirement="не более 24 часов",
        product_fact="В открытой документации не указано (требуется паспорт завода)",
        status="clarify",
        comment="Требуется официальный паспорт завода",
    )
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Мастика полиуретановая",
        identified_brand="ТЕХНОНИКОЛЬ",
        identified_model="ТЕХНОНИКОЛЬ 21",
        manufacturer="ТЕХНОНИКОЛЬ",
        confidence=0.95,
        reasoning="Тест",
        specs_breakdown=[spec],
    )

    filled = await auto_fill_ai_recommendations(settings, [pos])

    assert filled == 1
    assert spec.product_fact == "24 часов"
    assert spec.status == "clarify"
    assert "уточнить по паспорту" in spec.comment.lower()



