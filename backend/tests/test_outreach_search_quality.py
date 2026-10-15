from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import SystemSettings
from app.outreach_models import OutreachLead, OutreachSearchTask
from app.outreach_search import (
    OutreachCandidate,
    ai_rerank_outreach_candidates,
    ai_review_outreach_lead,
    enrich_lead_with_dadata,
    generate_search_queries_matrix,
)


@pytest.mark.asyncio
async def test_generate_search_queries_matrix_commercial_terms():
    settings = SystemSettings(id=1)
    prompt = "Поставщики кабеля и провода"
    queries, cost = await generate_search_queries_matrix(prompt, count=20, sys_settings=settings)
    assert len(queries) >= 10
    assert any("кабел" in q.lower() or "провод" in q.lower() for q in queries)


@pytest.mark.asyncio
async def test_ai_rerank_filters_out_irrelevant_domains():
    settings = SystemSettings(id=1, custom_ai_providers_json='[{"id":"ai","baseUrl":"https://test/v1","apiKey":"k"}]')
    
    candidates = [
        OutreachCandidate(url="https://sberbank.ru", domain="sberbank.ru", title="СберБанк - кредиты и банковские гарантии 44-ФЗ", snippet="Оформление банковских гарантий"),
        OutreachCandidate(url="https://kursy44.ru", domain="kursy44.ru", title="Курсы госзакупок и тендеров", snippet="Обучение специалистов по закупкам"),
        OutreachCandidate(url="https://kabel-zavod.ru", domain="kabel-zavod.ru", title="Кабельный завод Волга - производство кабеля ВВГнг", snippet="Оптовые поставки силового кабеля со склада от производителя"),
    ]
    
    mock_llm_resp = """[
        {"index": 0, "is_supplier": false, "confidence": 10, "reason": "Банк и финансовые услуги"},
        {"index": 1, "is_supplier": false, "confidence": 10, "reason": "Обучающие курсы"},
        {"index": 2, "is_supplier": true, "confidence": 95, "reason": "Завод производитель кабеля"}
    ]"""
    
    with patch("app.outreach_search.call_llm", new=AsyncMock(return_value=mock_llm_resp)):
        approved, cost = await ai_rerank_outreach_candidates(candidates, "Кабельные заводы и поставщики", settings)
        assert len(approved) == 1
        assert approved[0].domain == "kabel-zavod.ru"
        assert approved[0].ai_rank_confidence == 95


@pytest.mark.asyncio
async def test_ai_review_lead_acceptance_and_rejection():
    settings = SystemSettings(id=1, custom_ai_providers_json='[{"id":"ai","baseUrl":"https://test/v1","apiKey":"k"}]')
    
    valid_crawled = {
        "email": "sales@kabel-zavod.ru",
        "company_name": "Кабельный Завод",
        "website": "https://kabel-zavod.ru",
        "plain_text": "Производство и оптовая продажа силового кабеля ВВГ, КГ, АВВГ. Прайс-лист на кабель со склада.",
        "page_title": "Кабельный завод Волга",
        "activity_profile": "Кабельный завод",
    }
    
    mock_accept = """{
        "is_relevant": true,
        "score": 90,
        "site_type": "manufacturer",
        "activity_profile": "Производитель силового кабеля",
        "reason": "Завод выпускает кабельную продукцию"
    }"""
    
    with patch("app.outreach_search.call_llm", new=AsyncMock(return_value=mock_accept)):
        accepted, cost = await ai_review_outreach_lead(valid_crawled, "Поставщики кабеля", settings)
        assert accepted is not None
        assert accepted["relevance_score"] == 90
        assert accepted["site_type"] == "manufacturer"

    mock_reject = """{
        "is_relevant": false,
        "score": 15,
        "site_type": "unrelated",
        "activity_profile": "Финансовый брокер",
        "reason": "Не является поставщиком кабеля"
    }"""
    
    with patch("app.outreach_search.call_llm", new=AsyncMock(return_value=mock_reject)):
        rejected, cost = await ai_review_outreach_lead(valid_crawled, "Поставщики кабеля", settings)
        assert rejected is None


@pytest.mark.asyncio
async def test_enrich_lead_with_dadata_filters_and_enriches():
    lead = {
        "inn": "7701234567",
        "company_name": "kabel-zavod.ru",
        "email": "info@kabel.ru",
    }
    
    # 1. Active manufacturing company -> Accept and enrich
    mock_active = {
        "inn": "7701234567",
        "company_name": "ООО 'КАБЕЛЬ СНАБ'",
        "status": "ACTIVE",
        "okved": "27.32",
        "management_name": "Иванов Иван Иванович",
        "city": "г Москва",
        "legal_address": "г Москва, ул Ленина 1",
    }
    with patch("app.outreach_search.enrich_company_by_inn", new=AsyncMock(return_value=mock_active)):
        res = await enrich_lead_with_dadata(dict(lead))
        assert res is not None
        assert res["company_name"] == "ООО 'КАБЕЛЬ СНАБ'"
        assert res["management_name"] == "Иванов Иван Иванович"

    # 2. Bankrupt / liquidated company -> Reject
    mock_liquidated = {
        "inn": "7701234567",
        "company_name": "ООО 'БАНКРОТ'",
        "status": "LIQUIDATED",
        "okved": "27.32",
    }
    with patch("app.outreach_search.enrich_company_by_inn", new=AsyncMock(return_value=mock_liquidated)):
        res = await enrich_lead_with_dadata(dict(lead))
        assert res is None

    # 3. Financial / Bank / Training OKVED -> Reject
    mock_bank_okved = {
        "inn": "7701234567",
        "company_name": "ООО 'ФИНАНС ГАРАНТ'",
        "status": "ACTIVE",
        "okved": "64.19",
    }
    with patch("app.outreach_search.enrich_company_by_inn", new=AsyncMock(return_value=mock_bank_okved)):
        res = await enrich_lead_with_dadata(dict(lead))
        assert res is None
