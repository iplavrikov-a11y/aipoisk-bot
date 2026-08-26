import pytest
from app.db import Base, SessionLocal, engine, init_db
from app.outreach_models import (
    OutreachCampaign,
    OutreachIncomingEmail,
    OutreachLead,
    OutreachSearchTask,
    OutreachSendLog,
    OutreachSettings,
)
from app.outreach_mail import render_template_text
from app.supplier_search import email_has_valid_mx


def setup_module():
    init_db()


def test_outreach_lead_crud():
    db = SessionLocal()
    try:
        # Create lead
        lead = OutreachLead(
            email="test-lead@example.ru",
            company_name="ООО Тест Поставка",
            phone="+7 999 123-45-67",
            website="https://test-lead.ru",
            category="Металлопрокат",
            status="new",
            mx_valid=True,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        assert lead.id is not None
        assert lead.email == "test-lead@example.ru"
        assert lead.company_name == "ООО Тест Поставка"
        assert lead.status == "new"

        # Query lead
        fetched = db.query(OutreachLead).filter(OutreachLead.email == "test-lead@example.ru").first()
        assert fetched is not None
        assert fetched.company_name == "ООО Тест Поставка"

        # Cleanup
        db.delete(fetched)
        db.commit()
    finally:
        db.close()


def test_render_template_text():
    lead = OutreachLead(
        email="info@metall-prom.ru",
        company_name="АО МеталлПром",
        city="Екатеринбург",
        website="https://metall-prom.ru",
    )
    tpl = "Здравствуйте, {company}! Мы видим вашу компанию в г. {city}. Ваш сайт {site}."
    rendered = render_template_text(tpl, lead)
    assert "АО МеталлПром" in rendered
    assert "Екатеринбург" in rendered
    assert "https://metall-prom.ru" in rendered


@pytest.mark.asyncio
async def test_validate_mx():
    # Valid domain (yandex.ru or mail.ru)
    assert await email_has_valid_mx("info@yandex.ru") is True
    # Invalid domain
    assert await email_has_valid_mx("info@invalid-nonexistent-domain-1234567890.xyz") is False
    assert await email_has_valid_mx("test@invalid-domain-99999.ru") is False


def test_outreach_settings_singleton():
    db = SessionLocal()
    try:
        settings = db.query(OutreachSettings).filter(OutreachSettings.id == 1).first()
        if not settings:
            settings = OutreachSettings(id=1, from_email="info@tenderlex.ru")
            db.add(settings)
            db.commit()
            db.refresh(settings)

        assert settings.from_email == "info@tenderlex.ru"
        data = settings.to_dict(include_secrets=False)
        assert data["from_email"] == "info@tenderlex.ru"
    finally:
        db.close()


def test_outreach_search_task_crud():
    db = SessionLocal()
    try:
        task = OutreachSearchTask(
            name="Тестовый поиск поставщиков",
            prompt="поставщики кабеля и электротехники",
            target_count=500,
            status="completed",
            collected_count=450,
            yandex_requests=120,
            yandex_cost_rub=4.80,
            llm_cost_rub=0.50,
            total_cost_rub=5.30,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        assert task.id is not None
        assert task.name == "Тестовый поиск поставщиков"
        assert task.total_cost_rub == 5.30
        d = task.to_dict()
        assert d["cost_label"] == "5.30 ₽"
        assert d["collected_count"] == 450

        # Cleanup
        db.delete(task)
        db.commit()
    finally:
        db.close()


def test_outreach_stats_counts_sent_and_replied():
    from app.outreach_api import get_task_stats
    db = SessionLocal()
    try:
        task = OutreachSearchTask(
            id="test-task-stats-123",
            name="Тестовая задача",
            prompt="тест",
            target_count=10,
        )
        lead_new = OutreachLead(
            id="lead-test-new",
            task_id=task.id,
            email="new@test.ru",
            status="new",
            mx_valid=True,
        )
        lead_sent = OutreachLead(
            id="lead-test-sent",
            task_id=task.id,
            email="sent@test.ru",
            status="sent",
            sent_count=1,
            mx_valid=True,
        )
        lead_replied = OutreachLead(
            id="lead-test-replied",
            task_id=task.id,
            email="replied@test.ru",
            status="replied",
            reply_received=True,
            sent_count=1,
            mx_valid=True,
        )
        db.add_all([task, lead_new, lead_sent, lead_replied])
        db.commit()

        stats = get_task_stats(task.id, db)
        assert stats["total_leads"] == 3
        assert stats["new_leads"] == 1
        assert stats["sent_leads"] == 2  # sent + replied
        assert stats["replied_leads"] == 1
        assert stats["mx_valid_leads"] == 3

        db.delete(lead_new)
        db.delete(lead_sent)
        db.delete(lead_replied)
        db.delete(task)
        db.commit()
    finally:
        db.close()


def test_is_spam_message_detection():
    from app.outreach_mail import is_spam_message

    # 1. Spammer domains
    is_sp, reason = is_spam_message("Привет", "текст", "Иван", "eyxowql@rumixos.shop")
    assert is_sp is True
    assert "rumixos.shop" in reason

    is_sp, reason = is_spam_message("Рассылка", "текст", "Служба", "test@thespacebanana.com")
    assert is_sp is True

    # 2. Makita & tool keywords
    is_sp, reason = is_spam_message("Аккумуляторный секатор Makita", "распродажа со склада", "Инструмент", "sales@some-store.ru")
    assert is_sp is True

    # 3. Water heaters
    is_sp, reason = is_spam_message("Горячая вода за 3 секунды", "бойлеры косвенного нагрева", "Менеджер", "boiler@random.ru")
    assert is_sp is True

    # 4. Tarot / Love-coach / Scam
    is_sp, reason = is_spam_message("3 секрета ярких любовных отношений", "вебинар для женщин", "Ева | Love-коуч", "eva@love.ru")
    assert is_sp is True

    # 5. Mass email pitch
    is_sp, reason = is_spam_message("Разошлем ваше коммерческое предложение", "база директоров РФ", "Рассылки89299788445", "promo@mailer.ru")
    assert is_sp is True

    # 6. Real supplier replies must NOT be flagged as spam
    is_sp, reason = is_spam_message(
        "Re: Запрос КП: Задвижка чугунная фланцевая",
        "Добрый день! Во вложении счет и коммерческое предложение на задвижки.",
        "ООО Трубопроводная Арматура",
        "sales@trubarm.ru",
        has_lead_match=True,
    )
    assert is_sp is False
    assert reason == ""

    # 7. Custom rule matching
    custom_rules = [{"type": "domain", "value": "customspammer.xyz"}]
    is_sp, reason = is_spam_message("Тест", "Обычный текст", "Менеджер", "info@customspammer.xyz", custom_rules=custom_rules)
    assert is_sp is True
    assert "customspammer.xyz" in reason

