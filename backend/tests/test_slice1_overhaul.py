from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_mod
from app.billing import (
    KIND_DEPOSIT,
    KIND_EXACT_PRODUCT,
    KIND_MONEY,
    OP_CHARGE,
    OP_GRANT,
    OP_RELEASE,
    OP_RESERVE,
    adjust_exact_product_reservation_for_selection,
    balance_counter,
    grant_money_balance,
    grant_package_units,
    settle_exact_product_job,
)
from app.bot import _looks_like_supplier_text_tz, _start_text, start as bot_start_handler
from app.db import Base, db_session
from app.jobs import (
    MODE_EXACT_PRODUCT,
    MODE_PRICE_MONITORING,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
)
from app.main import (
    CUSTOMER_AUTH_ATTEMPTS,
    EMAIL_VERIFY_RESEND_ATTEMPTS,
    app,
    create_customer_job_api,
    customer_jobs_api,
    customer_session_payload,
    grant_client_billing_units,
    require_admin,
)
from app.mcp_api import (
    McpSupplierSearchRequest,
    _attach_api_input_file,
    _resolve_mcp_source_text,
    generate_api_key,
    mcp_supplier_search,
)
from app.models import (
    ApiKey,
    BillingTransaction,
    Client,
    Invoice,
    Job,
    JobFile,
    JobSource,
    LegalAcceptance,
    SecurityEvent,
    SupportBlockedActor,
    SystemSettings,
    TariffPackage,
    WebEmailVerificationToken,
    WebPasswordResetRequest,
    WebPasswordResetToken,
    WebSession,
    WebUser,
)
from app.schemas import BillingGrantCreate
from app.security_shield import (
    PROTECTED_INFRASTRUCTURE_IPS,
    extract_real_request_ip,
    get_protected_infrastructure_ips,
    maybe_auto_block_actor,
    normalize_blockable_ip,
    record_security_event,
)
from app.supplier_search import EmptyProcurementProfileError
from app.support_chat import is_blockable_ip, unblock_support_dialog
from app.tenderplan import TenderplanDownloadedFile
from app.web_auth import (
    CSRF_HEADER,
    WebAuthContext,
    create_email_verification_token,
    create_password_reset_token,
    create_web_session,
    create_web_user,
    verify_email_token,
)


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    TestingSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    db = TestingSession()

    settings = SystemSettings(
        id=1,
        trial_enabled=True,
        trial_supplier_search_limit=2,
        trial_procurement_report_limit=2,
        trial_file_limit=10,
        payment_provider="yookassa",
        yookassa_shop_id="123456",
        yookassa_secret_key="test_secret_key",
    )
    db.add(settings)
    db.commit()

    def _override_db():
        yield db

    CUSTOMER_AUTH_ATTEMPTS.clear()
    EMAIL_VERIFY_RESEND_ATTEMPTS.clear()
    monkeypatch.setattr(main_mod.config, "storage_dir", str(tmp_path / "storage"))
    app.dependency_overrides[db_session] = _override_db
    app.dependency_overrides[require_admin] = lambda: "admin"

    with TestClient(app) as tc:
        yield SimpleNamespace(db=db, client=tc, tmp_path=tmp_path)

    app.dependency_overrides.clear()
    CUSTOMER_AUTH_ATTEMPTS.clear()
    EMAIL_VERIFY_RESEND_ATTEMPTS.clear()
    db.close()
    eng.dispose()


def test_extract_real_request_ip_right_to_left_and_env_proxies(monkeypatch):
    assert {"79.133.182.215", "202.71.13.57", "127.0.0.1", "::1"}.issubset(PROTECTED_INFRASTRUCTURE_IPS)

    # Attacker spoofs 1.1.1.1 on the left; real visitor is 85.140.12.34 behind edge 79.133.182.215 -> 202.71.13.57
    req = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "1.1.1.1, 85.140.12.34, 79.133.182.215, 202.71.13.57, 127.0.0.1"},
    )
    assert extract_real_request_ip(req) == "85.140.12.34"

    # Private RFC1918 hops are also skipped from right to left
    req_lan = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "9.9.9.9, 91.210.44.10, 10.0.0.5, 192.168.1.2, 79.133.182.215"},
    )
    assert extract_real_request_ip(req_lan) == "91.210.44.10"

    # Custom AIPOISK_TRUSTED_PROXY_IPS env var is respected
    monkeypatch.setenv("AIPOISK_TRUSTED_PROXY_IPS", "185.10.20.30, 185.10.20.31")
    assert "185.10.20.30" in get_protected_infrastructure_ips()
    req_custom = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "8.8.8.8, 93.158.134.11, 185.10.20.30"},
    )
    assert extract_real_request_ip(req_custom) == "93.158.134.11"
    assert normalize_blockable_ip("185.10.20.30") == ""


def test_auto_block_actor_never_blocks_infra_and_matches_prefixed_guest_and_client(isolated_env):
    db = isolated_env.db

    # Infrastructure & private IPs must never be blocked even with 10 security events
    for protected_ip in ("79.133.182.215", "202.71.13.57", "127.0.0.1", "::1", "10.1.2.3", "192.168.1.5", "172.16.5.4", "240.0.0.1"):
        assert is_blockable_ip(protected_ip) == ""
        for _ in range(4):
            record_security_event(db, event_type="chat_probe", ip_address=protected_ip, actor_key=protected_ip)
        assert maybe_auto_block_actor(db, actor_type="ip", actor_value=protected_ip, threshold=3) is False

    # Guest session events logged as "guest:<sid>" trigger auto-block when queried by "<sid>"
    sid = "sess_guest_prefixed_01"
    for _ in range(3):
        record_security_event(db, event_type="chat_probe", ip_address="85.140.12.50", actor_key=f"guest:{sid}")
    assert maybe_auto_block_actor(db, actor_type="guest_session", actor_value=sid, threshold=3) is True
    assert (
        db.query(SupportBlockedActor)
        .filter(SupportBlockedActor.actor_type == "guest_session", SupportBlockedActor.actor_value == sid)
        .first()
        is not None
    )

    # Client events logged as "client:<cid>" trigger auto-block when queried by "<cid>"
    cid = "client_prefixed_01"
    for _ in range(3):
        record_security_event(db, event_type="chat_probe", ip_address="85.140.12.51", actor_key=f"client:{cid}")
    assert maybe_auto_block_actor(db, actor_type="client", actor_value=cid, threshold=3) is True


@pytest.mark.asyncio
async def test_real_ip_persisted_across_auth_and_cleared_on_client_unblock(isolated_env, monkeypatch):
    db = isolated_env.db
    tc = isolated_env.client
    monkeypatch.setattr(main_mod, "_send_customer_verification_email", lambda *a, **kw: True)
    monkeypatch.setattr(main_mod, "send_password_reset_email", lambda *a, **kw: True)

    xff_headers = {"X-Forwarded-For": "1.2.3.4, 91.210.55.77, 79.133.182.215, 202.71.13.57"}
    reg_res = tc.post(
        "/api/customer/auth/register",
        headers=xff_headers,
        json={
            "email": "ipcheck@stroymash.ru",
            "password": "StrongPassword123!",
            "name": "ООО СтройМаш",
            "terms_accepted": True,
            "personal_data_consent": True,
        },
    )
    assert reg_res.status_code == 200
    user = db.query(WebUser).filter(WebUser.email == "ipcheck@stroymash.ru").first()
    assert user is not None
    assert user.client.registration_ip == "91.210.55.77"

    acceptances = db.query(LegalAcceptance).filter(LegalAcceptance.subject_id == user.id).all()
    assert len(acceptances) == 2
    assert all(a.ip_address == "91.210.55.77" for a in acceptances)

    sess = db.query(WebSession).filter(WebSession.user_id == user.id).first()
    assert sess is not None
    assert sess.ip_address == "91.210.55.77"

    fake_req = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "5.5.5.5, 91.210.55.78, 79.133.182.215", "user-agent": "PytestBrowser/1.0"},
    )
    _tok_v, rec_v = create_email_verification_token(db, user, request=fake_req)
    assert rec_v.requested_ip == "91.210.55.78"
    _tok_r, rec_r = create_password_reset_token(db, user, request=fake_req)
    assert rec_r.requested_ip == "91.210.55.78"
    _tok_s, _csrf_s, rec_s = create_web_session(db, user, request=fake_req)
    assert rec_s.ip_address == "91.210.55.78"

    reset_res = tc.post(
        "/api/customer/auth/password-reset/request",
        headers=xff_headers,
        json={"email": "ipcheck@stroymash.ru"},
    )
    assert reset_res.status_code == 200
    reset_req_row = db.query(WebPasswordResetRequest).filter(WebPasswordResetRequest.user_id == user.id).first()
    assert reset_req_row is not None
    assert reset_req_row.requested_ip == "91.210.55.77"

    # Simulate auto_shield blocking both registration_ip and session IP with empty dialog_key
    for ip_val in ("91.210.55.77", "91.210.55.78"):
        db.add(
            SupportBlockedActor(
                actor_type="ip",
                actor_value=ip_val,
                dialog_key="",
                reason="Auto shield",
                blocked_by="auto_shield",
            )
        )
    db.commit()

    await unblock_support_dialog(db, client_id=user.client_id)
    remaining_blocks = (
        db.query(SupportBlockedActor)
        .filter(SupportBlockedActor.actor_type == "ip", SupportBlockedActor.actor_value.in_(["91.210.55.77", "91.210.55.78"]))
        .count()
    )
    assert remaining_blocks == 0


def test_blocked_ip_and_client_rejected_with_403_on_login_and_chat(isolated_env):
    db = isolated_env.db
    tc = isolated_env.client

    user = create_web_user(db, email="chatblock@stroymash.ru", password="StrongPassword123!", name="Клиент", email_verified=True)
    tok, csrf, _sess = create_web_session(db, user)

    # Unauthenticated chat returns 401
    tc.cookies.clear()
    unauth_chat = tc.post("/api/customer/chat", data={"message": "Привет"})
    assert unauth_chat.status_code == 401

    # Block IP 93.158.134.55 -> login and chat from that IP return 403
    db.add(SupportBlockedActor(actor_type="ip", actor_value="93.158.134.55", reason="Spam IP", blocked_by="admin"))
    db.commit()

    blocked_login = tc.post(
        "/api/customer/auth/login",
        headers={"X-Forwarded-For": "93.158.134.55, 79.133.182.215"},
        json={"email": "chatblock@stroymash.ru", "password": "StrongPassword123!"},
    )
    assert blocked_login.status_code == 403

    tc.cookies.set("tenderlex_customer_session", tok)
    blocked_ip_chat = tc.post(
        "/api/customer/chat",
        headers={"X-Forwarded-For": "93.158.134.55, 79.133.182.215", CSRF_HEADER: csrf},
        data={"message": "Тест с заблокированного IP"},
    )
    assert blocked_ip_chat.status_code == 403

    # From a clean IP, client actor block also returns 403 on chat
    db.add(SupportBlockedActor(actor_type="client", actor_value=user.client_id, reason="Spam client", blocked_by="admin"))
    db.commit()
    blocked_client_chat = tc.post(
        "/api/customer/chat",
        headers={"X-Forwarded-For": "93.158.134.99, 79.133.182.215", CSRF_HEADER: csrf},
        data={"message": "Тест от заблокированного клиента"},
    )
    assert blocked_client_chat.status_code == 403


def test_email_verify_resend_never_locks_out_password_login(isolated_env, monkeypatch):
    db = isolated_env.db
    tc = isolated_env.client
    monkeypatch.setattr(main_mod, "_send_customer_verification_email", lambda *a, **kw: True)

    user = create_web_user(db, email="resendtest@stroymash.ru", password="StrongPassword123!", name="Иван", email_verified=False)
    tok, csrf, _sess = create_web_session(db, user)
    tc.cookies.set("tenderlex_customer_session", tok)
    hdrs = {"X-Forwarded-For": "95.108.213.10, 79.133.182.215", CSRF_HEADER: csrf}

    # 5 resends succeed, 6th hits dedicated resend limit (429)
    for _ in range(5):
        r = tc.post("/api/customer/auth/verify-email/request", headers=hdrs)
        assert r.status_code == 200
    r_sixth = tc.post("/api/customer/auth/verify-email/request", headers=hdrs)
    assert r_sixth.status_code == 429

    # Password login from the exact same IP + email MUST still succeed!
    r_login = tc.post(
        "/api/customer/auth/login",
        headers={"X-Forwarded-For": "95.108.213.10, 79.133.182.215"},
        json={"email": "resendtest@stroymash.ru", "password": "StrongPassword123!"},
    )
    assert r_login.status_code == 200
    assert r_login.json()["authenticated"] is True


@pytest.mark.asyncio
async def test_first_trial_job_before_email_verify_and_eis_notice_in_text(isolated_env, monkeypatch):
    db = isolated_env.db
    enqueued: list[str] = []
    monkeypatch.setattr(main_mod, "enqueue_job", lambda jid: enqueued.append(jid))

    user = create_web_user(db, email="trialuser@stroymash.ru", password="StrongPassword123!", name="Новичок", email_verified=False)
    grant_money_balance(db, user.client, amount_kopeks=500_000, note="Welcome", created_by="system")

    sess_before = customer_session_payload(db, user, csrf_token="csrf1", authenticated=True)
    assert sess_before["can_launch_trial_without_email_verify"] is True
    assert sess_before["user"]["can_launch_trial_without_email_verify"] is True

    # 1st job (bare 19-digit EIS notice pasted into text of supplier_search!) succeeds without email verification
    res_job1 = await create_customer_job_api(
        mode=MODE_SUPPLIER_SEARCH,
        text="0177200000926002782",
        source_urls="",
        files=[],
        context=WebAuthContext(user=user, session=None),
        db=db,
    )
    assert res_job1["count"] == 1
    job1_id = res_job1["job"]["id"]
    sources1 = db.query(JobSource).filter(JobSource.job_id == job1_id).all()
    assert len(sources1) == 1
    assert sources1[0].kind == "tenderplan_notice"
    assert sources1[0].value == "0177200000926002782"
    # No dummy raw-digit technical_assignment.txt file was created
    assert db.query(JobFile).filter(JobFile.job_id == job1_id).count() == 0

    sess_after = customer_session_payload(db, user, csrf_token="csrf1", authenticated=True)
    assert sess_after["can_launch_trial_without_email_verify"] is False

    # 2nd job while still unverified is blocked with clear Russian prompt
    with pytest.raises(HTTPException) as exc_second:
        await create_customer_job_api(
            mode=MODE_EXACT_PRODUCT,
            text="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0177200000926002782",
            source_urls="",
            files=[],
            context=WebAuthContext(user=user, session=None),
            db=db,
        )
    assert exc_second.value.status_code == 403
    assert "первая пробная задача уже выполнена" in exc_second.value.detail

    # Verify email -> 2nd job with official EIS URL in text of exact_product succeeds!
    tok_v, _ = create_email_verification_token(db, user)
    verified_user = verify_email_token(db, tok_v)
    res_job2 = await create_customer_job_api(
        mode=MODE_EXACT_PRODUCT,
        text="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0177200000926002782",
        source_urls="",
        files=[],
        context=WebAuthContext(user=verified_user, session=None),
        db=db,
    )
    assert res_job2["count"] == 1
    job2_id = res_job2["job"]["id"]
    sources2 = db.query(JobSource).filter(JobSource.job_id == job2_id).all()
    assert len(sources2) == 1
    assert sources2[0].kind == "official_eis"


def test_job_history_filter_includes_price_monitoring(isolated_env):
    db = isolated_env.db
    user = create_web_user(db, email="hist@stroymash.ru", password="StrongPassword123!", name="История", email_verified=True)
    db.add_all(
        [
            Job(job_number=1001, client_id=user.client_id, mode=MODE_SUPPLIER_SEARCH, status="completed", title="Поиск"),
            Job(job_number=1002, client_id=user.client_id, mode=MODE_PRICE_MONITORING, status="completed", title="Мониторинг цен"),
        ]
    )
    db.commit()

    resp = SimpleNamespace(headers={})
    pm_jobs = customer_jobs_api(
        response=resp,
        mode=MODE_PRICE_MONITORING,
        context=WebAuthContext(user=user, session=None),
        db=db,
    )
    assert len(pm_jobs) == 1
    assert pm_jobs[0]["mode"] == MODE_PRICE_MONITORING
    assert pm_jobs[0]["title"] == "Мониторинг цен"


def test_yookassa_package_integrity_and_admin_grant_invoice_sync(isolated_env):
    db = isolated_env.db
    tc = isolated_env.client

    pkg = TariffPackage(
        name="Про",
        kind=KIND_DEPOSIT,
        units=1,
        price_kopeks=490_000,
        bonus_kopeks=60_000,
        is_active=True,
    )
    db.add(pkg)
    db.commit()

    user = create_web_user(db, email="pay@stroymash.ru", password="StrongPassword123!", name="Плательщик", email_verified=True)
    tok, csrf, _sess = create_web_session(db, user)
    tc.cookies.set("tenderlex_customer_session", tok)
    hdrs = {CSRF_HEADER: csrf}

    # Tampered amount_rub=100 with package_id='Про' (4900 ₽) MUST be rejected with 400!
    r_tamper = tc.post(
        "/api/customer/payments/yookassa/create",
        headers=hdrs,
        json={"amount_rub": 100, "package_id": pkg.id},
    )
    assert r_tamper.status_code == 400
    assert "не совпадает" in r_tamper.json()["detail"]

    # Custom top-up below 300 ₽ rejected with 400
    r_low = tc.post(
        "/api/customer/payments/yookassa/create",
        headers=hdrs,
        json={"amount_rub": 150},
    )
    assert r_low.status_code == 400

    # Matching package price succeeds and applies package.bonus_kopeks (600 ₽)
    mock_yk_resp = {
        "id": "yk_pay_001",
        "status": "pending",
        "amount": {"value": "4900.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "confirmation_url": "https://yoomoney.ru/checkout/yk_pay_001"},
    }
    with patch("app.main.create_yookassa_payment", return_value=mock_yk_resp), patch(
        "app.main.notify_admin_payment_attempt"
    ):
        r_ok = tc.post(
            "/api/customer/payments/yookassa/create",
            headers=hdrs,
            json={"amount_rub": 4900, "package_id": pkg.id},
        )
        assert r_ok.status_code == 200
        body = r_ok.json()
        assert body["amount_rub"] == 4900
        assert body["bonus_rub"] == 600
        assert body["total_credit_rub"] == 5500

    # Open issued invoice auto-syncs to 'paid' when admin grants matching balance
    inv = Invoice(
        invoice_number="TL-2026-0099",
        client_id=user.client_id,
        amount_rub=4900,
        bonus_rub=600,
        total_credit_rub=5500,
        status="issued",
    )
    db.add(inv)
    db.commit()

    grant_res = grant_client_billing_units(
        user.client_id,
        BillingGrantCreate(kind=KIND_MONEY, operation="grant", package_id=pkg.id),
        db=db,
    )
    assert grant_res["success"] is True
    assert grant_res.get("synced_invoice_number") == "TL-2026-0099"
    db.refresh(inv)
    assert inv.status == "paid"
    assert inv.paid_at is not None


def test_exact_product_partial_settlement_package_units_and_rubles(isolated_env):
    db = isolated_env.db

    # Case A: Package units reservation (reserve_units=5, reserve_amount=0), confirmed=2 -> charge 2, release 3
    c_pkg = Client(telegram_id="web:pkg-exact", name="Пакетный клиент", is_trial=False)
    db.add(c_pkg)
    db.commit()
    grant_package_units(db, c_pkg, kind=KIND_EXACT_PRODUCT, units=5, amount_kopeks=0, note="Пакет 5 поз.")
    assert balance_counter(db, c_pkg, KIND_EXACT_PRODUCT)["available"] == 5

    job_pkg = Job(job_number=2001, client_id=c_pkg.id, mode=MODE_EXACT_PRODUCT, status="running", title="Подбор пакет")
    db.add(job_pkg)
    db.commit()
    adjust_exact_product_reservation_for_selection(db, job_pkg, chosen_count=5, price_per_item_kopeks=0)
    db.commit()
    assert balance_counter(db, c_pkg, KIND_EXACT_PRODUCT)["available"] == 0

    charged_pkg = settle_exact_product_job(db, job_pkg, confirmed_count=2)
    assert charged_pkg is True
    assert balance_counter(db, c_pkg, KIND_EXACT_PRODUCT)["available"] == 3

    txs_pkg = db.query(BillingTransaction).filter(BillingTransaction.job_id == job_pkg.id).all()
    ops_pkg = {t.operation: t.units for t in txs_pkg}
    assert ops_pkg[OP_RESERVE] == 5
    assert ops_pkg[OP_CHARGE] == 2
    assert ops_pkg[OP_RELEASE] == 3

    # Case B: Ruble reservation (reserve_units=4, 100 ₽/pos = 400 ₽), confirmed=1 -> charge 100 ₽, release 300 ₽
    c_rub = Client(telegram_id="web:rub-exact", name="Рублёвый клиент", is_trial=False)
    db.add(c_rub)
    db.commit()
    grant_money_balance(db, c_rub, amount_kopeks=100_000, note="Депозит 1000 ₽", created_by="admin")
    job_rub = Job(job_number=2002, client_id=c_rub.id, mode=MODE_EXACT_PRODUCT, status="running", title="Подбор рубли")
    db.add(job_rub)
    db.commit()
    adjust_exact_product_reservation_for_selection(db, job_rub, chosen_count=4, price_per_item_kopeks=10_000)
    db.commit()
    db.refresh(c_rub)
    reserved_amt = c_rub.money_reserved_kopeks
    assert reserved_amt == 40_000
    unit_p = 10_000

    charged_rub = settle_exact_product_job(db, job_rub, confirmed_count=1)
    assert charged_rub is True
    db.refresh(c_rub)
    assert c_rub.money_reserved_kopeks == 0
    assert c_rub.money_balance_kopeks == 100_000 - unit_p


@pytest.mark.asyncio
async def test_mcp_api_parse_status_eis_autofetch_and_422_on_empty_profile(isolated_env, monkeypatch):
    db = isolated_env.db
    settings = db.query(SystemSettings).first()

    client = Client(telegram_id="web:mcp-client", name="MCP Client", is_trial=False)
    db.add(client)
    db.commit()
    grant_money_balance(db, client, amount_kopeks=500_000, note="MCP balance", created_by="admin")
    grant_package_units(db, client, kind="supplier_search", units=2, amount_kopeks=0, note="MCP units")

    _raw, key_hash, key_prefix = generate_api_key(is_admin=False)
    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        secret_token="",
        name="Test MCP Key",
        client_id=client.id,
        is_active=True,
        allowed_supplier_search=True,
    )
    db.add(api_key)
    job = Job(job_number=3001, client_id=client.id, mode=MODE_SUPPLIER_SEARCH, status="running", title="MCP Test")
    db.add(job)
    db.commit()

    # 1. _attach_api_input_file sets parse_status="ok"
    _attach_api_input_file(db, job, "Поставка кабеля ВВГнг(А)-LS 3х2.5", "spec.txt")
    jf = db.query(JobFile).filter(JobFile.job_id == job.id).first()
    assert jf is not None
    assert jf.parse_status == "ok"

    # 2. _resolve_mcp_source_text auto-fetches 19-digit EIS notice & extracts downloaded attachment text
    tz_bytes = "Сервер стоечный 2U Xeon Gold".encode("utf-8")
    fake_notice_res = SimpleNamespace(
        ok=True,
        context="Извещение 0177200000926002782: Поставка серверного оборудования",
        downloaded_files=[
            TenderplanDownloadedFile(
                filename="tz.txt",
                category="specification",
                source_url="https://zakupki.gov.ru/tz.txt",
                content=tz_bytes,
                size=len(tz_bytes),
            )
        ],
    )
    monkeypatch.setattr("app.mcp_api.fetch_tenderplan_source_sync", lambda val: fake_notice_res)
    resolved = await _resolve_mcp_source_text("0177200000926002782", settings)
    assert "Поставка серверного оборудования" in resolved
    assert "Сервер стоечный 2U Xeon Gold" in resolved

    # 3. EmptyProcurementProfileError returns 422 (not 500) and releases reservation cleanly
    monkeypatch.setattr("app.mcp_api.extract_supplier_search_context", AsyncMock(return_value="Пустой бланк"))
    monkeypatch.setattr(
        "app.mcp_api.discover_suppliers",
        AsyncMock(side_effect=EmptyProcurementProfileError("В документе не найдены конкретные товары.")),
    )
    balance_before = client.money_balance_kopeks
    with pytest.raises(HTTPException) as exc_mcp:
        await mcp_supplier_search(
            req=McpSupplierSearchRequest(specification="Пустой бланк без товаров"),
            idempotency_key=None,
            api_key=api_key,
            db=db,
        )
    assert exc_mcp.value.status_code == 422
    db.refresh(client)
    assert client.money_reserved_kopeks == 0
    assert client.money_balance_kopeks == balance_before
    assert balance_counter(db, client, "supplier_search")["available"] == 2


@pytest.mark.asyncio
async def test_telegram_bot_concise_queries_rule14_and_start_welcome_legal(isolated_env, monkeypatch):
    import app.bot as bot_mod

    # Concise real procurement/GOST queries pass without requiring stem lists or 50+ chars
    assert _looks_like_supplier_text_tz("ФБС 24.4.6-Т") is True
    assert _looks_like_supplier_text_tz("Лист бронзовый БрАЖ9-4") is True
    assert _looks_like_supplier_text_tz("Окна пластиковые ПВХ") is True
    assert _looks_like_supplier_text_tz("Било Л-04.524") is True

    # Slash commands, bare notice numbers, bare URLs, and 1-word greetings do not hijack supplier TZ
    assert _looks_like_supplier_text_tz("/start") is False
    assert _looks_like_supplier_text_tz("32616063169") is False
    assert _looks_like_supplier_text_tz("0177200000926002782") is False
    assert _looks_like_supplier_text_tz("https://etp.example.ru/procedure/123") is False
    assert _looks_like_supplier_text_tz("Привет") is False

    # Base no-arg _start_text() remains clean, while start() shows trial balance + /legal 152-ФЗ note
    base_text = _start_text()
    assert "TenderLex" in base_text
    assert "политик" not in base_text.lower()

    enriched_text = _start_text(balance_rub=500, include_legal_note=True)
    assert "500 ₽" in enriched_text
    assert "/legal" in enriched_text

    # Verify live start() handler output
    db = isolated_env.db
    tg_client = Client(telegram_id="99887766", name="TG User", money_balance_kopeks=50_000, money_reserved_kopeks=0)
    db.add(tg_client)
    db.commit()

    monkeypatch.setattr(bot_mod, "SessionLocal", lambda: sessionmaker(bind=db.get_bind())())
    monkeypatch.setattr(
        bot_mod,
        "get_or_create_trial_client_by_telegram_id",
        lambda s, *a, **kw: (s.query(Client).filter(Client.telegram_id == "99887766").first(), ""),
    )
    msg = MagicMock()
    msg.text = "/start"
    msg.chat.id = 99887766
    msg.from_user.id = 99887766
    msg.from_user.username = "tguser"
    msg.from_user.full_name = "TG User"
    msg.answer = AsyncMock()

    await bot_start_handler(msg)
    msg.answer.assert_awaited_once()
    sent_text = msg.answer.await_args.args[0]
    assert "500 ₽" in sent_text
    assert "/legal" in sent_text
