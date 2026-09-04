from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.main import app
from app.models import (
    Client,
    ClientTelegramAccount,
    Job,
    OnboardingReminder,
    SystemSettings,
    WebUser,
    now_utc,
)
from app.nurturing import (
    build_nurturing_email_html,
    build_nurturing_telegram_message,
    dispatch_nurturing_candidate,
    generate_unsubscribe_token,
    get_due_nurturing_candidates,
    unsubscribe_by_telegram_id,
    unsubscribe_by_token,
    verify_unsubscribe_token,
)


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, db_session as app_db_session


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(db_session: Session) -> TestClient:
    app.dependency_overrides[app_db_session] = lambda: db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(app_db_session, None)


def test_unsubscribe_token_lifecycle():
    client_id = "client-test-123"
    recipient = "buyer@example.com"

    token = generate_unsubscribe_token(client_id, recipient)
    assert token and "." in token

    verified = verify_unsubscribe_token(token)
    assert verified is not None
    cid, rec = verified
    assert cid == client_id
    assert rec == recipient

    # Tampered token fails
    assert verify_unsubscribe_token(token + "tampered") is None
    assert verify_unsubscribe_token("invalid.token") is None
    assert verify_unsubscribe_token("") is None


def test_unsubscribe_by_token_and_api_endpoint(db_session: Session, test_client: TestClient):
    uid = uuid.uuid4().hex[:8]
    client = Client(
        telegram_id=f"pending:web:unsub_{uid}",
        name="ООО Тест Отписки",
        is_active=True,
        marketing_unsubscribed=False,
    )
    db_session.add(client)
    db_session.flush()

    web_user = WebUser(
        client_id=client.id,
        email=f"unsub_{uid}@example.com",
        name="Менеджер",
        is_active=True,
        is_email_verified=True,
        marketing_unsubscribed=False,
    )
    db_session.add(web_user)
    db_session.commit()

    token = generate_unsubscribe_token(client.id, web_user.email)

    # Valid token via API endpoint
    response = test_client.get(f"/api/customer/auth/unsubscribe?token={token}")
    assert response.status_code == 200
    assert "Вы успешно отписались" in response.text
    assert "TenderLex" in response.text

    db_session.refresh(client)
    db_session.refresh(web_user)
    assert client.marketing_unsubscribed is True
    assert web_user.marketing_unsubscribed is True

    # Invalid token via API endpoint
    bad_resp = test_client.get("/api/customer/auth/unsubscribe?token=garbage_token")
    assert bad_resp.status_code == 400
    assert "Ошибка отписки" in bad_resp.text


def test_unsubscribe_by_telegram_id(db_session: Session):
    tg_id = str(uuid.uuid4().int)[:10]
    client = Client(
        telegram_id=tg_id,
        name="ООО Телеграм Клиент",
        is_active=True,
        marketing_unsubscribed=False,
    )
    db_session.add(client)
    db_session.flush()

    account = ClientTelegramAccount(
        client_id=client.id,
        telegram_id=tg_id,
        username=f"tg_{tg_id}",
        name="Иван",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    ok = unsubscribe_by_telegram_id(db_session, tg_id)
    assert ok is True

    db_session.refresh(client)
    assert client.marketing_unsubscribed is True


def test_nurturing_step1_candidates(db_session: Session):
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    rollout = (now - timedelta(days=10)).isoformat()

    settings = db_session.query(SystemSettings).first() or SystemSettings(id=1)
    settings.onboarding_reminders_enabled = True
    settings.onboarding_reminders_rollout_at = rollout
    db_session.add(settings)
    db_session.commit()

    t1, t2, t3, t4 = str(uuid.uuid4().int)[:10], str(uuid.uuid4().int)[:10], str(uuid.uuid4().int)[:10], str(uuid.uuid4().int)[:10]

    # Client A: 25h old, 0 jobs, subscribed -> should be candidate
    client_a = Client(
        telegram_id=t1,
        name="Клиент 1",
        is_active=True,
        marketing_unsubscribed=False,
        created_at=now - timedelta(hours=25),
    )
    db_session.add(client_a)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_a.id, telegram_id=t1, is_active=True))

    # Client B: 10h old, 0 jobs -> too young
    client_b = Client(
        telegram_id=t2,
        name="Клиент 2",
        is_active=True,
        marketing_unsubscribed=False,
        created_at=now - timedelta(hours=10),
    )
    db_session.add(client_b)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_b.id, telegram_id=t2, is_active=True))

    # Client C: 25h old, but unsubscribed -> excluded
    client_c = Client(
        telegram_id=t3,
        name="Клиент 3",
        is_active=True,
        marketing_unsubscribed=True,
        created_at=now - timedelta(hours=25),
    )
    db_session.add(client_c)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_c.id, telegram_id=t3, is_active=True))

    # Client D: 25h old, but has a job -> excluded from step1
    client_d = Client(
        telegram_id=t4,
        name="Клиент 4",
        is_active=True,
        marketing_unsubscribed=False,
        created_at=now - timedelta(hours=25),
    )
    db_session.add(client_d)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_d.id, telegram_id=t4, is_active=True))
    db_session.add(Job(client_id=client_d.id, status="completed"))

    db_session.commit()

    candidates = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)
    candidate_ids = [c.client_id for c in candidates if c.step == "step1"]

    assert client_a.id in candidate_ids
    assert client_b.id not in candidate_ids
    assert client_c.id not in candidate_ids
    assert client_d.id not in candidate_ids


def test_nurturing_step2_and_step3_candidates(db_session: Session):
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    rollout = (now - timedelta(days=10)).isoformat()

    settings = db_session.query(SystemSettings).first() or SystemSettings(id=1)
    settings.onboarding_reminders_enabled = True
    settings.onboarding_reminders_rollout_at = rollout
    db_session.add(settings)
    db_session.commit()

    t5, t6 = str(uuid.uuid4().int)[:10], str(uuid.uuid4().int)[:10]

    # Client Step 2: 1 completed job 50h ago, remaining trial balance 297 RUB (29700 kop)
    client_s2 = Client(
        telegram_id=t5,
        name="Клиент Шаг 2",
        is_active=True,
        marketing_unsubscribed=False,
        money_balance_kopeks=29700,
        created_at=now - timedelta(days=3),
    )
    db_session.add(client_s2)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_s2.id, telegram_id=t5, is_active=True))
    job1 = Job(client_id=client_s2.id, status="completed", created_at=now - timedelta(hours=50))
    db_session.add(job1)

    # Client Step 3: 4 completed jobs, balance 0 kopeks, last job 5h ago
    client_s3 = Client(
        telegram_id=t6,
        name="Клиент Шаг 3",
        is_active=True,
        marketing_unsubscribed=False,
        money_balance_kopeks=0,
        created_at=now - timedelta(days=5),
    )
    db_session.add(client_s3)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_s3.id, telegram_id=t6, is_active=True))
    for i in range(4):
        db_session.add(Job(client_id=client_s3.id, status="completed", created_at=now - timedelta(hours=5 + i)))

    db_session.commit()

    candidates = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)
    step2_ids = [c.client_id for c in candidates if c.step == "step2"]
    step3_ids = [c.client_id for c in candidates if c.step == "step3"]

    assert client_s2.id in step2_ids
    assert client_s3.id in step3_ids


def test_nurturing_content_builders():
    # Email HTML builder
    for step in ("step1", "step1_final", "step2", "step3", "step4_reengage"):
        subject, html = build_nurturing_email_html(step, "cid-123", "user@example.com")
        assert subject
        assert "TenderLex" in html
        assert "сервис автоматизации снабжения" in html
        assert "1. Поиск поставщиков" in html
        assert "2. Подбор товара и аналогов" in html
        assert "3. Анализ документации" in html
        assert "@tenderlex_bot" in html
        assert "api/customer/auth/unsubscribe?token=" in html
        assert "Отписаться от рассылки" in html
        assert "\n\n\n" not in html  # no massive empty newline blocks

    # Telegram message builder
    for step in ("step1", "step1_final", "step2", "step3", "step4_reengage"):
        text, buttons = build_nurturing_telegram_message(step)
        assert text
        assert "TenderLex" in text
        # Must contain unsubscribe button in markup
        assert any(b.get("callback_data") == "nurturing_unsubscribe" for row in buttons for b in row)


@pytest.mark.asyncio
async def test_dispatch_nurturing_candidate_telegram(db_session: Session):
    t7 = str(uuid.uuid4().int)[:10]
    client = Client(
        telegram_id=t7,
        name="Тест Диспетчера",
        is_active=True,
        marketing_unsubscribed=False,
    )
    db_session.add(client)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client.id, telegram_id=t7, is_active=True))
    db_session.commit()

    candidates = get_due_nurturing_candidates(
        db_session,
        SystemSettings(onboarding_reminders_enabled=True, onboarding_reminders_rollout_at="2020-01-01T00:00:00Z"),
        current_time=now_utc() + timedelta(days=2),
        enforce_work_hours=False,
    )
    assert len(candidates) >= 1
    cand = next(c for c in candidates if c.client_id == client.id)

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = True

    ok = await dispatch_nurturing_candidate(db_session, cand, bot=mock_bot)
    assert ok is True
    assert mock_bot.send_message.called

    reminder = (
        db_session.query(OnboardingReminder)
        .filter(OnboardingReminder.client_id == client.id, OnboardingReminder.step == cand.step)
        .first()
    )
    assert reminder is not None
    assert reminder.status == "sent"


def _make_tg_client(db_session: Session, telegram_id: str, created_at) -> Client:
    client = Client(
        telegram_id=telegram_id,
        name=f"Клиент {telegram_id}",
        is_active=True,
        marketing_unsubscribed=False,
        created_at=created_at,
    )
    db_session.add(client)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client.id, telegram_id=telegram_id, is_active=True))
    return client


def test_nurturing_step1_final_candidates(db_session: Session):
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    settings = db_session.query(SystemSettings).first() or SystemSettings(id=1)
    settings.onboarding_reminders_enabled = True
    settings.onboarding_reminders_rollout_at = (now - timedelta(days=30)).isoformat()
    db_session.add(settings)

    t1, t2, t3, t4 = (str(uuid.uuid4().int)[:10] for _ in range(4))

    # Client A: 15 days old, 0 jobs, step1 sent -> candidate for step1_final
    client_a = _make_tg_client(db_session, t1, now - timedelta(days=15))
    db_session.flush()
    db_session.add(
        OnboardingReminder(client_id=client_a.id, channel="telegram", step="step1", status="sent", sent_at=now - timedelta(days=13))
    )

    # Client B: 15 days old, 0 jobs, but step1 never sent -> no final call
    client_b = _make_tg_client(db_session, t2, now - timedelta(days=15))

    # Client C: 15 days old, 0 jobs, step1 sent, but final already sent -> no repeat
    client_c = _make_tg_client(db_session, t3, now - timedelta(days=15))
    db_session.flush()
    db_session.add(
        OnboardingReminder(client_id=client_c.id, channel="telegram", step="step1", status="sent", sent_at=now - timedelta(days=13))
    )
    db_session.add(
        OnboardingReminder(client_id=client_c.id, channel="telegram", step="step1_final", status="sent", sent_at=now - timedelta(days=1))
    )

    # Client D: 15 days old, step1 sent, but created a job since -> converted, no final call
    client_d = _make_tg_client(db_session, t4, now - timedelta(days=15))
    db_session.flush()
    db_session.add(
        OnboardingReminder(client_id=client_d.id, channel="telegram", step="step1", status="sent", sent_at=now - timedelta(days=13))
    )
    db_session.add(Job(client_id=client_d.id, status="completed"))

    db_session.commit()

    candidates = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)
    final_ids = [c.client_id for c in candidates if c.step == "step1_final"]

    assert client_a.id in final_ids
    assert client_b.id not in final_ids
    assert client_c.id not in final_ids
    assert client_d.id not in final_ids

    # Text and buttons present
    text, buttons = build_nurturing_telegram_message("step1_final")
    assert "последнее напоминание" in text.lower()
    assert any("nurturing_unsubscribe" in btn.get("callback_data", "") for row in buttons for btn in row)
    subject, html = build_nurturing_email_html("step1_final", "cid", "a@b.ru")
    assert "Последнее напоминание" in subject


def test_nurturing_step4_reengage_candidates(db_session: Session):
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    settings = db_session.query(SystemSettings).first() or SystemSettings(id=1)
    settings.onboarding_reminders_enabled = True
    settings.reengagement_reminders_enabled = True
    settings.onboarding_reminders_rollout_at = (now - timedelta(days=60)).isoformat()
    db_session.add(settings)

    t1, t2, t3, t4, t5 = (str(uuid.uuid4().int)[:10] for _ in range(5))

    # Client A: completed job 12 days ago, no active jobs -> reengage candidate
    client_a = _make_tg_client(db_session, t1, now - timedelta(days=40))
    db_session.add(Job(client_id=client_a.id, status="completed", created_at=now - timedelta(days=12)))

    # Client B: completed 12 days ago too — valid candidate when the global flag is on
    client_b = _make_tg_client(db_session, t2, now - timedelta(days=40))
    db_session.add(Job(client_id=client_b.id, status="completed", created_at=now - timedelta(days=12)))

    # Client C: completed only 5 days ago (within step2 window) -> excluded
    client_c = _make_tg_client(db_session, t3, now - timedelta(days=40))
    db_session.add(Job(client_id=client_c.id, status="completed", created_at=now - timedelta(days=5)))

    # Client D: completed 12 days ago but has a running job -> excluded
    client_d = _make_tg_client(db_session, t4, now - timedelta(days=40))
    db_session.add(Job(client_id=client_d.id, status="completed", created_at=now - timedelta(days=12)))
    db_session.add(Job(client_id=client_d.id, status="running", created_at=now - timedelta(days=1)))

    # Client E: completed 12 days ago, reengage already sent -> excluded
    client_e = _make_tg_client(db_session, t5, now - timedelta(days=40))
    db_session.add(Job(client_id=client_e.id, status="completed", created_at=now - timedelta(days=12)))
    db_session.flush()
    db_session.add(
        OnboardingReminder(client_id=client_e.id, channel="telegram", step="step4_reengage", status="sent", sent_at=now - timedelta(days=2))
    )

    # Flag off applies globally: temporarily disable
    settings.reengagement_reminders_enabled = False
    db_session.commit()
    candidates_off = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)
    assert all(c.step != "step4_reengage" for c in candidates_off)

    settings.reengagement_reminders_enabled = True
    db_session.commit()
    candidates = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)
    reengage_ids = [c.client_id for c in candidates if c.step == "step4_reengage"]

    assert client_a.id in reengage_ids
    assert client_b.id in reengage_ids
    assert client_c.id not in reengage_ids
    assert client_d.id not in reengage_ids
    assert client_e.id not in reengage_ids

    text, _ = build_nurturing_telegram_message("step4_reengage")
    assert "давно не виделись" in text.lower()


def test_nurturing_funnel_stats(db_session: Session):
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    settings = db_session.query(SystemSettings).first() or SystemSettings(id=1)
    settings.onboarding_reminders_enabled = True
    settings.onboarding_reminders_rollout_at = (now - timedelta(days=30)).isoformat()
    db_session.add(settings)

    t1, t2 = (str(uuid.uuid4().int)[:10] for _ in range(2))
    client_a = _make_tg_client(db_session, t1, now - timedelta(days=20))
    client_b = _make_tg_client(db_session, t2, now - timedelta(days=20))
    db_session.flush()
    db_session.add(
        OnboardingReminder(client_id=client_a.id, channel="telegram", step="step1", status="sent", sent_at=now - timedelta(days=19))
    )
    db_session.add(Job(client_id=client_a.id, status="completed"))
    db_session.commit()

    from app.nurturing import get_nurturing_funnel_stats

    stats = get_nurturing_funnel_stats(db_session, settings)
    assert stats["registered_since_rollout"] >= 2
    assert stats["steps"]["step1"]["sent"] >= 1
    assert stats["steps"]["step1"]["converted_to_first_job"] >= 1
    assert stats["funnel"]["activated_created_job"] >= 1
    assert stats["funnel"]["activation_rate"] is not None


def test_nurturing_email_channel_priority_and_web_users(db_session: Session):
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    settings = db_session.query(SystemSettings).first() or SystemSettings(id=1)
    settings.onboarding_reminders_enabled = True
    settings.onboarding_reminders_rollout_at = (now - timedelta(days=30)).isoformat()
    db_session.add(settings)

    # 1. Pure Web User (registered via website/Yandex, 0 jobs, 26h ago)
    client_web = Client(
        telegram_id=f"web:{uuid.uuid4().hex[:12]}",
        name="ООО Веб Клиент",
        is_active=True,
        marketing_unsubscribed=False,
        created_at=now - timedelta(hours=26),
    )
    db_session.add(client_web)
    db_session.flush()
    web_user = WebUser(
        client_id=client_web.id,
        email="client_web@tenderlex.ru",
        name="ООО Веб Клиент",
        is_active=True,
        is_email_verified=True,
        marketing_unsubscribed=False,
    )
    db_session.add(web_user)

    # 2. Dual-channel User who works in Web cabinet (created job via web cabinet, no created_by_telegram_id)
    t_dual_web = str(uuid.uuid4().int)[:10]
    client_dual_web = Client(
        telegram_id=f"web:{uuid.uuid4().hex[:12]}",
        name="ООО Веб И ТГ",
        is_active=True,
        marketing_unsubscribed=False,
        money_balance_kopeks=20000,
        created_at=now - timedelta(days=4),
    )
    db_session.add(client_dual_web)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_dual_web.id, telegram_id=t_dual_web, is_active=True))
    db_session.add(
        WebUser(
            client_id=client_dual_web.id,
            email="dual_web@tenderlex.ru",
            name="Иван",
            is_active=True,
            is_email_verified=True,
            marketing_unsubscribed=False,
        )
    )
    # Completed job created in web cabinet (created_by_telegram_id is empty) 50h ago
    db_session.add(Job(client_id=client_dual_web.id, status="completed", created_by_telegram_id="", created_at=now - timedelta(hours=50)))

    # 3. Dual-channel User who works in Telegram bot (created job via bot, created_by_telegram_id is numeric)
    t_dual_tg = str(uuid.uuid4().int)[:10]
    client_dual_tg = Client(
        telegram_id=t_dual_tg,
        name="ООО ТГ Юзер",
        is_active=True,
        marketing_unsubscribed=False,
        money_balance_kopeks=20000,
        created_at=now - timedelta(days=4),
    )
    db_session.add(client_dual_tg)
    db_session.flush()
    db_session.add(ClientTelegramAccount(client_id=client_dual_tg.id, telegram_id=t_dual_tg, is_active=True))
    db_session.add(
        WebUser(
            client_id=client_dual_tg.id,
            email="dual_tg@tenderlex.ru",
            name="Петр",
            is_active=True,
            is_email_verified=True,
            marketing_unsubscribed=False,
        )
    )
    # Completed job created in Telegram bot
    db_session.add(Job(client_id=client_dual_tg.id, status="completed", created_by_telegram_id=t_dual_tg, created_at=now - timedelta(hours=50)))

    db_session.commit()

    candidates = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)

    # Check 1: Web-only user receives email
    web_candidates = [c for c in candidates if c.client_id == client_web.id]
    assert len(web_candidates) == 1
    assert web_candidates[0].channel == "email"
    assert web_candidates[0].recipient == "client_web@tenderlex.ru"
    assert web_candidates[0].step == "step1"

    # Check 2: Dual user working in Web cabinet prioritizes email
    dual_web_candidates = [c for c in candidates if c.client_id == client_dual_web.id]
    assert len(dual_web_candidates) == 1
    assert dual_web_candidates[0].channel == "email"
    assert dual_web_candidates[0].recipient == "dual_web@tenderlex.ru"
    assert dual_web_candidates[0].step == "step2"

    # Check 3: Dual user working in Telegram prioritizes telegram
    dual_tg_candidates = [c for c in candidates if c.client_id == client_dual_tg.id]
    assert len(dual_tg_candidates) == 1
    assert dual_tg_candidates[0].channel == "telegram"
    assert dual_tg_candidates[0].recipient == t_dual_tg
    assert dual_tg_candidates[0].step == "step2"

    # Check 4: Anti-spam — once a step is claimed or sent, no duplicate sending on either channel
    db_session.add(
        OnboardingReminder(
            client_id=client_web.id,
            channel="email",
            step="step1",
            status="sent",
            sent_at=now - timedelta(hours=1),
        )
    )
    db_session.commit()

    candidates_after = get_due_nurturing_candidates(db_session, settings, current_time=now, enforce_work_hours=False)
    assert not any(c.client_id == client_web.id and c.step == "step1" for c in candidates_after)

