from __future__ import annotations

import pytest
from app.db import SessionLocal
from app.models import Client, Job, WebUser, new_id, now_utc
from app.referral import (
    REFERRAL_INVITER_REWARD_KOPEKS,
    REFERRAL_WELCOME_BONUS_KOPEKS,
    ensure_client_referral_code,
    get_referral_stats,
    is_disposable_email,
    link_referral_and_grant_welcome,
    process_referral_on_job_completion,
    resolve_referrer,
    validate_referral_linkage,
)
from app.billing import charge_job_reservation, reserve_job_units, KIND_SUPPLIER_SEARCH


def test_disposable_email_detection():
    assert is_disposable_email("user@mailinator.com") is True
    assert is_disposable_email("test@temp-mail.org") is True
    assert is_disposable_email("real@company.ru") is False
    assert is_disposable_email("alex@yandex.ru") is False


def test_referral_code_generation_and_resolution():
    db = SessionLocal()
    try:
        client = Client(
            telegram_id=f"tg_{new_id()}",
            name="Test User",
            is_active=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)

        code = ensure_client_referral_code(client, db=db)
        db.commit()
        assert code
        assert client.referral_code == code

        # Resolve via exact code
        found = resolve_referrer(db, code)
        assert found is not None
        assert found.id == client.id

        # Resolve via code with ref_ prefix
        found_ref = resolve_referrer(db, f"ref_{code}")
        assert found_ref is not None
        assert found_ref.id == client.id

        # Resolve via client ID
        found_id = resolve_referrer(db, client.id)
        assert found_id is not None
        assert found_id.id == client.id
    finally:
        db.close()


def test_anti_abuse_safeguards():
    db = SessionLocal()
    try:
        user_a = Client(
            telegram_id="111111",
            name="User A",
            is_active=True,
        )
        user_b = Client(
            telegram_id="222222",
            name="User B",
            is_active=True,
        )
        db.add_all([user_a, user_b])
        db.commit()

        # 1. Self-referral by ID
        valid, err = validate_referral_linkage(db, user_a, user_a)
        assert not valid
        assert "самого себя" in err

        # 2. Self-referral by Telegram ID
        valid, err = validate_referral_linkage(db, user_a, user_b, invitee_telegram_id="111111")
        assert not valid
        assert "свой же Telegram" in err

        # 3. Disposable email
        valid, err = validate_referral_linkage(db, user_a, user_b, invitee_email="bot@trashmail.com")
        assert not valid
        assert "Временные почтовые адреса" in err

        # 4. Cycle detection (A invited B, now B tries to invite A)
        user_b.referrer_id = user_a.id
        db.commit()
        valid, err = validate_referral_linkage(db, user_b, user_a)
        assert not valid
        assert "Циклическое" in err
    finally:
        db.close()


from app.referral import (
    REFERRAL_INVITER_REWARD_KOPEKS,
    REFERRAL_WELCOME_BONUS_KOPEKS,
    ensure_client_referral_code,
    get_referral_stats,
    link_referral,
    link_referral_and_grant_welcome,
    process_referral_on_job_completion,
    process_referral_on_payment,
    validate_referral_linkage,
)


def test_referral_welcome_and_first_job_reward_lifecycle():
    db = SessionLocal()
    try:
        inviter = Client(
            telegram_id=f"inviter_{new_id()}",
            name="Inviter",
            is_active=True,
            money_balance_kopeks=0,
        )
        invitee = Client(
            telegram_id=f"invitee_{new_id()}",
            name="Invitee",
            is_active=True,
            money_balance_kopeks=0,
        )
        db.add_all([inviter, invitee])
        db.commit()
        db.refresh(inviter)
        db.refresh(invitee)

        # Step 1: Link referral (welcome bonus is pending first qualifying payment)
        success = link_referral_and_grant_welcome(db, invitee, inviter)
        assert success is True
        db.refresh(invitee)
        assert invitee.referrer_id == inviter.id
        # Invitee has 0 unearned balance before real payment
        assert invitee.money_balance_kopeks == 0

        # Idempotency check: linking again does nothing
        assert link_referral_and_grant_welcome(db, invitee, inviter) is False
        db.refresh(invitee)
        assert invitee.money_balance_kopeks == 0

        # Check stats before deposit: invited=1, activated=0
        stats = get_referral_stats(db, inviter)
        assert stats["invited_count"] == 1
        assert stats["activated_count"] == 0
        assert stats["bonus_earned_rub"] == 0

        # Step 2: Invitee completes a free trial job -> MUST NOT award any referral money!
        job = Job(
            client_id=invitee.id,
            mode="supplier_search",
            status="completed",
            title="Закупка кабеля ВВГнг",
            target_suppliers=5,
            completed_at=now_utc(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Free job does not reward
        rewarded = process_referral_on_job_completion(db, job)
        assert rewarded is False
        db.refresh(inviter)
        assert inviter.money_balance_kopeks == 0

        # Step 3: Non-qualifying small payment (< 1000 ₽) does not trigger reward
        small_payment_rewarded = process_referral_on_payment(db, invitee, 50_000)
        assert small_payment_rewarded is False

        # Step 4: Qualifying first payment (>= 1 000 ₽ / 100_000 kopeks)
        # Triggers +1 000 ₽ welcome match for invitee AND +1 000 ₽ reward for inviter
        payment_rewarded = process_referral_on_payment(db, invitee, 100_000)
        assert payment_rewarded is True

        db.refresh(inviter)
        db.refresh(invitee)
        assert invitee.referral_reward_granted is True
        assert invitee.money_balance_kopeks == REFERRAL_WELCOME_BONUS_KOPEKS
        assert inviter.money_balance_kopeks == REFERRAL_INVITER_REWARD_KOPEKS

        # Step 5: Check stats after qualifying payment
        stats = get_referral_stats(db, inviter)
        assert stats["invited_count"] == 1
        assert stats["activated_count"] == 1
        assert stats["bonus_earned_rub"] == 1000

        # Step 6: Subsequent payments do NOT reward inviter again
        assert process_referral_on_payment(db, invitee, 100_000) is False
        db.refresh(inviter)
        assert inviter.money_balance_kopeks == REFERRAL_INVITER_REWARD_KOPEKS
    finally:
        db.close()


def test_customer_referral_api_and_registration():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    db = SessionLocal()
    try:
        # Create inviter
        inviter = Client(
            telegram_id=f"inviter_api_{new_id()}",
            name="API Inviter",
            is_active=True,
        )
        db.add(inviter)
        db.commit()
        db.refresh(inviter)
        ref_code = ensure_client_referral_code(inviter, db=db)
        db.commit()

        # Register invitee with ref parameter
        test_email = f"invitee_{new_id()}@corporate.ru"
        reg_resp = client.post(
            "/api/customer/auth/register",
            json={
                "email": test_email,
                "password": "StrongPassword123!",
                "name": "Invitee User",
                "terms_accepted": True,
                "personal_data_consent": True,
                "ref": ref_code,
            },
        )
        assert reg_resp.status_code == 200
        session_cookie = client.cookies.get("tenderlex_customer_session")
        assert session_cookie

        # Check that invitee is linked to referrer
        invitee_client = db.query(Client).join(WebUser, WebUser.client_id == Client.id).filter(WebUser.email == test_email).first()
        assert invitee_client is not None
        assert invitee_client.referrer_id == inviter.id
        # Starts with standard trial balance without unearned referral bonus (< 1 000 ₽)
        assert invitee_client.money_balance_kopeks in {49500, 49600}

        # Check referral stats via customer_referral_api
        from app.main import customer_referral_api
        from app.web_auth import WebAuthContext
        invitee_user = db.query(WebUser).filter(WebUser.email == test_email).first()
        context = WebAuthContext(user=invitee_user, session=None)
        ref_data = customer_referral_api(context=context, db=db)
        assert "referral_code" in ref_data
        assert "invite_url_bot" in ref_data
        assert "invite_url_web" in ref_data
        assert "invited_count" in ref_data
        assert ref_data["balance_rub"] in {495, 496}
    finally:
        db.close()

