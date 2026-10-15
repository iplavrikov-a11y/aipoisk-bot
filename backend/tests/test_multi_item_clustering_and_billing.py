from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Client, Job, BillingTransaction
from app.supplier_search import (
    ProcurementItem,
    ProcurementProfile,
    normalize_procurement_profile,
    profile_to_dict,
)
from app.billing import (
    KIND_SUPPLIER_SEARCH,
    OP_RESERVE,
    reserve_job_units,
    reserve_additional_job_units,
    BillingError,
    balance_counter,
)
from app.main import (
    choose_customer_multi_item_strategy_api,
    customer_job_to_dict,
    WebAuthContext,
    WebUser,
)
from app.jobs import update_dobor_context_dict, read_dobor_context


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_procurement_profile_clustering_fields():
    data = {
        "summary": "Поставка подвесных потолков и освещения",
        "items": [
            {
                "id": "ceiling-system",
                "name": "Потолочная система Armstrong (панели, направляющие T-24, подвесы, уголок)",
                "aliases": ["подвесной потолок", "кассетный потолок"],
                "okpd2_codes": ["25.11.23.110"],
                "is_core": True,
                "is_auxiliary": False,
                "included_sub_items": [
                    "Панель потолочная 600х600",
                    "Направляющая основная T-24 3.6м",
                    "Подвес спица-петля с пружиной",
                    "Пристенный L-профиль 25х25",
                ],
                "cost_tier": "high",
            },
            {
                "id": "led-profile",
                "name": "Светодиодный алюминиевый профиль с рассеивателем",
                "aliases": ["LED профиль", "профиль для подсветки"],
                "okpd2_codes": ["27.40.39"],
                "is_core": False,
                "is_auxiliary": True,
                "included_sub_items": ["Алюминиевый профиль накладной", "Матовый рассеиватель"],
                "cost_tier": "auxiliary",
            },
        ],
    }

    profile = normalize_procurement_profile(data)
    assert len(profile.items) == 2

    core_item = profile.items[0]
    assert core_item.id == "ceiling-system"
    assert core_item.is_core is True
    assert core_item.is_auxiliary is False
    assert len(core_item.included_sub_items) == 4
    assert "Пристенный L-профиль 25х25" in core_item.included_sub_items
    assert core_item.cost_tier == "high"

    aux_item = profile.items[1]
    assert aux_item.id == "led-profile"
    assert aux_item.is_core is False
    assert aux_item.is_auxiliary is True
    assert aux_item.cost_tier == "auxiliary"

    # Test serialization to dict
    as_dict = profile_to_dict(profile)
    assert len(as_dict["items"]) == 2
    assert as_dict["items"][0]["is_core"] is True
    assert as_dict["items"][0]["included_sub_items"] == list(core_item.included_sub_items)
    assert as_dict["items"][1]["is_auxiliary"] is True


def test_reserve_additional_job_units_and_billing(test_db):
    client = Client(
        id="client-test-1",
        telegram_id="test-tg-1",
        name="ООО Тест",
        monthly_supplier_search_limit=5,
        money_balance_kopeks=0,
    )
    test_db.add(client)
    test_db.commit()

    job = Job(
        id="job-test-1",
        client_id=client.id,
        mode="supplier_search",
        status="running",
        progress=10,
        message="",
        title="Тест мульти-позиций",
        target_suppliers=5,
        verified_count=0,
        file_count=1,
        result_path="",
        evidence_path="",
        error="",
    )
    test_db.add(job)
    test_db.commit()

    # Initial reservation (1 unit)
    reserve_job_units(test_db, client, job, supplier_search_count=1)
    test_db.refresh(client)
    counter = balance_counter(test_db, client, KIND_SUPPLIER_SEARCH)
    assert counter["available"] == 4  # 5 - 1 reserved

    # Customer picks per_item mode for 3 positions -> needs 2 additional units
    reserve_additional_job_units(test_db, client, job, additional_units=2)
    test_db.refresh(client)
    counter = balance_counter(test_db, client, KIND_SUPPLIER_SEARCH)
    assert counter["available"] == 2  # 5 - 3 reserved

    # Trying to reserve more than available should raise BillingError
    with pytest.raises(BillingError):
        reserve_additional_job_units(test_db, client, job, additional_units=10)


def test_choose_customer_multi_item_strategy_with_filtering(test_db):
    client = Client(
        id="client-test-2",
        telegram_id="test-tg-2",
        name="ООО Снабженец",
        monthly_supplier_search_limit=10,
    )
    test_db.add(client)
    test_db.commit()

    job = Job(
        id="job-test-multi",
        client_id=client.id,
        mode="supplier_search",
        status="awaiting_customer_confirmation",
        confirmation_kind="multi_item_strategy",
        progress=30,
        message="В ТЗ обнаружено 3 позиций",
        title="Закупка стройматериалов",
        target_suppliers=5,
        verified_count=0,
        file_count=1,
        result_path="",
        evidence_path="",
        error="",
    )
    test_db.add(job)
    test_db.commit()

    # Mock profile in dobor_context
    profile_dict = {
        "summary": "Стройматериалы",
        "items": [
            {"id": "cat-1", "name": "Потолок СМЛ", "is_core": True, "included_sub_items": ["СМЛ 12мм", "Профиль"]},
            {"id": "cat-2", "name": "Кассетный потолок", "is_core": True, "included_sub_items": ["Кассеты", "Гребенки"]},
            {"id": "cat-3", "name": "Светодиодный профиль", "is_core": False, "is_auxiliary": True},
        ],
    }
    update_dobor_context_dict(job, {"procurement_profile": profile_dict})

    # Initial unit reserved
    reserve_job_units(test_db, client, job, supplier_search_count=1)

    web_user = WebUser(id="usr-1", client_id=client.id, email="snab@example.com")
    test_db.add(web_user)
    test_db.commit()
    context = WebAuthContext(user=web_user, session=None)

    # Client selects only 2 of the 3 positions: cat-1 and cat-2
    res = choose_customer_multi_item_strategy_api(
        job.id,
        multi_item_mode="per_item",
        selected_item_ids=["cat-1", "cat-2"],
        context=context,
        db=test_db,
    )

    assert res["success"] is True
    test_db.refresh(job)
    assert job.status == "pending"
    assert job.multi_item_mode == "per_item"
    assert "2 поз." in job.message

    dobor_ctx = read_dobor_context(job)
    assert dobor_ctx.get("multi_item_confirmed") is True
    assert dobor_ctx.get("selected_item_ids") == ["cat-1", "cat-2"]

    # Check client balance: 1 reserved initially + 1 reserved additional = 2 total reserved
    counter = balance_counter(test_db, client, KIND_SUPPLIER_SEARCH)
    assert counter["available"] == 8  # 10 - 2
