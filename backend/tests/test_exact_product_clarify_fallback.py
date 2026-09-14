import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.exact_product import (
    ExactProductPosition,
    SpecParameterMatch,
    _is_placeholder_brand_or_model,
    resolve_clarify_parameters,
)
from app.models import SystemSettings


def test_is_placeholder_brand_or_model():
    assert _is_placeholder_brand_or_model("") is True
    assert _is_placeholder_brand_or_model("В открытой документации не указано") is True
    assert _is_placeholder_brand_or_model("требуется официальный паспорт завода") is True
    assert _is_placeholder_brand_or_model("не указано") is True
    assert _is_placeholder_brand_or_model("отечественный производитель") is True
    assert _is_placeholder_brand_or_model("по спецификации") is True
    assert _is_placeholder_brand_or_model("ООО «Прессмакс»") is False
    assert _is_placeholder_brand_or_model("ПГП-4 (Мини)") is False
    assert _is_placeholder_brand_or_model("ЗиМ") is False


@pytest.mark.asyncio
async def test_resolve_clarify_parameters_uses_clean_name_and_specs():
    settings = MagicMock()
    settings.has_active_ai_provider = True
    settings.yandex_search_price_per_request = 0.04

    pos = ExactProductPosition(
        position_no=2,
        name_in_tz="Вертикальный гидравлический пресс для отходов",
        identified_brand="В открытой документации не указано (требуется официальный паспорт завода)",
        identified_model="В открытой документации не указано",
        manufacturer="В открытой документации не указано",
        confidence=0.5,
        reasoning="Оборудование из комплектации",
        specs_breakdown=[
            SpecParameterMatch(
                param_name="Габариты пресса",
                tz_requirement="2000*950*450 мм",
                product_fact="В открытой документации не указано",
                status="clarify",
            )
        ],
    )

    captured_queries = []

    async def mock_yandex_search(stgs, queries, **kwargs):
        captured_queries.extend(queries)
        return [], 1

    with patch("app.exact_product._yandex_credentials", return_value=("mock_folder", "mock_key")), \
         patch("app.exact_product._search_with_yandex", side_effect=mock_yandex_search):
        resolved, cost = await resolve_clarify_parameters(
            settings=settings,
            positions=[pos],
            existing_urls=set(),
            web_sources=[],
            verified_docs=[],
            max_sub_queries=2,
        )

    assert len(captured_queries) > 0
    query = captured_queries[0]
    # Verify that placeholder words are NOT present in the search query
    assert "не указано" not in query.lower()
    assert "требуется официальный паспорт" not in query.lower()
    # Verify that the actual name in TZ and dimensions ARE present
    assert "Вертикальный гидравлический пресс" in query
    assert "2000*950*450" in query
