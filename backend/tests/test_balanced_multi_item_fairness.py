from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import supplier_search
from app.models import SystemSettings
from app.supplier_search import (
    Candidate,
    CandidateRerank,
    MinpromRegistryContext,
    MinpromRegistryRequirement,
    ProcurementItem,
    ProcurementProfile,
    _balance_supplier_queries_across_items,
    _build_minprom_supplier_queries,
    _merge_supplier_query_tracks,
    _minprom_profile_query_terms,
    build_minprom_registry_queries,
    discover_suppliers,
)


def _marina_two_item_profile() -> ProcurementProfile:
    return ProcurementProfile(
        summary="Поставка калориметрической установки АБК-1В и устройства заправки кислородом УЗК-30м",
        items=(
            ProcurementItem(
                id="item-1",
                name="Калориметрическая установка",
                aliases=("Калориметр бомбовый АБК-1В", "Калориметрическая установка АБК-1В"),
                okpd2_codes=("26.51.41.130",),
                category_terms=(
                    "Лабораторное оборудование",
                    "Измерительные приборы",
                    "Аналитическое оборудование",
                    "Калориметры",
                ),
                exact_terms=("АБК-1В", "КБ-ЗУ", "выход RS-422"),
                included_sub_items=tuple(f"Комплектующая позиция {i}" for i in range(1, 27)),
            ),
            ProcurementItem(
                id="item-2",
                name="Устройство заправки кислородом",
                aliases=("УЗК-30м", "Устройство заправки кислородом"),
                okpd2_codes=("26.51.41.130",),
                category_terms=("Лабораторное вспомогательное оборудование", "Газовое оборудование"),
                exact_terms=("УЗК-30м",),
                included_sub_items=("Редуктор баллонный кислородный", "Трубки соединительные"),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_minprom_registry_queries_not_crowded_out_by_first_item_sub_items() -> None:
    profile = _marina_two_item_profile()
    req = MinpromRegistryRequirement(required=True, measure_type="restriction")
    settings = SimpleNamespace(has_active_ai_provider=True)

    async def fake_llm(*_args, **_kwargs) -> str:
        return '{"queries": ["калориметр бомбовый", "устройство заправки кислородом"]}'

    with patch.object(supplier_search, "call_llm", side_effect=fake_llm):
        queries = await build_minprom_registry_queries(settings, "ТЗ", profile, req)

    assert queries[0] == "Калориметрическая установка"
    assert queries[1] == "Устройство заправки кислородом"
    assert "УЗК-30м" in queries
    assert "Газовое оборудование" in queries
    assert len(queries) <= 32


def test_minprom_supplier_queries_and_merged_tracks_interleave_all_positions() -> None:
    profile = _marina_two_item_profile()
    reg_ctx = MinpromRegistryContext(
        requirement=MinpromRegistryRequirement(required=True, measure_type="restriction"),
        status="empty",
    )

    terms = _minprom_profile_query_terms(profile)
    assert any("калориметр" in t.lower() for t in terms[:2])
    assert any("кислород" in t.lower() or "узк-30м" in t.lower() for t in terms[:2])

    mp_queries = _build_minprom_supplier_queries(profile, reg_ctx, policy="minprom_registry_priority")
    assert any("калориметр" in q.lower() for q in mp_queries[:4])
    assert any("кислород" in q.lower() or "узк-30м" in q.lower() for q in mp_queries[:4])

    # Simulate AI returning 8 item-1 queries and only 1 item-2 query at the tail
    skewed_general = [
        "бомбовые калориметры производство рф",
        "автоматические калориметрические установки завод",
        "лабораторные приборы для определения теплоты сгорания",
        "калориметр для жидкого и твердого топлива",
        "калориметрическая бомба кб изготовитель",
        "оборудование для испытания топлива в лаборатории",
        "калориметрическая установка купить оптом",
        "комплектующие для бомбовых калориметров",
        "устройства для заправки кислородом баллонов",
    ]
    balanced_general = _balance_supplier_queries_across_items(skewed_general, profile, min_per_item=3)
    # Item 2 must have at least 3 dedicated queries and appear in the very first 4 queries
    item2_total = [q for q in balanced_general if "кислород" in q.lower() or "узк-30м" in q.lower()]
    assert len(item2_total) >= 3
    assert any("кислород" in q.lower() or "узк-30м" in q.lower() for q in balanced_general[:4])

    merged = _merge_supplier_query_tracks(balanced_general, mp_queries, profile=profile)
    # Even if Yandex stops after the first 8 queries, BOTH positions get strong coverage
    first_eight = merged[:8]
    assert sum(1 for q in first_eight if "кислород" in q.lower() or "узк-30м" in q.lower()) >= 3
    assert sum(1 for q in first_eight if "калориметр" in q.lower() or "абк-1в" in q.lower()) >= 3


@pytest.mark.asyncio
async def test_balanced_recovery_targets_zero_item_even_below_minimum_target() -> None:
    profile = _marina_two_item_profile()
    settings = SystemSettings(
        custom_ai_providers_json='[{"apiKey": "test-key", "baseUrl": "https://example.invalid/v1"}]'
    )

    discover_calls: list[list[str]] = []

    async def fake_build_queries(*_args, **_kwargs):
        return [
            "бомбовые калориметры производство рф",
            "устройства для заправки кислородом баллонов",
        ]

    async def fake_discover_candidates(_settings, queries, **_kwargs):
        discover_calls.append(list(queries))
        if len(discover_calls) == 1:
            # First pass returns ONLY 6 candidates for item-1 (below minimum_target=10)
            cands = [
                Candidate(
                    url=f"https://calor-{i}.ru",
                    domain=f"calor-{i}.ru",
                    title=f"Калориметры завод {i}",
                    snippet="Калориметрические установки АБК-1В",
                    source="yandex",
                    query=queries[0],
                    procurement_item_id="item-1",
                )
                for i in range(1, 7)
            ]
            return cands, {"yandex_requests_count": 1, "yandex_cost_rub": 0.03, "reports": []}
        # Recovery pass receives targeted item-2 queries and finds 4 item-2 suppliers
        cands = [
            Candidate(
                url=f"https://oxy-{i}.ru",
                domain=f"oxy-{i}.ru",
                title=f"Кислородная заправка завод {i}",
                snippet="Устройство заправки кислородом УЗК-30м",
                source="yandex",
                query=queries[0],
                procurement_item_id="item-2",
            )
            for i in range(1, 5)
        ]
        return cands, {"yandex_requests_count": 1, "yandex_cost_rub": 0.03, "reports": []}

    async def fake_rerank(_settings, _prof, cands, _target, **_kwargs):
        return CandidateRerank(list(cands), {"status": "ok", "kept_count": len(cands)})

    async def fake_verify(_settings, cand: Candidate, _context: str, **_kwargs):
        is_item2 = "oxy-" in cand.domain
        return {
            "company_name": f"ООО {'Кислород' if is_item2 else 'Калориметр'} {cand.domain}",
            "site": cand.url,
            "phone": f"+7 (495) 555-{1000 + abs(hash(cand.domain)) % 8999}",
            "email": f"sales@{cand.domain}",
            "evidence_status": "verified",
            "product_fit": "exact",
            "procurement_item_id": "item-2" if is_item2 else "item-1",
            "procurement_item": "Устройство заправки кислородом" if is_item2 else "Калориметрическая установка",
            "quality_score": 88,
            "source": "yandex",
            "search_query": cand.query,
        }

    async def fake_recovery_queries(_settings, _ctx, rec_profile, *_args, **_kwargs):
        assert len(rec_profile.items) == 1
        assert rec_profile.items[0].id == "item-2"
        return ["устройство заправки кислородом УЗК-30м производитель"]

    with (
        patch.object(supplier_search, "build_supplier_queries", side_effect=fake_build_queries),
        patch.object(supplier_search, "discover_candidates", side_effect=fake_discover_candidates),
        patch.object(supplier_search, "ai_rerank_candidates", side_effect=fake_rerank),
        patch.object(supplier_search, "_verify_candidate_with_limits", side_effect=fake_verify),
        patch.object(supplier_search, "_build_supplier_recovery_queries_with_ai", side_effect=fake_recovery_queries),
        patch.object(supplier_search, "_enrich_accepted_suppliers_with_dadata", side_effect=lambda rows: rows),
        patch.object(
            supplier_search,
            "assess_minprom_registry_requirement",
            return_value=MinpromRegistryRequirement(required=False),
        ),
    ):
        accepted, evidence = await discover_suppliers(
            settings,
            "ТЗ: Калориметрическая установка и Устройство заправки кислородом",
            target=10,
            cached_procurement_profile=supplier_search._profile_to_dict(profile),
            multi_item_mode="balanced",
        )

    item1_rows = [r for r in accepted if r.get("procurement_item_id") == "item-1"]
    item2_rows = [r for r in accepted if r.get("procurement_item_id") == "item-2"]
    assert len(item1_rows) == 6
    assert len(item2_rows) == 4
    assert len(discover_calls) == 2
    assert any(
        rr.get("targeted_zero_items") == ["Устройство заправки кислородом"]
        for rr in evidence.get("recovery_rounds", [])
    )
