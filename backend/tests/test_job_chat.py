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
