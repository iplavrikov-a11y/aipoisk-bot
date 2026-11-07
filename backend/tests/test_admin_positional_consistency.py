from __future__ import annotations

import json
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import jobs, main
from app import billing
from app.billing import expire_stale_confirmations
from app.db import Base
from app.models import BillingTransaction, Client, Job, SystemSettings
from app.models import now_utc
from app.position_selection import build_selection_snapshot, read_selection
from app.price_monitoring.models import BatchMonitoringResult, ItemPriceResult, SupplierQuote


@pytest.fixture
def admin_db(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        client = Client(telegram_id="admin-positional", money_balance_kopeks=0)
        db.add_all((client, SystemSettings(price_monitoring_default_price_kopeks=10_000)))
        db.commit()
        storage = tmp_path / "storage"
        monkeypatch.setattr(main, "job_dir", lambda job_id: storage / job_id)
        monkeypatch.setattr(jobs, "job_dir", lambda job_id: storage / job_id)
        yield db, client
    engine.dispose()


@pytest.mark.parametrize("mode,status", [("exact_product", "completed"), ("price_monitoring", "completed")])
def test_admin_rerun_keeps_confirmed_nonfirst_position_subset(admin_db, monkeypatch, mode, status):
    db, client = admin_db
    snapshot = json.loads(build_selection_snapshot(
        [{"position_no": 4, "name": "first"}, {"position_no": 18, "name": "selected"}],
        price_kopeks=10_000,
        mode=mode,
    ))
    snapshot.update(confirmed=True, selected_ids=[snapshot["items"][1]["id"]])
    parent = Job(
        client_id=client.id,
        mode=mode,
        status=status,
        position_selection_json=json.dumps(snapshot, ensure_ascii=False),
        delivery_city="Казань",
        geo_radius_km=30,
    )
    db.add(parent); db.commit()
    queued = []
    monkeypatch.setattr(main, "enqueue_job", queued.append)

    response = main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)
    child = db.get(Job, response["job"]["id"])
    inherited = read_selection(child)

    assert inherited["confirmed"] is True
    assert inherited["revision"] != snapshot["revision"]
    assert inherited["selected_ids"] != snapshot["selected_ids"]
    assert [item["position_no"] for item in inherited["items"] if item["id"] in inherited["selected_ids"]] == [18]
    assert read_selection(parent)["revision"] == snapshot["revision"]
    assert read_selection(parent)["selected_ids"] == snapshot["selected_ids"]
    if mode == "price_monitoring":
        assert child.delivery_city == "Казань"
        assert child.geo_radius_km == 30
    else:
        assert child.delivery_city == ""
        assert child.geo_radius_km is None
    assert queued == [child.id]


def test_admin_rerun_reuses_supplier_per_item_selection_without_cached_market_state(admin_db, monkeypatch):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="completed", multi_item_mode="per_item")
    db.add(parent); db.commit()
    jobs.update_dobor_context_dict(parent, {
        "multi_item_confirmed": True,
        "selected_item_ids": ["item-2"],
        "procurement_profile": {"summary": "spec", "items": [{"id": "item-1"}, {"id": "item-2"}]},
        "executed_queries": ["must not copy"],
        "unreviewed_candidates": [{"name": "must not copy"}],
    })
    monkeypatch.setattr(main, "enqueue_job", lambda _job_id: None)

    child = db.get(Job, main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)["job"]["id"])
    context = jobs.read_dobor_context(child)

    assert child.multi_item_mode == "per_item"
    assert context["multi_item_confirmed"] is True
    assert context["selected_item_ids"] == ["item-2"]
    assert context["procurement_profile"]["items"] == [{"id": "item-1"}, {"id": "item-2"}]
    assert "executed_queries" not in context
    assert "unreviewed_candidates" not in context


def test_admin_rerun_rejects_parent_waiting_for_strategy_or_unconfirmed_positions(admin_db):
    db, client = admin_db
    waiting_strategy = Job(
        client_id=client.id, mode="supplier_search", status="awaiting_customer_confirmation",
        confirmation_kind="multi_item_strategy",
    )
    waiting_selection = Job(
        client_id=client.id, mode="exact_product", status="awaiting_exact_selection",
        position_selection_json=build_selection_snapshot([{"name": "unconfirmed"}], price_kopeks=100),
    )
    db.add_all((waiting_strategy, waiting_selection)); db.commit()

    for parent in (waiting_strategy, waiting_selection):
        with pytest.raises(HTTPException) as error:
            main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)
        assert error.value.status_code == 409
    assert db.query(Job).filter(Job.parent_job_id.in_([waiting_strategy.id, waiting_selection.id])).count() == 0


def test_admin_strategy_rejects_unknown_per_item_ids_and_exposes_selection_state(admin_db, monkeypatch):
    db, client = admin_db
    job = Job(
        client_id=client.id, mode="supplier_search", status="awaiting_customer_confirmation",
        confirmation_kind="multi_item_strategy", confirmation_offered_at=None,
    )
    db.add(job); db.commit()
    jobs.update_dobor_context_dict(job, {"procurement_profile": {"items": [{"id": "item-1"}, {"id": "item-2"}]}})

    with pytest.raises(HTTPException) as error:
        main.choose_admin_multi_item_strategy_api(job.id, multi_item_mode="per_item", selected_item_ids=["unknown"], db=db)
    assert error.value.status_code == 400
    assert job.status == "awaiting_customer_confirmation"

    monkeypatch.setattr(main, "enqueue_job", lambda _job_id: None)
    response = main.choose_admin_multi_item_strategy_api(job.id, multi_item_mode="per_item", selected_item_ids=["item-2"], db=db)
    assert jobs.read_dobor_context(job)["selected_item_ids"] == ["item-2"]
    assert response["job"]["selected_position_count"] == 0
    assert response["job"]["confirmation_expires_at"] is None


def test_internal_admin_monitoring_runs_without_customer_reserve_or_charge(admin_db, monkeypatch, tmp_path):
    db, client = admin_db
    snapshot = json.loads(build_selection_snapshot([{"name": "selected", "unit": "шт"}], price_kopeks=10_000, mode="price_monitoring"))
    snapshot.update(confirmed=True, selected_ids=[snapshot["items"][0]["id"]])
    job = Job(client_id=client.id, mode="price_monitoring", status="running", is_admin_rerun=True,
              position_selection_json=json.dumps(snapshot, ensure_ascii=False))
    db.add(job); db.commit()
    monkeypatch.setattr(jobs, "_check_cancelled", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs, "_populate_job_ai_metadata", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs, "reserve_price_monitoring_job", lambda *_args, **_kwargs: pytest.fail("admin rerun must not reserve customer funds"))
    monkeypatch.setattr(jobs, "charge_price_monitoring_job", lambda *_args, **_kwargs: pytest.fail("admin rerun must not charge customer funds"))

    async def pipeline(**kwargs):
        __import__("pathlib").Path(kwargs["output_excel_path"]).write_bytes(b"internal report")
        item = ItemPriceResult(1, "selected", "selected", "шт", quotes=[SupplierQuote(company_name="Supplier", price_rub=10, url="https://example.invalid")])
        return BatchMonitoringResult(job_id=job.id, items=[item], total_positions=1, found_positions=1, not_found_positions=0, price_per_position_rub=100, total_charged_rub=100)

    monkeypatch.setattr(jobs, "run_price_monitoring_pipeline", pipeline)
    jobs._process_price_monitoring(db, job, db.query(SystemSettings).one(), "selected")
    db.refresh(client)
    assert job.status == "completed"
    assert client.money_balance_kopeks == 0
    assert db.query(BillingTransaction).filter_by(job_id=job.id).count() == 0


def test_multi_item_strategy_confirmation_expires_instead_of_waiting_indefinitely(admin_db):
    db, client = admin_db
    job = Job(client_id=client.id, mode="supplier_search", status="awaiting_customer_confirmation",
              confirmation_kind="multi_item_strategy", updated_at=now_utc() - timedelta(hours=25))
    db.add(job); db.commit()

    assert expire_stale_confirmations(db) == 1
    assert db.get(Job, job.id).status == "confirmation_expired"


def test_legacy_partial_without_reservation_does_not_expire_with_strategy_confirmations(admin_db):
    db, client = admin_db
    job = Job(client_id=client.id, mode="supplier_search", status="partial", updated_at=now_utc() - timedelta(hours=25))
    db.add(job); db.commit()

    assert expire_stale_confirmations(db) == 0
    assert db.get(Job, job.id).status == "partial"


def test_strategy_expiry_releases_existing_reservation(admin_db, monkeypatch):
    db, client = admin_db
    job = Job(client_id=client.id, mode="supplier_search", status="awaiting_customer_confirmation",
              confirmation_kind="multi_item_strategy", updated_at=now_utc() - timedelta(hours=25))
    db.add(job); db.commit()
    released = []
    monkeypatch.setattr(billing, "job_has_unsettled_reservation", lambda *_args: True)
    monkeypatch.setattr(billing, "release_job_reservation", lambda _db, released_job, **kwargs: released.append((released_job.id, kwargs["note"])))

    assert expire_stale_confirmations(db) == 1
    assert released == [(job.id, "Резерв возвращён: клиент не подтвердил выбор стратегии за 24 часа")]


@pytest.mark.parametrize("strategy", ["balanced", "per_item"])
def test_supplier_confirmed_repeat_preserves_subset_geo_and_new_revision(admin_db, monkeypatch, strategy):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="completed", multi_item_mode=strategy,
                 delivery_city="Казань", geo_radius_km=30)
    db.add(parent); db.commit()
    jobs.update_dobor_context_dict(parent, {
        "multi_item_confirmed": True, "selected_item_ids": ["item-2"],
        "procurement_profile": {"summary": "source", "items": [{"id": "item-1", "name": "first"}, {"id": "item-2", "name": "chosen"}]},
        "executed_queries": ["stale market search"], "unreviewed_candidates": [{"name": "stale supplier"}],
    })
    before = main.job_to_dict(parent, db=db)["multi_item_selection"]
    monkeypatch.setattr(main, "enqueue_job", lambda _id: None)

    result = main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)["job"]
    child = db.get(Job, result["id"])
    assert result["multi_item_selection"]["selected_ids"] == ["item-2"]
    assert result["multi_item_selection"]["revision"] != before["revision"]
    assert result["multi_item_mode"] == strategy
    assert (child.delivery_city, child.geo_radius_km) == ("Казань", 30)
    assert set(jobs.read_dobor_context(child)) == {"multi_item_confirmed", "selected_item_ids", "procurement_profile"}
    assert main.job_to_dict(parent, db=db)["admin_reruns"][0]["multi_item_selection"]["revision"] == result["multi_item_selection"]["revision"]


@pytest.mark.parametrize("strategy", ["balanced", "per_item"])
@pytest.mark.parametrize("status", ["confirmation_expired", "awaiting_customer_confirmation"])
def test_supplier_unconfirmed_reissue_requires_explicit_selection_and_leaves_parent_unchanged(admin_db, monkeypatch, strategy, status):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status=status,
                 confirmation_kind="multi_item_strategy", confirmation_outcome="expired" if status == "confirmation_expired" else "pending")
    db.add(parent); db.commit()
    jobs.update_dobor_context_dict(parent, {"procurement_profile": {"items": [{"id": "item-1"}, {"id": "item-2"}]}})
    before = main.job_to_dict(parent, db=db)["multi_item_selection"]
    monkeypatch.setattr(main, "enqueue_job", lambda _id: None)
    with pytest.raises(HTTPException) as error:
        main.admin_rerun_job(parent.id, policy=None, multi_item_mode=strategy, db=db)
    assert error.value.status_code == 409

    result = main.admin_rerun_job(parent.id, policy=None, multi_item_mode=strategy,
                                 selection_payload={"revision": before["revision"], "selected_item_ids": ["item-2"]}, db=db)["job"]
    assert result["multi_item_selection"]["selected_ids"] == ["item-2"]
    assert result["multi_item_selection"]["revision"] != before["revision"]
    assert result["multi_item_selection"]["confirmed"] is True
    assert parent.status == status
    assert jobs.read_dobor_context(parent).get("multi_item_confirmed") is None
    db.refresh(client)
    assert client.money_balance_kopeks == 0
    assert db.query(BillingTransaction).count() == 0


@pytest.mark.parametrize("revision,ids", [("stale", ["item-2"]), (None, []), (None, ["unknown"]), (None, ["item-2", "item-2"])])
def test_supplier_reissue_rejects_stale_or_invalid_selection(admin_db, monkeypatch, revision, ids):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="confirmation_expired")
    db.add(parent); db.commit()
    jobs.update_dobor_context_dict(parent, {"procurement_profile": {"items": [{"id": "item-1"}, {"id": "item-2"}]}})
    selection = main.job_to_dict(parent, db=db)["multi_item_selection"]
    monkeypatch.setattr(main, "enqueue_job", lambda _id: pytest.fail("invalid selection queued"))
    with pytest.raises(HTTPException) as error:
        main.admin_rerun_job(parent.id, policy=None, multi_item_mode="balanced",
                             selection_payload={"revision": revision or selection["revision"], "selected_item_ids": ids}, db=db)
    assert error.value.status_code == 400
    assert db.query(Job).filter_by(parent_job_id=parent.id).count() == 0


@pytest.mark.parametrize("ids", [["item-2"], [], ["unknown"], ["item-2", "item-2"]])
def test_balanced_strategy_respects_explicit_rows(admin_db, monkeypatch, ids):
    db, client = admin_db
    job = Job(client_id=client.id, mode="supplier_search", status="awaiting_customer_confirmation", confirmation_kind="multi_item_strategy")
    db.add(job); db.commit()
    jobs.update_dobor_context_dict(job, {"procurement_profile": {"items": [{"id": "item-1"}, {"id": "item-2"}]}})
    monkeypatch.setattr(main, "enqueue_job", lambda _id: None)
    if ids != ["item-2"]:
        with pytest.raises(HTTPException) as error:
            main.choose_admin_multi_item_strategy_api(job.id, multi_item_mode="balanced", selected_item_ids=ids, db=db)
        assert error.value.status_code == 400
    else:
        main.choose_admin_multi_item_strategy_api(job.id, multi_item_mode="balanced", selected_item_ids=ids, db=db)
        assert jobs.read_dobor_context(job)["selected_item_ids"] == ["item-2"]
    assert db.query(BillingTransaction).count() == 0


@pytest.mark.parametrize("strategy", ["balanced", "per_item"])
@pytest.mark.parametrize("mode", ["supplier_search", "analysis_and_suppliers"])
def test_supplier_discovery_receives_only_explicit_source_rows(admin_db, monkeypatch, strategy, mode):
    db, client = admin_db
    job = Job(client_id=client.id, mode=mode, status="running", multi_item_mode=strategy)
    db.add(job); db.commit()
    jobs.update_dobor_context_dict(job, {
        "multi_item_confirmed": True, "selected_item_ids": ["item-2"],
        "procurement_profile": {"items": [{"id": "item-1", "name": "first"}, {"id": "item-2", "name": "chosen"}]},
    })
    monkeypatch.setattr(jobs, "_check_cancelled", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs, "_populate_job_ai_metadata", lambda *_args: None)
    class ReachedDiscovery(Exception):
        pass
    async def discover(*_args, **kwargs):
        assert [item["id"] for item in kwargs["cached_procurement_profile"]["items"]] == ["item-2"]
        raise ReachedDiscovery
    async def report(*_args):
        return type("Report", (), {"report": "fresh analysis"})()
    async def context(*_args):
        return "fresh supplier context"
    monkeypatch.setattr(jobs, "discover_suppliers", discover)
    monkeypatch.setattr(jobs, "generate_procurement_report", report)
    monkeypatch.setattr(jobs, "extract_supplier_search_context", context)
    processor = jobs._process_supplier_search if mode == "supplier_search" else jobs._process_analysis_and_suppliers
    with pytest.raises(ReachedDiscovery):
        processor(db, job, db.query(SystemSettings).one(), "source")


def test_supplier_revision_depends_only_on_canonical_source_profile_and_job(admin_db):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="confirmation_expired")
    db.add(parent); db.commit()
    jobs.update_dobor_context_dict(parent, {"procurement_profile": {"summary": "source", "items": [{"id": "item-1", "name": "source"}]}})
    revision = main.job_to_dict(parent, db=db)["multi_item_selection"]["revision"]
    jobs.update_dobor_context_dict(parent, {
        "procurement_profile": {"items": [{"name": "source", "id": "item-1"}], "summary": "source"},
        "executed_queries": ["market search"], "unreviewed_candidates": [{"name": "market supplier"}],
    })
    assert main.job_to_dict(parent, db=db)["multi_item_selection"]["revision"] == revision
    jobs.update_dobor_context_dict(parent, {"procurement_profile": {"items": [{"id": "item-1", "name": "changed source"}]}})
    assert main.job_to_dict(parent, db=db)["multi_item_selection"]["revision"] != revision


def test_failed_legacy_supplier_without_profile_can_reparse_input(admin_db, monkeypatch):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="failed", multi_item_mode="per_item")
    db.add(parent); db.commit()
    monkeypatch.setattr(main, "enqueue_job", lambda _id: None)
    child = main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)["job"]
    assert child["status"] == "pending"
    assert child["multi_item_selection"] is None
    assert parent.status == "failed"


@pytest.mark.parametrize("mode", ["supplier_search", "analysis_and_suppliers"])
@pytest.mark.parametrize("ids", [[], ["unknown"], ["item-1", "item-1"]])
def test_supplier_worker_rejects_invalid_explicit_selection_instead_of_all_rows(admin_db, monkeypatch, mode, ids):
    db, client = admin_db
    job = Job(client_id=client.id, mode=mode, status="running", multi_item_mode="balanced")
    db.add(job); db.commit()
    jobs.update_dobor_context_dict(job, {
        "multi_item_confirmed": True, "selected_item_ids": ids,
        "procurement_profile": {"items": [{"id": "item-1", "name": "first"}, {"id": "item-2", "name": "second"}]},
    })
    monkeypatch.setattr(jobs, "_check_cancelled", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs, "_populate_job_ai_metadata", lambda *_args: None)
    async def report(*_args):
        return type("Report", (), {"report": "fresh analysis"})()
    async def context(*_args):
        return "fresh supplier context"
    monkeypatch.setattr(jobs, "generate_procurement_report", report)
    monkeypatch.setattr(jobs, "extract_supplier_search_context", context)
    monkeypatch.setattr(jobs, "discover_suppliers", lambda *_args, **_kwargs: pytest.fail("invalid selection must not search any rows"))
    processor = jobs._process_supplier_search if mode == "supplier_search" else jobs._process_analysis_and_suppliers
    with pytest.raises(ValueError, match="Нет подтверждённых позиций"):
        processor(db, job, db.query(SystemSettings).one(), "source")


@pytest.mark.parametrize("profile", [{}, {"items": []}, {"summary": "source profile without positions"}])
def test_unconfirmed_supplier_profile_never_reruns_without_source_rows(admin_db, monkeypatch, profile):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="confirmation_expired")
    db.add(parent); db.commit()
    jobs.update_dobor_context_dict(parent, {"procurement_profile": profile})
    monkeypatch.setattr(main, "enqueue_job", lambda _id: pytest.fail("unconfirmed source profile must not be queued"))
    with pytest.raises(HTTPException) as error:
        main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, db=db)
    assert error.value.status_code == 409


@pytest.mark.parametrize("channel", ["admin", "customer"])
@pytest.mark.parametrize("stale", [True, False])
def test_strategy_revision_checked_before_state_reservation_or_enqueue(admin_db, monkeypatch, channel, stale):
    db, client = admin_db
    job = Job(client_id=client.id, mode="supplier_search", status="awaiting_customer_confirmation", confirmation_kind="multi_item_strategy")
    db.add(job); db.commit()
    jobs.update_dobor_context_dict(job, {"procurement_profile": {"items": [{"id": "one", "name": "first"}, {"id": "two", "name": "second"}]}})
    revision = main.job_to_dict(job, db=db)["multi_item_selection"]["revision"]
    queued, reserved = [], []
    monkeypatch.setattr(main, "enqueue_job", queued.append)
    monkeypatch.setattr(billing, "reserve_additional_job_units", lambda *_args, **_kwargs: reserved.append(True))
    monkeypatch.setattr(main, "_customer_job_or_404", lambda *_args: job)
    if channel == "admin":
        confirm = lambda: main.choose_admin_strategy(job.id, multi_item_mode="per_item", selected_item_ids=["one", "two"], revision="stale" if stale else revision, db=db)
    else:
        confirm = lambda: main.choose_customer_multi_item_strategy_api(job.id, multi_item_mode="per_item", selected_item_ids=["one", "two"], revision="stale" if stale else revision, context=None, db=db)
    if stale:
        with pytest.raises(HTTPException) as error:
            confirm()
        assert error.value.status_code == 400
        assert queued == reserved == []
        assert job.status == "awaiting_customer_confirmation"
        assert job.confirmation_kind == "multi_item_strategy"
        assert jobs.read_dobor_context(job).get("multi_item_confirmed") is None
    else:
        confirm()
        assert job.status == "pending"
        assert queued == [job.id]
        assert reserved == [True]
        assert main.customer_job_to_dict(job, db=db)["multi_item_details"]["revision"] == revision


@pytest.mark.parametrize("mode", ["exact_product", "price_monitoring"])
@pytest.mark.parametrize("payload_kind", ["stale", "unknown", "revision_only", "ids_only", "valid_override", "empty", "null"])
def test_confirmed_position_rerun_validates_explicit_override(admin_db, monkeypatch, mode, payload_kind):
    db, client = admin_db
    snapshot = json.loads(build_selection_snapshot([{"position_no": 2, "name": "original choice"}, {"position_no": 8, "name": "override choice"}], price_kopeks=10_000, mode=mode))
    snapshot.update(confirmed=True, selected_ids=[snapshot["items"][0]["id"]])
    parent = Job(client_id=client.id, mode=mode, status="completed", position_selection_json=json.dumps(snapshot, ensure_ascii=False))
    db.add(parent); db.commit()
    queued = []
    monkeypatch.setattr(main, "enqueue_job", queued.append)
    payload = {"revision": snapshot["revision"], "selected_item_ids": [snapshot["items"][1]["id"]]}
    if payload_kind == "stale":
        payload["revision"] = "stale"
    elif payload_kind == "unknown":
        payload["selected_item_ids"] = ["unknown"]
    elif payload_kind == "revision_only":
        payload.pop("selected_item_ids")
    elif payload_kind == "ids_only":
        payload.pop("revision")
    elif payload_kind == "empty":
        payload["selected_item_ids"] = []
    elif payload_kind == "null":
        payload = {"revision": None, "selected_item_ids": None}
    if payload_kind != "valid_override":
        with pytest.raises(HTTPException) as error:
            main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, selection_payload=payload, db=db)
        assert error.value.status_code == 400
        assert queued == []
        assert db.query(Job).filter_by(parent_job_id=parent.id).count() == 0
    else:
        child = db.get(Job, main.admin_rerun_job(parent.id, policy=None, multi_item_mode=None, selection_payload=payload, db=db)["job"]["id"])
        selection = read_selection(child)
        assert [item["position_no"] for item in selection["items"] if item["id"] in selection["selected_ids"]] == [8]
        assert selection["revision"] != snapshot["revision"]
        assert selection["selected_ids"] != payload["selected_item_ids"]
        assert queued == [child.id]
    assert read_selection(parent) == snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("internal", [True, False])
async def test_zero_balance_monitoring_confirmation_only_exempts_internal_expert(admin_db, monkeypatch, internal):
    from starlette.requests import Request
    db, client = admin_db
    snapshot = json.loads(build_selection_snapshot([{"name": "chosen"}], price_kopeks=10_000, mode="price_monitoring"))
    job = Job(client_id=client.id, mode="price_monitoring", status="awaiting_position_selection", is_admin_rerun=internal,
              position_selection_json=json.dumps(snapshot, ensure_ascii=False))
    db.add(job); db.commit()
    payload = json.dumps({"revision": snapshot["revision"], "selected_item_ids": [snapshot["items"][0]["id"]]}).encode()
    async def receive():
        return {"type": "http.request", "body": payload}
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []}, receive)
    queued = []
    monkeypatch.setattr(main, "enqueue_job", queued.append)
    if internal:
        result = await main.admin_exact_selection_route(job.id, request, db=db)
        assert result["job"]["status"] == "pending"
        assert read_selection(job)["confirmed"] is True
        assert queued == [job.id]
    else:
        with pytest.raises(HTTPException) as error:
            await main.admin_exact_selection_route(job.id, request, db=db)
        assert error.value.status_code == 400
        assert "Недостаточно средств" in error.value.detail
        assert job.status == "awaiting_position_selection"
        assert queued == []
    assert client.money_balance_kopeks == 0
    assert db.query(BillingTransaction).count() == 0


@pytest.mark.parametrize("strategy", ["balanced", "per_item"])
@pytest.mark.parametrize("confirmed,selected,expected", [(True, None, ["one", "two"]), (True, [], []), (False, None, [])])
def test_supplier_serializer_distinguishes_confirmed_legacy_all_and_explicit_empty(admin_db, monkeypatch, strategy, confirmed, selected, expected):
    db, client = admin_db
    parent = Job(client_id=client.id, mode="supplier_search", status="completed", multi_item_mode=strategy)
    child = Job(client_id=client.id, mode="supplier_search", status="completed", multi_item_mode=strategy, is_admin_rerun=True)
    db.add_all((parent, child)); db.commit()
    child.parent_job_id = parent.id
    db.commit()
    for job in (parent, child):
        jobs.update_dobor_context_dict(job, {"multi_item_confirmed": confirmed, "selected_item_ids": selected,
            "procurement_profile": {"items": [{"id": "one"}, {"id": "two"}]}})
    serialized = main.job_to_dict(parent, db=db)
    assert serialized["multi_item_selection"]["selected_ids"] == expected
    assert serialized["admin_reruns"][0]["multi_item_selection"]["selected_ids"] == expected
