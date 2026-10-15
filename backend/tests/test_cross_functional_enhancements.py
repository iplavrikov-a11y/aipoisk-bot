from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.models import SystemSettings
from app.supplier_search import (
    Candidate,
    build_universal_negative_keywords,
    _is_grounded_in_text,
    extract_internal_links,
    html_text_to_page,
    _candidate_score,
)
from app.exact_product import (
    ExactProductPosition,
    AlternativeProduct,
    SpecParameterMatch,
    GispRegistryMatch,
    analyze_exact_product,
    fetch_batch_web_documents,
)


def test_supplier_search_universal_negative_keywords():
    tz = "Техническое задание на поставку автоматического выключателя и электрического привода."
    negatives = build_universal_negative_keywords(tz)
    assert "б/у" in negatives
    assert "неликвид" in negatives
    assert "полуавтоматический" in negatives
    assert "дизельный" in negatives
    assert "ручной" in negatives


def test_supplier_search_grounding_verification():
    doc_text = "Насос центробежный многоступенчатый 2.2 кВт, степень защиты IP67, климатическое исполнение УХЛ4."
    assert _is_grounded_in_text("2.2 кВт", doc_text) is True
    assert _is_grounded_in_text("IP67", doc_text) is True
    assert _is_grounded_in_text("УХЛ4", doc_text) is True
    assert _is_grounded_in_text("999 кВт", doc_text) is False


def test_supplier_search_extract_internal_links_pdf_boost():
    html = """
    <html>
      <body>
        <a href="/contacts">Контакты</a>
        <a href="/catalog/price.pdf">Скачать прайс-лист PDF</a>
        <a href="/datasheet_manual.pdf">Паспорт изделия</a>
        <a href="/about">О компании</a>
      </body>
    </html>
    """
    links = extract_internal_links(html, "https://zavod-nasos.ru")
    assert any("price.pdf" in link for link in links)
    assert any("datasheet_manual.pdf" in link for link in links)
    assert any("contacts" in link for link in links)


def test_supplier_search_html_structured_table_extraction():
    html = """
    <html>
      <body>
        <h1>Каталог продукции</h1>
        <table>
          <tr><th>Модель</th><th>Мощность</th><th>Цена</th></tr>
          <tr><td>НЦ-100</td><td>5.5 кВт</td><td>45 000 руб</td></tr>
          <tr><td>НЦ-200</td><td>11 кВт</td><td>85 000 руб</td></tr>
        </table>
        <div class="product-specs">
          <dl class="spec-list">
            <dt>Рабочая температура</dt>
            <dd>-40 до +60 C</dd>
          </dl>
        </div>
        <p>Телефон: +7 (495) 123-45-67, email: info@zavod.ru</p>
      </body>
    </html>
    """
    page = html_text_to_page(html, "https://zavod.ru/catalog")
    assert page is not None
    assert "[ТАБЛИЦА ПРОДУКЦИИ/ХАРАКТЕРИСТИК" in page["text"]
    assert "НЦ-100 | 5.5 кВт | 45 000 руб" in page["text"]
    assert "[БЛОК ПАРАМЕТРОВ]" in page["text"] or "-40 до +60" in page["text"]
    assert "+7 (495) 123-45-67" in page["text"]
    assert "info@zavod.ru" in page["text"]


def test_supplier_search_candidate_score_negative_penalty():
    cand_clean = Candidate(
        url="https://zavod-privod.ru",
        domain="zavod-privod.ru",
        title="Официальный завод приводной техники",
        snippet="Производство электрических приводов и редукторов.",
        source="yandex",
        query="электрический привод",
    )
    cand_used = Candidate(
        url="https://bu-stanki.ru",
        domain="bu-stanki.ru",
        title="Продажа б/у приводов и неликвидов",
        snippet="Дизельный привод б/у с хранения и аренда техники.",
        source="yandex",
        query="электрический привод",
    )
    context = "Поставка электрического привода 5.5 кВт."
    score_clean = _candidate_score(cand_clean, context)
    score_used = _candidate_score(cand_used, context)
    assert score_clean > score_used
    assert score_used < 0 or score_clean - score_used >= 15


@pytest.mark.asyncio
async def test_exact_product_position_dadata_enrichment():
    pos = ExactProductPosition(
        position_no=1,
        name_in_tz="Насос",
        identified_brand="ЭнергоМаш",
        identified_model="НЦ-50",
        manufacturer="АО Завод ЭнергоМаш",
        confidence=0.95,
        reasoning="Соответствует ТЗ",
        inn="7701234567",
        region="г. Москва",
    )
    d = pos.to_dict()
    assert d.get("inn") == "7701234567"
    assert d.get("region") == "г. Москва"

    alt = AlternativeProduct(
        brand="ГидроМаш",
        model="ГМ-50",
        manufacturer="ООО Завод ГидроМаш",
        inn="7801234567",
        region="г. Санкт-Петербург",
    )
    d_alt = alt.to_dict()
    assert d_alt.get("inn") == "7801234567"
    assert d_alt.get("region") == "г. Санкт-Петербург"


@pytest.mark.asyncio
async def test_exact_product_batch_web_documents_dns_filter():
    urls = [
        "https://example.com/spec.html",
        "https://invalid-non-existent-domain-123456789.ru/doc.pdf",
    ]
    async def fake_dns(u):
        return "example.com" in u

    with patch("app.exact_product.candidate_domain_resolves_fast", side_effect=fake_dns):
        with patch("app.exact_product.fetch_web_or_pdf_document", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"url": "https://example.com/spec.html", "text": "Спецификация"}
            docs = await fetch_batch_web_documents(urls, max_docs=2)
            assert len(docs) == 1
            assert mock_fetch.call_count == 1
