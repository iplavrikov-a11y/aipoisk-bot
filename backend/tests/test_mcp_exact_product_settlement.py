from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.exact_product.models import ExactProductPosition, ExactProductReport
from app.mcp_api import McpExactProductRequest, mcp_exact_product


def report_with_statuses(statuses):
    return ExactProductReport("Товар", len(statuses), [ExactProductPosition(
        position_no=index, name_in_tz="Клапан", identified_brand="Завод" if status == "found" else "",
        identified_model="К25" if status == "found" else "", manufacturer="Изготовитель" if status == "found" else "",
        confidence=.9 if status == "found" else 0, reasoning="Результат проверки", status=status,
    ) for index, status in enumerate(statuses, 1)])


@pytest.mark.asyncio
@pytest.mark.parametrize("statuses", [["not_found"], ["needs_clarification"], ["error", "not_found"]])
async def test_no_confirmed_product_releases_instead_of_charging(tmp_path, statuses):
    db = MagicMock()
    job = SimpleNamespace(id="testjob", result_path="", evidence_path="")
    with patch("app.mcp_api.get_or_create_settings", return_value=SimpleNamespace(public_base_url="https://tenderlex.ru")), patch("app.mcp_api.start_api_job_with_reservation", return_value=(job, 10)), patch("app.mcp_api.analyze_exact_product", new_callable=AsyncMock, return_value=report_with_statuses(statuses)), patch("app.mcp_api.config.storage_dir", str(tmp_path)), patch("app.jobs.job_dir", return_value=tmp_path / "job"), patch("app.mcp_api.write_exact_product_docx", side_effect=lambda path, *args, **kwargs: path.write_bytes(b"docx")), patch("app.mcp_api.release_api_job_reservation") as release, patch("app.mcp_api.finalize_api_job_success") as charge:
        response = await mcp_exact_product(McpExactProductRequest(specification="Спецификация клапанов"), api_key=SimpleNamespace(id="test-key", key_hash="test-hash", is_admin=False, client_id=None, allowed_exact_product=True), db=db)
    release.assert_called_once()
    assert release.call_args.kwargs["verified_count"] == 0
    assert release.call_args.kwargs["status_val"] == "completed"
    charge.assert_not_called()
    assert response.ok
    assert response.docx_download_url
    assert [position.status for position in response.positions] == statuses
    assert release.call_args.kwargs["result_path"]
    assert release.call_args.kwargs["evidence_path"]
    assert not job.result_path
    assert not job.evidence_path


@pytest.mark.asyncio
async def test_mixed_report_counts_only_confirmed_positions(tmp_path):
    with patch("app.mcp_api.get_or_create_settings", return_value=SimpleNamespace(public_base_url="https://tenderlex.ru")), patch("app.mcp_api.start_api_job_with_reservation", return_value=(None, 10)), patch("app.mcp_api.analyze_exact_product", new_callable=AsyncMock, return_value=report_with_statuses(["found", "not_found", "needs_clarification"])), patch("app.mcp_api.config.storage_dir", str(tmp_path)), patch("app.mcp_api.write_exact_product_docx", side_effect=lambda path, *args, **kwargs: path.write_bytes(b"docx")), patch("app.mcp_api.release_api_job_reservation") as release, patch("app.mcp_api.finalize_api_job_success") as charge:
        await mcp_exact_product(McpExactProductRequest(specification="Спецификация клапанов"), api_key=SimpleNamespace(id="test-key", key_hash="test-hash", is_admin=False, client_id=None, allowed_exact_product=True), db=MagicMock())
    release.assert_not_called()
    assert charge.call_args.kwargs["verified_count"] == 1


@pytest.mark.asyncio
async def test_docx_save_failure_releases_and_returns_error(tmp_path):
    with patch("app.mcp_api.get_or_create_settings", return_value=SimpleNamespace(public_base_url="https://tenderlex.ru")), patch("app.mcp_api.start_api_job_with_reservation", return_value=(None, 10)), patch("app.mcp_api.analyze_exact_product", new_callable=AsyncMock, return_value=report_with_statuses(["found"])), patch("app.mcp_api.config.storage_dir", str(tmp_path)), patch("app.mcp_api.write_exact_product_docx", side_effect=OSError("disk full")), patch("app.mcp_api.release_api_job_reservation") as release, patch("app.mcp_api.finalize_api_job_success") as charge:
        with pytest.raises(HTTPException) as error:
            await mcp_exact_product(McpExactProductRequest(specification="Спецификация клапанов"), api_key=SimpleNamespace(id="test-key", key_hash="test-hash", is_admin=False, client_id=None, allowed_exact_product=True), db=MagicMock())
    assert error.value.status_code == 500
    release.assert_called_once()
    charge.assert_not_called()


@pytest.mark.asyncio
async def test_job_report_save_failure_after_public_copy_never_charges(tmp_path):
    job = SimpleNamespace(id="testjob")
    with patch("app.mcp_api.get_or_create_settings", return_value=SimpleNamespace(public_base_url="https://tenderlex.ru")), patch("app.mcp_api.start_api_job_with_reservation", return_value=(job, 10)), patch("app.mcp_api.analyze_exact_product", new_callable=AsyncMock, return_value=report_with_statuses(["found"])), patch("app.mcp_api.config.storage_dir", str(tmp_path)), patch("app.jobs.job_dir", return_value=tmp_path / "job"), patch("app.mcp_api.write_exact_product_docx", side_effect=[None, OSError("disk full")]), patch("app.mcp_api.release_api_job_reservation") as release, patch("app.mcp_api.finalize_api_job_success") as charge:
        with pytest.raises(HTTPException) as error:
            await mcp_exact_product(McpExactProductRequest(specification="Спецификация клапанов"), api_key=SimpleNamespace(id="test-key", key_hash="test-hash", is_admin=False, client_id=None, allowed_exact_product=True), db=MagicMock())
    assert error.value.status_code == 500
    release.assert_called_once()
    charge.assert_not_called()
