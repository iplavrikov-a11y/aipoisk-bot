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


def test_task_cost_normalization():
    import uuid
    from app.outreach_api import _normalize_task_cost

    db = SessionLocal()
    try:
        task_id = f"test-cost-{uuid.uuid4().hex[:8]}"
        task = OutreachSearchTask(
            id=task_id,
            name="Тест себестоимости",
            prompt="тестовый промпт",
            target_count=500,
            collected_count=500,
            scanned_sites=600,
            queries_count=50,
            status="completed",
            total_cost_rub=0.0,
            yandex_cost_rub=0.0,
        )
        db.add(task)
        db.commit()

        _normalize_task_cost(task, db)
        assert task.yandex_requests > 0
        assert task.yandex_cost_rub > 0.0
        assert task.total_cost_rub > 0.0

        db.delete(task)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_extend_search_task_endpoint(monkeypatch):
    import uuid
    from app.outreach_api import extend_search_task, ExtendSearchRequest

    # Mock background search coroutine so tests do not spawn background tasks in DB
    async def mock_run(*args, **kwargs):
        pass

    monkeypatch.setattr("app.outreach_api.run_outreach_search_task", mock_run)

    db = SessionLocal()
    try:
        t_id = f"test-extend-{uuid.uuid4().hex[:8]}"
        l_id = f"lead-extend-{uuid.uuid4().hex[:8]}"
        task = OutreachSearchTask(
            id=t_id,
            name="Тест добора",
            prompt="поставка насосного оборудования",
            target_count=100,
            collected_count=100,
            status="completed",
        )
        lead = OutreachLead(
            id=l_id,
            task_id=task.id,
            email=f"{l_id}@nasos-test.ru",
            company_name="ООО НасосТест",
            website="https://nasos-test.ru",
            status="new",
        )
        db.add_all([task, lead])
        db.commit()

        req = ExtendSearchRequest(extra_count=500, additional_prompt="промышленные насосы")
        res = await extend_search_task(task.id, req, db)

        assert res["ok"] is True
        assert res["target_count"] == 1 + 500
        assert res["task"]["status"] == "running"
        assert res["wave_index"] == 2
        assert len(res["task"]["waves"]) == 2
    finally:
        try:
            db.query(OutreachLead).filter(OutreachLead.task_id == t_id).delete()
            db.query(OutreachSearchTask).filter(OutreachSearchTask.id == t_id).delete()
            db.commit()
        except Exception:
            pass
        db.close()


def test_list_leads_wave_filter():
    import uuid
    from app.outreach_api import list_leads

    db = SessionLocal()
    try:
        t_id = f"test-task-{uuid.uuid4().hex[:8]}"
        task = OutreachSearchTask(
            id=t_id,
            name="Тест волн",
            prompt="тест",
            target_count=20,
            collected_count=2,
            status="completed",
        )
        l1 = OutreachLead(
            id=f"lead-w1-{uuid.uuid4().hex[:8]}",
            task_id=t_id,
            wave_index=1,
            email="lead1@w1.ru",
            company_name="ООО Волна 1",
            status="new",
        )
        l2 = OutreachLead(
            id=f"lead-w2-{uuid.uuid4().hex[:8]}",
            task_id=t_id,
            wave_index=2,
            email="lead2@w2.ru",
            company_name="ООО Волна 2",
            status="new",
        )
        db.add_all([task, l1, l2])
        db.commit()

        # All leads
        res_all = list_leads(task_id=t_id, db=db)
        assert res_all["total"] == 2

        # Filter wave 1
        res_w1 = list_leads(task_id=t_id, wave=1, db=db)
        assert res_w1["total"] == 1
        assert res_w1["items"][0]["email"] == "lead1@w1.ru"

        # Filter wave 2
        res_w2 = list_leads(task_id=t_id, wave=2, db=db)
        assert res_w2["total"] == 1
        assert res_w2["items"][0]["email"] == "lead2@w2.ru"

        # Cleanup
        db.delete(l1)
        db.delete(l2)
        db.delete(task)
        db.commit()
    finally:
        db.close()


def test_mark_all_inbox_read():
    import uuid
    from app.outreach_api import mark_all_inbox_read
    from app.outreach_models import OutreachIncomingEmail

    db = SessionLocal()
    try:
        m1 = OutreachIncomingEmail(
            id=f"msg-b-{uuid.uuid4().hex[:8]}",
            sender_email="mailer-daemon@yandex.ru",
            subject="Delivery status notification (failure)",
            body_text="Mail delivery failed",
            category="bounce",
            is_read=False,
        )
        m2 = OutreachIncomingEmail(
            id=f"msg-s-{uuid.uuid4().hex[:8]}",
            sender_email="spam@spam.com",
            subject="Casino bonus",
            body_text="Click here",
            category="spam",
            is_spam=True,
            is_read=False,
        )
        db.add_all([m1, m2])
        db.commit()

        # Mark bounces read
        res_b = mark_all_inbox_read(category="bounces", db=db)
        assert res_b["ok"] is True
        db.refresh(m1)
        db.refresh(m2)
        assert m1.is_read is True
        assert m2.is_read is False

        # Mark spam read
        res_s = mark_all_inbox_read(category="spam", db=db)
        assert res_s["ok"] is True
        db.refresh(m2)
        assert m2.is_read is True

        # Cleanup
        db.delete(m1)
        db.delete(m2)
        db.commit()
    finally:
        db.close()


def test_outreach_search_pause_resume_and_queue():
    import json
    import uuid
    from pathlib import Path
    from app.outreach_api import pause_search_task, resume_search_task, get_queue_info
    from app.outreach_models import OutreachSearchTask

    db = SessionLocal()
    task_id = f"test-pause-{uuid.uuid4().hex[:8]}"
    queue_file = Path(f"data/outreach_queue_{task_id}.json")
    try:
        task = OutreachSearchTask(
            id=task_id,
            name="Тест паузы",
            prompt="тест",
            target_count=500,
            collected_count=50,
            status="running",
            waves_json=json.dumps([{"wave": 1, "status": "running", "target": 500, "collected": 50}]),
        )
        db.add(task)
        db.commit()

        # 1. Create a mock queue file
        queue_file.write_text(
            json.dumps({
                "task_id": task_id,
                "wave_index": 1,
                "processed_idx": 10,
                "candidates": [{"title": f"Site {i}", "url": f"https://site{i}.ru", "domain": f"site{i}.ru"} for i in range(50)],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        # 2. Check get_queue_info
        q_info = get_queue_info(task_id)
        assert q_info["has_queue"] is True
        assert q_info["total"] == 50
        assert q_info["remaining"] == 40

        # 3. Pause task
        p_res = pause_search_task(task_id, db)
        assert p_res["ok"] is True
        assert p_res["status"] == "paused"
        db.refresh(task)
        assert task.status == "paused"

        # 4. Check waves_json updated to paused
        waves = json.loads(task.waves_json)
        assert waves[0]["status"] == "paused"

        # Clean up
        db.delete(task)
        db.commit()
    finally:
        queue_file.unlink(missing_ok=True)
        db.close()


def test_spintax_rendering():
    from app.outreach_mail import render_spintax, render_template_text
    
    # Simple spintax
    tpl = "{Здравствуйте|Добрый день|Приветствую}"
    rendered = {render_spintax(tpl) for _ in range(30)}
    assert len(rendered) > 1
    assert all(r in {"Здравствуйте", "Добрый день", "Приветствую"} for r in rendered)

    # Nested spintax with template variables
    complex_tpl = "{Здравствуйте|Добрый день}, {company}! {Мы создали {сервис|платформу}|Предлагаем решение} TenderLex."
    lead = OutreachLead(company_name="ООО Вектор")
    results = [render_template_text(complex_tpl, lead) for _ in range(20)]
    assert any("сервис" in r for r in results)
    assert any("платформу" in r for r in results)
    assert all("ООО Вектор" in r for r in results)


def test_clean_email_filters():
    from app.outreach_search import _clean_email

    # Corrupted URL encodings
    assert _clean_email("20info@profit-tender.com") == "info@profit-tender.com"
    assert _clean_email("%20zakaz@zavod.ru") == "zakaz@zavod.ru"
    assert _clean_email("3dinfo@metall.ru") == "info@metall.ru"

    # Blocked placeholder emails
    assert _clean_email("name@example.com") == ""
    assert _clean_email("mail@example.com") == ""
    assert _clean_email("your@email.com") == ""
    assert _clean_email("rating@mail.ru") == ""
    assert _clean_email("email@mail.ru") == ""
    assert _clean_email("k.saf@vashsait.ru") == ""
    assert _clean_email("test@sample.com") == ""
    assert _clean_email("test1@site.ru") == ""

    # Blocked support & ticket queues
    assert _clean_email("support@kwork.ru") == ""
    assert _clean_email("help@sravni.ru") == ""
    assert _clean_email("claim@team.profi.ru") == ""
    assert _clean_email("abuse@domain.ru") == ""
    assert _clean_email("ticket@service.ru") == ""
    assert _clean_email("ebs_support@znanium.ru") == ""

    # Valid corporate & commercial emails
    assert _clean_email("snab@zavod-kabel.ru") == "snab@zavod-kabel.ru"
    assert _clean_email("sale@gts24.com") == "sale@gts24.com"
    assert _clean_email("info@emiko.ru") == "info@emiko.ru"


@pytest.mark.asyncio
async def test_email_deliverability_verification():
    from app.outreach_mail import verify_email_deliverability

    # Invalid junk
    ok1, reason1 = await verify_email_deliverability("name@example.com")
    assert ok1 is False

    ok2, reason2 = await verify_email_deliverability("help@sravni.ru")
    assert ok2 is False

    ok3, reason3 = await verify_email_deliverability("user@tempmail.com")
    assert ok3 is False

    # Valid domain
    ok4, reason4 = await verify_email_deliverability("info@yandex.ru")
    assert ok4 is True


def test_database_cleanup_endpoint():
    from app.outreach_api import cleanup_leads_database, DatabaseCleanupRequest
    
    db = SessionLocal()
    try:
        # Create test leads (1 corrupted prefix, 1 placeholder, 1 valid)
        lead_corrupt = OutreachLead(
            email="20info@test-cleanup-factory.ru",
            company_name="ООО Тест Префикс",
            status="new",
            mx_valid=True,
        )
        lead_junk = OutreachLead(
            email="name@example.com",
            company_name="ООО Пример",
            status="new",
            mx_valid=True,
        )
        lead_valid = OutreachLead(
            email="zakaz@test-cleanup-valid-factory.ru",
            company_name="ООО Завод Валидный",
            status="new",
            mx_valid=True,
        )
        db.add_all([lead_corrupt, lead_junk, lead_valid])
        db.commit()

        # Run cleanup
        res = cleanup_leads_database(DatabaseCleanupRequest(), db=db)
        assert res["ok"] is True
        assert res["fixed_prefixes"] >= 1
        assert res["invalidated"] >= 1

        db.refresh(lead_corrupt)
        db.refresh(lead_junk)
        db.refresh(lead_valid)

        assert lead_corrupt.email == "info@test-cleanup-factory.ru"
        assert lead_junk.status == "invalid"
        assert lead_junk.mx_valid is False
        assert lead_valid.status == "new"

        # Cleanup
        db.delete(lead_corrupt)
        db.delete(lead_junk)
        db.delete(lead_valid)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dobor_query_generation_and_deduplication():
    from app.outreach_search import generate_search_queries_matrix
    from app.models import SystemSettings

    empty_settings = SystemSettings(id=1)
    prompt = "Поставщики кабельной продукции и электротехники"
    executed = {"поставщики кабельной продукции дистрибьютор оптовые поставки москва -\"банковская гарантия\" -\"обучение\""}

    # Test wave 1 fallback
    q_wave1, _ = await generate_search_queries_matrix(prompt, count=100, sys_settings=empty_settings, is_extend=False, wave_index=1)
    assert len(q_wave1) > 0
    assert any("москва" in q.lower() or "спб" in q.lower() or "россия" in q.lower() for q in q_wave1)

    # Test dobor wave 2 with deduplication against executed
    q_dobor, _ = await generate_search_queries_matrix(
        prompt,
        count=100,
        sys_settings=empty_settings,
        is_extend=True,
        wave_index=2,
        existing_count=500,
        executed_queries=executed,
    )
    assert len(q_dobor) > 0
    # Make sure the already executed query was excluded
    for q in q_dobor:
        assert q.strip().lower() not in executed
    # Make sure dobor queries contain regional / supply distribution markers
    assert any("снабжение" in q.lower() or "склад" in q.lower() or "екатеринбург" in q.lower() or "казань" in q.lower() for q in q_dobor)


@pytest.mark.asyncio
async def test_dobor_query_generation_with_ai_mock(monkeypatch):
    import json
    from app.outreach_search import generate_search_queries_matrix
    from app.models import SystemSettings

    mock_queries = [
        "поставщики кабеля ввгнг москва склад",
        "дистрибьютор силовой кабель екатеринбург",
        "трансформаторы и ктп казань оптом",
        "старый запрос который уже выполнялся",
    ]

    async def mock_call_llm(settings, user_prompt, system_prompt="", tier="light", json_mode=True, timeout_seconds=40):
        assert "ДОБОРА" in system_prompt or "Волна #3" in user_prompt
        return json.dumps(mock_queries)

    monkeypatch.setattr("app.outreach_search.call_llm", mock_call_llm)

    executed = {"старый запрос который уже выполнялся"}
    settings = SystemSettings(id=1, primary_provider="polza", primary_model="gpt-4o-mini")

    queries, cost = await generate_search_queries_matrix(
        "Кабель и электротехника оптом",
        count=100,
        sys_settings=settings,
        is_extend=True,
        wave_index=3,
        existing_count=1200,
        executed_queries=executed,
    )

    assert len(queries) == 3
    assert "старый запрос который уже выполнялся" not in queries
    assert "дистрибьютор силовой кабель екатеринбург" in queries


@pytest.mark.asyncio
async def test_complex_supply_and_manufacturer_filtering(monkeypatch):
    import json
    from app.outreach_search import generate_search_queries_matrix, ai_review_outreach_lead
    from app.models import SystemSettings

    # 1. Test query matrix system prompt for tender complex supply
    async def mock_call_llm_supply(settings, user_prompt, system_prompt="", tier="light", json_mode=True, timeout_seconds=40):
        sys_lower = system_prompt.lower()
        assert "комплексного снабжения" in sys_lower or "торговых домов" in sys_lower
        assert "запрещено" in sys_lower or "не ищи заводы" in sys_lower
        return json.dumps(["комплексное снабжение предприятий ТМЦ екатеринбург -завод"])

    monkeypatch.setattr("app.outreach_search.call_llm", mock_call_llm_supply)
    custom_ai = json.dumps([{"id": "p1", "baseUrl": "https://api.polza.ai", "apiKey": "mock_key"}])
    settings = SystemSettings(id=1, custom_ai_providers_json=custom_ai, primary_provider="polza", primary_model="gpt-4o-mini")

    prompt = "Участники тендеров, поставщики, подрядчики по 44-ФЗ и 223-ФЗ, сопровождение закупок и снабжение. Комплексные поставщики промышленного оборудования"
    queries, _ = await generate_search_queries_matrix(prompt, count=100, sys_settings=settings, is_extend=True, wave_index=2)
    assert len(queries) == 1
    assert "комплексное снабжение" in queries[0]

    # 2. Test ai_review_outreach_lead rejects manufacturers when complex supply is requested
    async def mock_call_llm_review_mfr(settings, user_prompt, system_prompt="", tier="light", json_mode=True, timeout_seconds=40):
        return json.dumps({
            "is_relevant": True,  # even if LLM said true, site_type=manufacturer must be rejected
            "score": 85,
            "site_type": "manufacturer",
            "activity_profile": "Завод по производству насосов",
            "reason": "Завод производитель",
        })

    monkeypatch.setattr("app.outreach_search.call_llm", mock_call_llm_review_mfr)
    crawled_factory = {
        "plain_text": "Завод производитель насосов КМ 80",
        "page_title": "Завод насосов",
        "company_name": "ООО Завод Насос",
        "website": "https://zavod-nasos.ru",
        "activity_profile": "Завод насосов",
    }
    reviewed, _ = await ai_review_outreach_lead(crawled_factory, prompt, sys_settings=settings)
    assert reviewed is None  # Must be rejected because site_type == manufacturer!


def test_outreach_thread_endpoints():
    from app.outreach_api import get_inbox_message_thread, get_lead_thread

    db = SessionLocal()
    try:
        # Create a lead
        lead = OutreachLead(
            email="thread-supplier@example.com",
            company_name="ООО Поставщик Тред",
            phone="+7 999 555-44-33",
            website="https://thread-supplier.com",
            inn="7701234567",
            status="replied",
            mx_valid=True,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        # Create incoming message
        inc_msg = OutreachIncomingEmail(
            message_id="msg-thread-1",
            sender_email="thread-supplier@example.com",
            sender_name="Менеджер Иван",
            subject="Re: Запрос цен на инструмент",
            body_text="Добрый день! Готовы поставить инструмент со скидкой 10%.",
            category="reply",
            is_read=False,
            lead_id=lead.id,
        )
        db.add(inc_msg)

        # Create sent log
        sent_log = OutreachSendLog(
            recipient_email="thread-supplier@example.com",
            recipient_company="ООО Поставщик Тред",
            subject="Запрос цен на инструмент",
            status="sent",
            lead_id=lead.id,
        )
        db.add(sent_log)
        db.commit()
        db.refresh(inc_msg)

        # 1. Test get_inbox_message_thread
        thread_res = get_inbox_message_thread(message_id=inc_msg.id, db=db)
        assert thread_res["ok"] is True
        assert thread_res["contact_email"] == "thread-supplier@example.com"
        assert thread_res["lead"]["company_name"] == "ООО Поставщик Тред"
        assert len(thread_res["items"]) == 2
        assert thread_res["total_incoming"] == 1
        assert thread_res["total_outgoing"] == 1

        # 2. Test get_lead_thread
        lead_thread_res = get_lead_thread(lead_id=lead.id, db=db)
        assert lead_thread_res["ok"] is True
        assert lead_thread_res["contact_email"] == "thread-supplier@example.com"
        assert len(lead_thread_res["items"]) == 2

        # Cleanup
        db.delete(inc_msg)
        db.delete(sent_log)
        db.delete(lead)
        db.commit()
    finally:
        db.close()


def test_html_to_plain_text_and_body_extraction():
    from email.message import EmailMessage
    from app.outreach_mail import looks_like_html, html_to_plain_text, extract_email_bodies

    # 1. Test looks_like_html
    assert looks_like_html('<table style="border-collapse:collapse"><tr><td>Test</td></tr></table>') is True
    assert looks_like_html('<html><body><p>Hello world</p></body></html>') is True
    assert looks_like_html('<div>Plain-looking text inside div</div>') is True
    assert looks_like_html('Just simple plain text message from supplier without any tags.') is False
    assert looks_like_html('') is False

    # 2. Test html_to_plain_text
    raw_html = '''
    <style>body { font-size: 14px; }</style>
    <div class="msg">
        <p>Добрый день!</p>
        <p>Ваше обращение <b>№ АА-198138</b> от 27.08.2026 получено.</p>
        <table border="1">
            <tr><th>Товар</th><th>Цена</th></tr>
            <tr><td>Кабель ВВГнг 3x2.5</td><td>120 руб/м</td></tr>
        </table>
        <br/>
        С уважением,<br/>
        Отдел продаж
    </div>
    '''
    clean_txt = html_to_plain_text(raw_html)
    assert "<style>" not in clean_txt
    assert "<b>" not in clean_txt
    assert "<tr>" not in clean_txt
    assert "Добрый день!" in clean_txt
    assert "№ АА-198138" in clean_txt
    assert "Кабель ВВГнг 3x2.5" in clean_txt
    assert "120 руб/м" in clean_txt
    assert "Отдел продаж" in clean_txt

    # 3. Test extract_email_bodies on multipart email
    msg = EmailMessage()
    msg["Subject"] = "Тест КП"
    msg["From"] = "supplier@pro-solution.ru"
    msg["To"] = "info@tenderlex.ru"
    msg.set_content("Простой текст")
    msg.add_alternative("<h1>КП</h1><p>Текст предложения</p>", subtype="html")

    txt, htm = extract_email_bodies(msg)
    assert "Простой текст" in txt
    assert "КП" in htm
    assert "<p>Текст предложения</p>" in htm

    # 4. Test extract_email_bodies when text/plain is raw HTML
    msg_corrupt = EmailMessage()
    msg_corrupt["Subject"] = "Ответ от 1C"
    msg_corrupt["From"] = "1c@pro-solution.ru"
    msg_corrupt["To"] = "info@tenderlex.ru"
    msg_corrupt.set_content('<table width="100%"><tr><td>Заказ принят в работу</td></tr></table>')

    txt_c, htm_c = extract_email_bodies(msg_corrupt)
    assert "Заказ принят в работу" in txt_c
    assert "<table" not in txt_c
    assert "<table" in htm_c









