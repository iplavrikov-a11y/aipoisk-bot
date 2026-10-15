from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.jobs import job_dir, package_job_output_items, package_job_outputs
from app.main import customer_job_to_dict, read_job_evidence_payload
from app.models import Job


def test_package_job_outputs_fallback_resolution(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.config.storage_dir", str(tmp_path))
    job_id = "test-legacy-job-001"
    job = Job(
        id=job_id,
        mode="supplier_search",
        status="completed",
        progress=100,
        result_path="/root/projects/aipoisk-bot/storage/jobs/test-legacy-job-001/output/Поставщики - Тест.xlsx",
    )

    out_dir = job_dir(job_id) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    actual_xlsx = out_dir / "Поставщики - Тест.xlsx"
    actual_xlsx.write_bytes(b"dummy-xlsx-content")

    resolved = package_job_outputs(job)
    assert resolved is not None
    assert resolved.exists()
    assert resolved.resolve() == actual_xlsx.resolve()


def test_evidence_and_output_items_resilience(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.config.storage_dir", str(tmp_path))
    job_id = "test-legacy-job-002"

    out_dir = job_dir(job_id) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    actual_xlsx = out_dir / "Поставщики - Тест.xlsx"
    actual_xlsx.write_bytes(b"dummy-xlsx-content")
    actual_docx = out_dir / "Запрос КП - Тест.docx"
    actual_docx.write_bytes(b"dummy-docx-content")

    evidence_data = {
        "output_files": [
            {
                "kind": "suppliers",
                "label": "Поставщики",
                "path": "/root/projects/aipoisk-bot/storage/jobs/test-legacy-job-002/output/Поставщики - Тест.xlsx",
            },
            {
                "kind": "quote_request",
                "label": "Запрос КП",
                "path": "/root/projects/aipoisk-bot/storage/jobs/test-legacy-job-002/output/Запрос КП - Тест.docx",
            },
        ]
    }
    actual_evidence = out_dir / "evidence.json"
    actual_evidence.write_text(json.dumps(evidence_data), encoding="utf-8")

    job = Job(
        id=job_id,
        mode="supplier_search",
        status="completed",
        progress=100,
        result_path="/root/projects/aipoisk-bot/storage/jobs/test-legacy-job-002/output/Поставщики - Тест.xlsx",
        evidence_path="/root/projects/aipoisk-bot/storage/jobs/test-legacy-job-002/output/evidence.json",
    )

    items = package_job_output_items(job)
    assert len(items) == 2
    assert items[0]["kind"] == "suppliers"
    assert Path(items[0]["path"]).resolve() == actual_xlsx.resolve()
    assert items[1]["kind"] == "quote_request"
    assert Path(items[1]["path"]).resolve() == actual_docx.resolve()

    payload = read_job_evidence_payload(job)
    assert "output_files" in payload

    customer_dict = customer_job_to_dict(job)
    assert customer_dict["has_result"] is True
    assert customer_dict["can_download"] is True
    assert len(customer_dict["result_files"]) == 2
