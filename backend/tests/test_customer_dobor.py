from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock, patch

from app.models import Client, Job, SystemSettings
from app.jobs import write_dobor_context, read_dobor_context, DOBOR_CONTEXT_FILENAME
from app.main import _additional_supplier_target, _cumulative_prior_verified_count
from app import supplier_search


class TestCustomerDobor:
    def test_additional_supplier_target_calculation(self):
        settings = SystemSettings()
        client = Client(id="client-1")
        
        # Original job targeted 25, found 11 -> additional target should be 14
        job1 = Job(id="job-1", target_suppliers=25, verified_count=11)
        assert _additional_supplier_target(settings, client, job1) == 14

        # Original job targeted 25, found 25 -> additional target defaults to 25
        job2 = Job(id="job-2", target_suppliers=25, verified_count=25)
        assert _additional_supplier_target(settings, client, job2) == 25

        # Original job targeted 10, found 0 -> additional target is 10
        job3 = Job(id="job-3", target_suppliers=10, verified_count=0)
        assert _additional_supplier_target(settings, client, job3) == 10

    def test_dobor_context_io(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.jobs.job_dir", lambda job_id: tmp_path / "jobs" / job_id)
        job = Job(id="job-dobor-test")
        
        context_data = {
            "unreviewed_candidates": [{"url": "https://supplier1.ru", "domain": "supplier1.ru"}],
            "procurement_profile": {"summary": "Трубы стальные", "items": []},
            "executed_queries": ["трубы стальные производитель"],
            "wave_index": 2,
            "additional_prompt": "Только региональные склады",
        }
        
        write_dobor_context(
            job,
            previous_job_id="job-parent",
            unreviewed_candidates=context_data["unreviewed_candidates"],
            cached_procurement_profile=context_data["procurement_profile"],
            executed_queries=context_data["executed_queries"],
            wave_index=context_data["wave_index"],
            additional_prompt=context_data["additional_prompt"],
        )
        read_data = read_dobor_context(job)
        
        assert len(read_data["unreviewed_candidates"]) == 1
        assert read_data["unreviewed_candidates"][0]["domain"] == "supplier1.ru"
        assert read_data["wave_index"] == 2
        assert read_data["additional_prompt"] == "Только региональные склады"

    @pytest.mark.asyncio
    async def test_supplier_queries_in_dobor_mode(self):
        settings = SimpleNamespace(has_active_ai_provider=True)
        
        profile = supplier_search.ProcurementProfile(
            summary="Поставка кабеля ВВГнг",
            items=(
                supplier_search.ProcurementItem(
                    id="item-1",
                    name="Кабель ВВГнг-LS 3х2.5",
                    category_terms=("кабель силовой",),
                ),
            ),
        )
        
        with patch.object(supplier_search, "call_llm", AsyncMock(return_value='{"queries": ["кабель силовой склад СПб", "кабель ВВГнг-LS дистрибьютор"]}')):
            queries = await supplier_search.build_supplier_queries(
                settings,
                "ТЗ на поставку кабеля ВВГнг-LS 3х2.5",
                target=5,
                profile=profile,
                is_extend=True,
                wave_index=2,
                executed_queries=["кабель силовой производитель"],
                additional_prompt="Наличие на складе в СПб",
            )
            
            assert isinstance(queries, list)
            assert len(queries) > 0
            assert "кабель силовой склад СПб" in queries
