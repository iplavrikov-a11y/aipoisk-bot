import pytest
import json
from unittest.mock import AsyncMock, patch
from app.models import SystemSettings
from app.exact_product import (
    MAX_EXACT_POSITIONS_PER_JOB,
    MAX_YANDEX_QUERIES_PER_JOB,
    ExactProductPosition,
    SpecParameterMatch,
    analyze_exact_product,
    resolve_clarify_parameters,
    plan_exact_product_search,
)


@pytest.mark.asyncio
async def test_max_positions_limit_and_summary_note():
    settings = SystemSettings(
        custom_ai_providers_json=json.dumps([{
            "id": "mock",
            "name": "Mock AI",
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "mock-key",
            "model": "mock-model",
            "is_active": True,
        }])
    )

    # 5 positions returned by raw LLM
    mock_positions_json = {
        "summary": "Анализ спецификации оборудования",
        "positions": [
            {
                "position_no": i,
                "name_in_tz": f"Оборудование #{i}",
                "identified_brand": f"Завод #{i}",
                "identified_model": f"Модель-{i}00",
                "manufacturer": f"АО Завод #{i}",
                "confidence": 0.95,
                "reasoning": f"Соответствует ТЗ #{i}",
                "specs_breakdown": [
                    {
                        "param_name": "Мощность",
                        "tz_requirement": "10 кВт",
                        "product_fact": "10 кВт",
                        "status": "match",
                        "comment": "Подтверждено",
                    }
                ],
                "alternative_brands": [],
            }
            for i in range(1, 8)
        ],
    }

    with patch("app.exact_product.call_llm", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps(mock_positions_json)
        with patch("app.exact_product._search_with_yandex", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = ([], 0)

            report = await analyze_exact_product(
                settings=settings,
                context="Спецификация из 7 позиций оборудования",
                procurement_title="Комплексная закупка оборудования",
            )

            # Check that exactly MAX_EXACT_POSITIONS_PER_JOB (5) are retained
            assert len(report.positions) == MAX_EXACT_POSITIONS_PER_JOB
            assert report.total_positions == MAX_EXACT_POSITIONS_PER_JOB
            assert [p.position_no for p in report.positions] == [1, 2, 3, 4, 5]

            # Check that note is included in summary
            assert "обнаружено 7 позиций" in report.summary
            assert f"топ-{MAX_EXACT_POSITIONS_PER_JOB} ключевым позициям" in report.summary


@pytest.mark.asyncio
async def test_resolve_clarify_query_budget_cap():
    settings = SystemSettings(
        custom_ai_providers_json=json.dumps([{
            "id": "mock",
            "name": "Mock AI",
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "mock-key",
            "model": "mock-model",
            "is_active": True,
        }]),
        yandex_search_folder_id="mock-folder",
        yandex_search_api_key="mock-key",
    )

    positions = [
        ExactProductPosition(
            position_no=1,
            name_in_tz="Насос центробежный",
            identified_brand="ГМС Ливгидромаш",
            identified_model="К80-50-200",
            manufacturer="АО Ливгидромаш",
            confidence=0.9,
            reasoning="Соответствует ТЗ",
            specs_breakdown=[
                SpecParameterMatch(param_name=f"Параметр {i}", tz_requirement=f"Требование {i}", product_fact="", status="clarify")
                for i in range(1, 10)
            ],
            alternative_brands=[],
        )
    ]

    with patch("app.exact_product._search_with_yandex", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = ([], 1)
        with patch("app.exact_product.fetch_batch_web_documents", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            # Set max_sub_queries = 2
            resolved, cost = await resolve_clarify_parameters(
                settings=settings,
                positions=positions,
                existing_urls=set(),
                web_sources=[],
                verified_docs=[],
                max_sub_queries=2,
            )

            # mock_search should be called at most 2 times
            assert mock_search.call_count == 2
