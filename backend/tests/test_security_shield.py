from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app, require_admin
from app.models import SecurityEvent, SupportBlockedActor, SystemSettings, WebRegistrationAttempt
from app.security_shield import (
    _challenge_secret,
    classify_and_reply_support_message,
    create_human_challenge,
    detect_attack_payload,
    get_support_work_hours_status,
    is_automated_user_agent,
    is_disposable_or_garbage_email,
    maybe_auto_block_actor,
    record_security_event,
    validate_guest_contact,
    validate_optional_phone,
    verify_human_challenge,
)
from app.support_chat import notify_admins_of_incoming_message


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[require_admin] = lambda: "admin"
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_real_user_inputs_never_false_positive():
    assert detect_attack_payload('ООО "Техно-Снаб"') is None
    assert detect_attack_payload("Иван Петров-Сидоров") is None
    assert detect_attack_payload("Подскажите, сколько стоит подбор поставщиков по 44-ФЗ?") is None
    assert detect_attack_payload("Select cable from table 2") is None
    assert detect_attack_payload("onload = 15 kN") is None
    assert detect_attack_payload("curl https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0177200000926002782") is None

    assert is_disposable_or_garbage_email("ivan.petrov@yandex.ru") is None
    assert is_disposable_or_garbage_email("89199598403@mail.ru") is None
    assert is_disposable_or_garbage_email("zakupki@stroymash-group.ru") is None
    assert is_disposable_or_garbage_email("admin@stroymash.ru") is None

    assert validate_optional_phone("") is None
    assert validate_optional_phone("+7 (919) 959-84-03") is None

    assert validate_guest_contact("+7 916 555-33-22") is None
    assert validate_guest_contact("manager@company.ru") is None
    assert validate_guest_contact("@tender_manager") is None

    assert not is_automated_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")


def test_attack_and_garbage_inputs_detected():
    assert detect_attack_payload("-1' OR 2+781-781-1=0+0+0+1") is not None
    assert detect_attack_payload("UNION ALL SELECT 1,2,3") is not None
    assert detect_attack_payload("ls -l") is not None
    assert detect_attack_payload("whoami") is not None
    assert detect_attack_payload("uname -a") is not None
    assert detect_attack_payload("; cat /etc/passwd") is not None
    assert detect_attack_payload("../../etc/passwd") is not None
    assert detect_attack_payload('/"/') is not None
    assert detect_attack_payload("<script>alert(1)</script>") is not None
    assert detect_attack_payload("<svg/onload=alert(1)>") is not None

    assert is_disposable_or_garbage_email("sixiva3610@nbasweeps.com") is not None
    assert is_disposable_or_garbage_email("1@mail.ru") is not None
    assert is_disposable_or_garbage_email("admin@mail.ru") is not None

    assert validate_optional_phone("123") is not None
    assert validate_optional_phone("+7 (123) 456-78-9") is not None

    assert validate_guest_contact("admin") is not None
    assert validate_guest_contact("123") is not None
    assert validate_guest_contact("x") is not None

    assert is_automated_user_agent("curl/8.22.0")


def test_human_challenge_roundtrip():
    ch = create_human_challenge()
    ok_fast, reason_fast = verify_human_challenge(ch["token"], min_elapsed_sec=5.0)
    assert not ok_fast
    assert reason_fast == "submitted_too_fast"

    ok_now, reason_now = verify_human_challenge(ch["token"], min_elapsed_sec=0.0)
    assert ok_now
    assert reason_now == "ok"


def test_support_work_hours_calculation():
    settings = SystemSettings(
        support_work_hours_enabled=True,
        support_work_hours_start="09:00",
        support_work_hours_end="20:00",
        support_timezone_offset=3,
        support_quiet_night_notifications=True,
    )
    day_utc = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)  # 13:00 MSK
    night_utc = datetime(2026, 11, 15, 22, 0, tzinfo=timezone.utc)  # 01:00 MSK

    assert get_support_work_hours_status(settings, now=day_utc)["is_open"] is True
    night_status = get_support_work_hours_status(settings, now=night_utc)
    assert night_status["is_open"] is False
    assert "09:00" in night_status["notice"]


def test_register_blocks_sqli_and_disposable_allows_real_user(client: TestClient):
    headers = {"X-Forwarded-For": "198.51.100.42"}
    # 1. SQLi in name blocked
    res_sqli = client.post(
        "/api/customer/auth/register",
        headers=headers,
        json={
            "email": "realuser_sqli_check@yandex.ru",
            "password": "StrongPassword123!",
            "name": "-1' OR 2+781-781-1=0+0+0+1",
            "terms_accepted": True,
            "personal_data_consent": True,
        },
    )
    assert res_sqli.status_code == 400

    # 2. Disposable email blocked
    res_disp = client.post(
        "/api/customer/auth/register",
        headers=headers,
        json={
            "email": "sixiva3610@nbasweeps.com",
            "password": "StrongPassword123!",
            "name": "Тест",
            "terms_accepted": True,
            "personal_data_consent": True,
        },
    )
    assert res_disp.status_code == 400

    # 3. Real user succeeds
    unique_email = f"real.partner.{int(datetime.now().timestamp())}@yandex.ru"
    res_ok = client.post(
        "/api/customer/auth/register",
        headers=headers,
        json={
            "email": unique_email,
            "password": "StrongPassword123!",
            "name": 'ООО "СтройКомплект"',
            "phone": "+7 (916) 444-55-66",
            "terms_accepted": True,
            "personal_data_consent": True,
        },
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["authenticated"] is True


def test_guest_chat_anti_spam_and_real_flow(client: TestClient):
    ts = int(datetime.now().timestamp() * 1000)
    sid_spam = f"sess_shield_spam_{ts}"

    # 1. Garbage contact rejected (violation #1)
    r_bad_contact = client.post(
        "/api/public/guest-chat/send",
        json={"sessionId": sid_spam, "text": "[Контакт сохранен]: admin"},
    )
    assert r_bad_contact.status_code == 400

    # 2. CLI probe rejected (violation #2 -> triggers auto-block on guest_session threshold=2)
    r_probe = client.post(
        "/api/public/guest-chat/send",
        json={"sessionId": sid_spam, "text": "ls -l"},
    )
    assert r_probe.status_code == 400

    # 2b. Spammer session is now auto-blocked with 403
    r_blocked = client.post(
        "/api/public/guest-chat/send",
        json={"sessionId": sid_spam, "text": "Здравствуйте!"},
    )
    assert r_blocked.status_code == 403

    # 3. Legitimate visitor session succeeds
    sid = f"sess_shield_real_{ts}"
    with patch("app.main.notify_admins_of_incoming_message", new_callable=AsyncMock) as mock_notify:
        r_ok = client.post(
            "/api/public/guest-chat/send",
            json={
                "sessionId": sid,
                "text": "Здравствуйте! Нужен подбор поставщиков по ТЗ.",
                "preset": "🔍 Подбор поставщиков по ТЗ",
            },
        )
        assert r_ok.status_code == 200
        assert r_ok.json()["success"] is True
        assert mock_notify.await_count == 1

        # 4. Immediate duplicate blocked
        r_dup = client.post(
            "/api/public/guest-chat/send",
            json={
                "sessionId": sid,
                "text": "Здравствуйте! Нужен подбор поставщиков по ТЗ.",
                "preset": "🔍 Подбор поставщиков по ТЗ",
            },
        )
        assert r_dup.status_code == 429


@pytest.mark.asyncio
async def test_quiet_night_skips_admin_dm():
    db = SessionLocal()
    try:
        with patch("app.support_chat._tg_api_post", new_callable=AsyncMock) as mock_tg:
            mock_tg.return_value = {"ok": True, "result": {"message_id": 101}}
            summary = await notify_admins_of_incoming_message(
                db,
                guest_session_id="sess_night_test_01",
                text="Ночной вопрос по тарифам",
                channel="guest_web",
                quiet_night=True,
                allow_in_test=True,
            )
            assert summary["quiet_night"] is True
            assert summary["dm_sent"] == 0
    finally:
        db.close()


def test_admin_security_endpoints(client: TestClient):
    r_overview = client.get("/api/admin/security/overview")
    assert r_overview.status_code == 200
    body = r_overview.json()
    assert "summary" in body
    assert "work_hours" in body
    assert "registration_attempts" in body
    assert "security_events" in body

    r_block = client.post(
        "/api/admin/security/block",
        json={"actor_type": "ip", "actor_value": "203.0.113.55", "reason": "Test ban"},
    )
    assert r_block.status_code == 200
    block_id = r_block.json()["id"]

    r_unblock = client.post("/api/admin/security/unblock", json={"id": block_id})
    assert r_unblock.status_code == 200

    for protected_ip in ("79.133.182.215", "202.71.13.57", "127.0.0.1", "::1", "10.0.0.5", "192.168.1.1", "172.16.0.1"):
        r_bad = client.post(
            "/api/admin/security/block",
            json={"actor_type": "ip", "actor_value": protected_ip, "reason": "Accidental self-ban"},
        )
        assert r_bad.status_code == 400


@pytest.mark.asyncio
async def test_classify_and_reply_support_message_matches_real_call_llm_signature():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        if settings is None:
            settings = SystemSettings(id=1)
            db.add(settings)
        settings.custom_ai_providers_json = '[{"id":"p1","name":"Test","apiKey":"sk-or-test-key","baseUrl":"https://openrouter.ai/api/v1"}]'
        settings.support_ai_antispam_enabled = True
        settings.support_ai_auto_reply_enabled = True
        db.commit()

        with patch("app.security_shield.call_llm", autospec=True) as mock_llm:
            mock_llm.return_value = '{"category": "real_question", "need_human": true, "reply": "Добрый день! Поможем подобрать поставщиков."}'
            result = await classify_and_reply_support_message(
                db,
                text="Здравствуйте, сколько стоит поиск поставщиков?",
                is_guest=True,
                is_work_hours=True,
                force_in_test=True,
            )
            assert result["used_ai"] is True
            assert result["category"] == "real_question"
            assert result["need_human"] is True
            assert "Поможем" in result["reply"]
            mock_llm.assert_awaited_once()
    finally:
        db.close()


def test_challenge_secret_derivation_and_ephemeral_fallback(monkeypatch):
    import app.security_shield as ss

    monkeypatch.setenv("AIPOISK_CHALLENGE_SECRET", "explicit-secret-value")
    assert _challenge_secret() == b"explicit-secret-value"

    monkeypatch.delenv("AIPOISK_CHALLENGE_SECRET", raising=False)
    monkeypatch.setattr(ss.config, "admin_token", "prod-admin-secret-token")
    derived = _challenge_secret()
    assert len(derived) == 32
    assert derived != b"prod-admin-secret-token"

    monkeypatch.setattr(ss.config, "admin_token", "change-me")
    monkeypatch.setattr(ss, "_EPHEMERAL_CHALLENGE_SECRET", None)
    eph1 = _challenge_secret()
    eph2 = _challenge_secret()
    assert len(eph1) == 32
    assert eph1 == eph2
