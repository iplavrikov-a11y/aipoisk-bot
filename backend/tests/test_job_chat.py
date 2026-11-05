import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import (
    admin_dialogs_list,
    admin_job_chat_get,
    admin_job_chat_post,
    chat_message_to_dict,
    customer_job_chat_mark_read_route,
    customer_job_chat_route,
    customer_job_to_dict,
    get_job_chat_messages,
    job_to_dict,
)
from app.models import Client, Job, JobChatMessage, WebSession, WebUser
from app.web_auth import WebAuthContext


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_job_chat_two_way_workflow(db):
    client = Client(name="ИП Тестовый", telegram_id="123456789")
    db.add(client)
    db.flush()

    user = WebUser(
        client_id=client.id,
        email="test@tenderlex.ru",
        password_hash="hash",
        is_email_verified=True,
    )
    db.add(user)
    db.flush()

    job = Job(
        client_id=client.id,
        mode="price_monitoring",
        title="Смета на стройматериалы",
        status="completed",
        job_number=101,
        admin_comment="Просим уточнить ваш контактный телефон для связи.",
    )
    db.add(job)
    db.commit()

    # 1. Seeding: check get_job_chat_messages auto-seeds from existing admin_comment
    msgs = get_job_chat_messages(db, job, auto_seed=True)
    assert len(msgs) == 1
    assert msgs[0].sender_role == "admin"
    assert "уточнить ваш контактный телефон" in msgs[0].message
    assert msgs[0].is_read_by_client is True

    # 2. Customer replies via cabinet chat, providing a phone number
    web_sess = WebSession(id="sess-123", user_id=user.id)
    ctx = WebAuthContext(user=user, session=web_sess)

    res_client = await customer_job_chat_route(
        job_id=job.id,
        message="Добрый день! Мой номер +7 (999) 111-22-33, звоните в любое время.",
        context=ctx,
        db=db,
    )
    assert res_client["ok"] is True
    assert len(res_client["messages"]) == 2
    assert res_client["messages"][1]["sender_role"] == "client"
    assert "+7 (999) 111-22-33" in res_client["messages"][1]["message"]

    # Check phone number was auto-saved to user and client
    db.refresh(user)
    db.refresh(client)
    assert user.phone == "+7 (999) 111-22-33"
    assert client.phone == "+7 (999) 111-22-33"

    # 3. Serialization check in job_to_dict and customer_job_to_dict
    c_dict = customer_job_to_dict(job, db=db)
    assert len(c_dict["chat_messages"]) == 2
    assert c_dict["unread_admin_messages_count"] == 0

    j_dict = job_to_dict(job, db=db)
    assert j_dict["chat_messages_count"] == 2
    assert j_dict["unread_client_messages_count"] == 1  # Client message unread by admin

    # 4. Admin dialogs listing
    dialogs_res = admin_dialogs_list(db=db)
    assert dialogs_res["total_unread_admin"] == 1
    assert len(dialogs_res["dialogs"]) == 1
    assert dialogs_res["dialogs"][0]["unread_admin_count"] == 1
    assert dialogs_res["dialogs"][0]["client_phone"] == "+7 (999) 111-22-33"

    # 5. Admin opens chat and reads it
    chat_get = admin_job_chat_get(job_id=job.id, db=db)
    assert len(chat_get["messages"]) == 2

    # Unread counter for admin drops to 0 after viewing
    dialogs_res2 = admin_dialogs_list(db=db)
    assert dialogs_res2["total_unread_admin"] == 0

    # 6. Admin sends a reply
    res_admin = await admin_job_chat_post(
        job_id=job.id,
        message="Спасибо за контакт! Отправили вам коммерческое предложение.",
        db=db,
    )
    assert res_admin["ok"] is True
    assert len(res_admin["messages"]) == 3
    assert res_admin["messages"][2]["sender_role"] == "admin"

    # Customer sees 1 unread message
    c_dict2 = customer_job_to_dict(job, db=db)
    assert c_dict2["unread_admin_messages_count"] == 1

    # Customer marks messages as read
    customer_job_chat_mark_read_route(job_id=job.id, context=ctx, db=db)
    c_dict3 = customer_job_to_dict(job, db=db)
    assert c_dict3["unread_admin_messages_count"] == 0


@pytest.mark.asyncio
async def test_admin_supplement_offer_workflow(db, tmp_path, monkeypatch):
    from pathlib import Path
    import app.main as main_mod
    import app.result_offers as ro_mod

    import app.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod.config, "storage_dir", str(tmp_path))

    client = Client(name="ИП Строитель", telegram_id="web:builder", money_balance_kopeks=1000000) # 10 000 rub
    db.add(client)
    db.flush()

    user = WebUser(client_id=client.id, email="builder@tenderlex.ru", password_hash="h", is_email_verified=True)
    db.add(user)
    db.flush()

    web_sess = WebSession(id="sess-offer", user_id=user.id)
    ctx = WebAuthContext(user=user, session=web_sess)

    job = Job(
        client_id=client.id,
        mode="price_monitoring",
        title="Смета на арматуру",
        status="completed",
        verified_count=12,
        job_number=102,
    )
    db.add(job)
    db.flush()

    # Initial charge for 12 positions
    from app.models import BillingTransaction
    db.add(BillingTransaction(client_id=client.id, job_id=job.id, kind="price_monitoring", operation="charge", units=12, amount_kopeks=118800))
    db.commit()

    # 1. Admin prepares supplement offer: 56 positions total (+44 positions, 4 356 rub)
    # Mock data directory for result_offers
    monkeypatch.setattr(ro_mod, "Path", lambda *args: tmp_path / Path(*args[1:]) if len(args) > 1 and args[0] == "data/jobs" else Path(*args))

    # Child rerun job found 56 positions
    rerun_job = Job(
        client_id=client.id,
        parent_job_id=job.id,
        mode="price_monitoring",
        title="[Админ] Перезапуск",
        status="completed",
        verified_count=56,
        is_admin_rerun=True,
    )
    db.add(rerun_job)
    db.commit()

    # Create dummy output file in rerun job
    rerun_out_dir = tmp_path / rerun_job.id / "output"
    rerun_out_dir.mkdir(parents=True, exist_ok=True)
    fake_xlsx = rerun_out_dir / "supplement_table.xlsx"
    fake_xlsx.write_text("dummy xlsx data")

    # Upload supplement as offer
    from app.main import upload_admin_supplement, accept_customer_partial_job_api, decline_customer_partial_job_api, customer_job_result_files
    from unittest.mock import MagicMock
    from fastapi import UploadFile

    import io
    # Admin uploads supplement as offer
    res = await upload_admin_supplement(
        job_id=job.id,
        comment="Нашли 56 позиций вместо 12.",
        notify_telegram=False,
        source_mode="upload",
        as_offer=True,
        offer_charge_rub=4356.0,
        files=[UploadFile(filename="supplement_table.xlsx", file=io.BytesIO(b"dummy xlsx bytes"))],
        db=db,
    )
    assert res["success"] is True

    # Check job state after sending offer
    db.refresh(job)
    assert job.status == "awaiting_customer_confirmation"
    assert job.confirmation_kind == "admin_supplement_offer"
    assert job.confirmation_outcome == "pending"

    # Client balance should NOT be debited yet!
    db.refresh(client)
    assert client.money_balance_kopeks == 1000000

    # In customer serialization, files are locked
    c_dict = customer_job_to_dict(job, db=db)
    assert c_dict["awaiting_customer_confirmation"] is True
    assert c_dict["result_offer"] is not None
    assert c_dict["result_offer"]["kind"] == "admin_supplement_offer"
    assert c_dict["result_offer"]["charge_amount_rub"] == 4356.0
    assert c_dict["result_offer"]["can_accept"] is True
    assert len(c_dict["result_files"]) == 0  # Locked!

    # 2. Customer accepts the offer
    accept_res = accept_customer_partial_job_api(job.id, context=ctx, db=db)
    assert accept_res["success"] is True

    db.refresh(job)
    db.refresh(client)
    assert job.status == "completed"
    assert job.confirmation_outcome == "accepted"
    # Balance must be debited by 4 356.00 rub (435600 kopeks)
    assert client.money_balance_kopeks == 1000000 - 435600

    # Charge transaction should be recorded
    charge_tx = db.query(BillingTransaction).filter(BillingTransaction.job_id == job.id, BillingTransaction.amount_kopeks == 435600).first()
    assert charge_tx is not None
    assert charge_tx.operation == "charge"

    # Files must now be unlocked!
    c_files = customer_job_result_files(job)
    assert len(c_files) >= 1
    assert any(f.get("is_admin_supplement") for f in c_files)

    # Chat must have acceptance confirmation message
    chat_msgs = get_job_chat_messages(db, job)
    assert any(m.sender_role == "client" and "Клиент принял предложение" in m.message for m in chat_msgs)

    # 3. Test decline workflow on a separate job
    job_dec = Job(
        client_id=client.id,
        mode="price_monitoring",
        title="Смета на кирпич",
        status="completed",
        verified_count=10,
        job_number=103,
    )
    db.add(job_dec)
    db.commit()

    # Upload supplement offer for job_dec
    await upload_admin_supplement(
        job_id=job_dec.id,
        comment="Нашли ещё 20 позиций.",
        notify_telegram=False,
        source_mode="upload",
        as_offer=True,
        offer_charge_rub=1980.0,
        files=[UploadFile(filename="brick_supplement.xlsx", file=io.BytesIO(b"data"))],
        db=db,
    )
    db.refresh(job_dec)
    assert job_dec.status == "awaiting_customer_confirmation"

    balance_before_decline = client.money_balance_kopeks
    decline_res = decline_customer_partial_job_api(job_dec.id, context=ctx, db=db)
    assert decline_res["success"] is True

    db.refresh(job_dec)
    db.refresh(client)
    assert job_dec.status == "completed"
    assert job_dec.confirmation_outcome == "declined"
    # Balance must NOT be debited
    assert client.money_balance_kopeks == balance_before_decline

    # Declined supplement files must not be exposed to the customer
    dec_files = customer_job_result_files(job_dec)
    assert not any(f.get("is_admin_supplement") for f in dec_files)

    # Chat must reflect decline
    chat_msgs_dec = get_job_chat_messages(db, job_dec)
    assert any(m.sender_role == "client" and "отклонил предложение" in m.message for m in chat_msgs_dec)


@pytest.mark.asyncio
async def test_client_centric_dialogs_and_unified_chat(db, tmp_path, monkeypatch):
    import app.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod.config, "storage_dir", str(tmp_path))

    from app.main import (
        admin_client_chat_get,
        admin_client_chat_post,
        customer_chat_messages_route,
        customer_chat_post_route,
        customer_chat_mark_read_route,
    )

    client = Client(name="ООО Монолит", telegram_id="987654321")
    db.add(client)
    db.flush()

    user = WebUser(
        client_id=client.id,
        email="monolit@tenderlex.ru",
        password_hash="hash",
        is_email_verified=True,
    )
    db.add(user)
    db.flush()

    job1 = Job(
        client_id=client.id,
        mode="supplier_search",
        title="Поставка кирпича",
        status="completed",
        job_number=201,
    )
    job2 = Job(
        client_id=client.id,
        mode="price_monitoring",
        title="Мониторинг цен на щебень",
        status="completed",
        job_number=202,
    )
    db.add_all([job1, job2])
    db.commit()

    web_sess = WebSession(id="sess-monolit", user_id=user.id)
    ctx = WebAuthContext(user=user, session=web_sess)

    # 1. Customer sends a general support inquiry
    res1 = await customer_chat_post_route(
        message="Здравствуйте! Как выставить счёт на юрлицо?",
        context=ctx,
        db=db,
    )
    assert res1["ok"] is True
    assert len(res1["messages"]) == 1
    assert res1["messages"][0]["job_id"] == ""

    # 2. Customer sends a question tied to Job #201
    res2 = await customer_chat_post_route(
        message="По задаче с кирпичом: нужны сертификаты ГОСТ.",
        job_id=job1.id,
        context=ctx,
        db=db,
    )
    assert res2["ok"] is True
    assert len(res2["messages"]) == 2
    assert res2["messages"][1]["job_number"] == 201

    # 3. Check customer message feed endpoint
    feed = customer_chat_messages_route(context=ctx, db=db)
    assert feed["authenticated"] is True
    assert len(feed["messages"]) == 2
    assert len(feed["jobs"]) == 2
    assert feed["unread_admin_count"] == 0

    # 4. Check admin dialogs list: 1 entry for this client, not 2 separate rows!
    d_res = admin_dialogs_list(db=db)
    monolit_dialogs = [d for d in d_res["dialogs"] if d["client_id"] == client.id]
    assert len(monolit_dialogs) == 1
    diag = monolit_dialogs[0]
    assert diag["client_name"] == "ООО Монолит"
    assert diag["unread_admin_count"] == 2
    assert len(diag["jobs"]) == 2
    job_numbers = {j["job_number"] for j in diag["jobs"]}
    assert 201 in job_numbers and 202 in job_numbers

    # 5. Admin opens client chat: unread status marked as read
    admin_feed = admin_client_chat_get(client_id=client.id, db=db)
    assert len(admin_feed["messages"]) == 2
    assert admin_feed["client"]["name"] == "ООО Монолит"
    assert len(admin_feed["jobs"]) == 2

    # Check unread count dropped to 0
    d_res2 = admin_dialogs_list(db=db)
    monolit_dialogs2 = [d for d in d_res2["dialogs"] if d["client_id"] == client.id]
    assert monolit_dialogs2[0]["unread_admin_count"] == 0

    # 6. Admin replies with reference to Job #201
    res_admin = await admin_client_chat_post(
        client_id=client.id,
        job_id=job1.id,
        message="Сертификаты прикрепили к отчёту по кирпичу.",
        notify_telegram=False,
        db=db,
    )
    assert res_admin["ok"] is True
    assert len(res_admin["messages"]) == 3
    assert res_admin["messages"][2]["sender_role"] == "admin"
    assert res_admin["messages"][2]["job_number"] == 201

    # 7. Customer sees 1 unread message from admin
    feed2 = customer_chat_messages_route(context=ctx, db=db)
    assert feed2["unread_admin_count"] == 1
    assert len(feed2["messages"]) == 3

    # Customer marks as read
    customer_chat_mark_read_route(context=ctx, db=db)
    feed3 = customer_chat_messages_route(context=ctx, db=db)
    assert feed3["unread_admin_count"] == 0
