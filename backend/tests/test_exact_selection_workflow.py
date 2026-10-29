import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import jobs, main
from app.db import Base
from app.models import Client, Job, SystemSettings
from app.position_selection import build_selection_snapshot, read_selection


@pytest.fixture
def context_db(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        client = Client(telegram_id="selection-workflow", money_balance_kopeks=100_000)
        db.add_all([client, SystemSettings()]); db.commit()
        context = SimpleNamespace(user=SimpleNamespace(client_id=client.id, client=client, id="web-selection"))
        monkeypatch.setattr(jobs, "job_dir", lambda job_id: tmp_path / job_id)
        monkeypatch.setattr(jobs, "_check_cancelled", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(jobs, "_populate_job_ai_metadata", lambda *_args, **_kwargs: None)
        yield context, db
    engine.dispose()


def test_worker_prepares_positions_without_matching_or_charging(context_db, monkeypatch):
    context, db = context_db
    job = Job(client_id=context.user.client_id, mode="exact_product", status="running", title="Товары")
    db.add(job); db.commit()
    prepare = AsyncMock(return_value=[{"position_no": i, "name": f"Товар {i}", "requirements": []} for i in range(1, 13)])
    match = AsyncMock()
    monkeypatch.setattr(jobs, "prepare_exact_product_positions", prepare)
    monkeypatch.setattr(jobs, "analyze_exact_product", match)
    jobs._process_exact_product(db, job, db.query(SystemSettings).first(), "Товары")
    assert job.status == "awaiting_exact_selection"
    assert len(read_selection(job)["items"]) == 12
    match.assert_not_called()
    assert context.user.client.money_balance_kopeks == 100_000


def test_api_selection_owner_and_idempotence(context_db, monkeypatch):
    context, db = context_db
    job = Job(client_id=context.user.client_id, mode="exact_product", status="awaiting_exact_selection",
              position_selection_json=build_selection_snapshot([{"position_no": 2, "name": "Кран"}, {"position_no": 9, "name": "Кран"}], price_kopeks=9900))
    db.add(job); db.commit()
    selection = read_selection(job); queued = []
    monkeypatch.setattr(main, "enqueue_job", queued.append)
    for _ in range(2):
        main.choose_exact_product_positions_api(job.id, revision=selection["revision"], selected_item_ids=[selection["items"][1]["id"]], context=context, db=db)
    assert queued == [job.id]
    assert read_selection(job)["selected_ids"] == [selection["items"][1]["id"]]
    other = SimpleNamespace(user=SimpleNamespace(client_id="other"))
    with pytest.raises(HTTPException) as error:
        main.choose_exact_product_positions_api(job.id, revision=selection["revision"], selected_item_ids=[], context=other, db=db)
    assert error.value.status_code == 404


def test_exact_selection_can_be_cancelled(context_db, monkeypatch):
    context, db = context_db
    job = Job(client_id=context.user.client_id, mode="exact_product", status="awaiting_exact_selection")
    db.add(job); db.commit()
    monkeypatch.setattr(main, "cancel_running_job", lambda *_: None)
    result = main.cancel_customer_job_api(job.id, context=context, db=db)
    assert result["job"]["status"] == "cancelled"


def test_customer_monitoring_cancel_refuses_lost_settlement_race(context_db, monkeypatch):
    context, db = context_db
    job = Job(client_id=context.user.client_id, mode="price_monitoring", status="running")
    db.add(job); db.commit()
    called = []
    monkeypatch.setattr(main, "cancel_price_monitoring_job", lambda *_args, **_kwargs: called.append(True) or False, raising=False)
    with pytest.raises(HTTPException) as error:
        main.cancel_customer_job_api(job.id, context=context, db=db)
    assert error.value.status_code == 409
    assert called == [True]
    assert job.status == "running"


def test_admin_monitoring_cancel_uses_atomic_protocol(context_db, monkeypatch):
    context, db = context_db
    job = Job(client_id=context.user.client_id, mode="price_monitoring", status="running")
    db.add(job); db.commit()
    called = []
    monkeypatch.setattr(main, "cancel_price_monitoring_job", lambda *_args, **_kwargs: called.append(True) or False, raising=False)
    main.cancel_job(job.id, db=db)
    assert called == [True]
    assert job.status == "running"


def test_retry_reuses_active_child_and_preserves_old_result(context_db, tmp_path, monkeypatch):
    from app.models import JobFile, BillingTransaction
    context, db = context_db
    context.user.client.allowed_exact_product = True
    original = tmp_path / "original.txt"
    original.write_text("Товар 1\nТовар 2")
    parent = Job(client_id=context.user.client_id, mode="exact_product", status="completed", result_path="old-result.docx")
    db.add(parent); db.commit()
    db.add(JobFile(job_id=parent.id, original_filename="original.txt", stored_path=str(original))); db.commit()
    first, created = main._create_fresh_processing_job(db, parent, client=context.user.client)
    second, created_again = main._create_fresh_processing_job(db, parent, client=context.user.client)
    assert first.id == second.id and created and not created_again
    assert first.status == "pending"
    assert parent.status == "completed" and parent.result_path == "old-result.docx"
    assert db.query(BillingTransaction).filter_by(job_id=first.id, operation="reserve").count() == 1
    assert db.query(Job).filter_by(parent_job_id=parent.id).count() == 1


def test_row_retry_reuses_same_confirmation_and_rejects_other_intent(context_db, tmp_path):
    from app.models import JobFile
    context, db = context_db
    context.user.client.allowed_exact_product = True
    original = tmp_path / "original.txt"; original.write_text("Кран\nКран")
    parent = Job(client_id=context.user.client_id, mode="exact_product", status="completed",
                 position_selection_json=build_selection_snapshot([{"position_no": 2, "name": "Кран"}, {"position_no": 9, "name": "Кран"}], price_kopeks=9900))
    db.add(parent); db.commit()
    db.add(JobFile(job_id=parent.id, original_filename="original.txt", stored_path=str(original))); db.commit()
    selection = read_selection(parent)
    chosen = [selection["items"][1]["id"]]
    child, created = main._create_fresh_processing_job(db, parent, client=context.user.client, selected_source_ids=chosen)
    same, created_again = main._create_fresh_processing_job(db, parent, client=context.user.client, selected_source_ids=chosen)
    assert child.id == same.id and created and not created_again
    snapshot = read_selection(child)
    assert child.status == "awaiting_exact_selection" and not snapshot["confirmed"]
    assert snapshot["revision"] != selection["revision"]
    assert [row["position_no"] for row in snapshot["items"] if row["id"] in snapshot["selected_ids"]] == [9]
    with pytest.raises(HTTPException) as error:
        main._create_fresh_processing_job(db, parent, client=context.user.client, selected_source_ids=[selection["items"][0]["id"]])
    assert error.value.status_code == 409


def test_admin_rerun_reuses_waiting_child_and_clears_unsupported_legacy_geo(context_db, monkeypatch):
    context, db = context_db
    parent = Job(client_id=context.user.client_id, mode="exact_product", status="completed", delivery_city="Казань", geo_radius_km=250)
    db.add(parent); db.commit()
    queued = []
    monkeypatch.setattr(main, "enqueue_job", queued.append)
    first = main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)
    child = db.get(Job, first["job"]["id"])
    child.status = "awaiting_exact_selection"
    db.commit()
    second = main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)
    assert second["job"]["id"] == child.id
    assert queued == [child.id]
    assert child.delivery_city == "" and child.geo_radius_km is None
