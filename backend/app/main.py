from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import time

import httpx
import jwt

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from .ai import call_llm, resolve_job_ai_info
from .result_offers import (
    result_offer_to_dict,
    accept_job_result_offer,
    decline_job_result_offer,
    claim_job_result_offer_delivery,
    complete_job_result_offer_delivery,
)
from .billing import (
    BillingError,
    KIND_MONEY,
    OP_CHARGE,
    OP_GRANT,
    OP_MANUAL_DEBIT,
    OP_RELEASE,
    OP_RESERVE,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CUSTOMER_DECLINED,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_DELIVERY_EXPIRED,
    VALID_BILLING_KINDS,
    billing_kind_label,
    charge_job_reservation,
    charge_job_kind_reservation,
    client_balance_summary,
    client_service_balance_summary,
    client_uses_trial_access,
    debit_money_balance,
    debit_package_units,
    expire_stale_confirmations,
    grant_money_balance,
    grant_package_units,
    invalidate_tariff_packages_cache,
    operation_label,
    release_job_reservation,
    list_tariffs,
    recent_billing_transactions,
    reserve_job_units,
    tariff_to_dict,
    transaction_to_dict,
)
from .legal import (
    LEGAL_VERSION,
    LEGAL_DOCUMENT_TERMS,
    LEGAL_DOCUMENT_PERSONAL_DATA,
    record_legal_acceptance,
)
from .config import config
from .db import db_session, init_db
from .jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_EXACT_PRODUCT,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    SUPPLIER_POLICY_MINPROM_ONLY,
    SUPPLIER_POLICY_MINPROM_PRIORITY,
    SUPPLIER_POLICY_NORMAL,
    SUPPLIER_RUN_ADDITIONAL,
    SUPPLIER_RUN_INITIAL,
    TERMINAL_JOB_STATUSES,
    VALID_SUPPLIER_SEARCH_POLICIES,
    VALID_JOB_MODES,
    cancel_running_job,
    cleanup_expired_jobs,
    create_job,
    enqueue_job,
    package_job_output_items,
    package_job_outputs,
    read_supplier_exclusions,
    read_supplier_exclusions_payload,
    recover_interrupted_jobs,
    write_dobor_context,
    write_supplier_exclusions,
)
from .models import (
    AccountLinkToken,
    BillingTransaction,
    Client,
    ClientTariffOverride,
    ClientTelegramAccount,
    Job,
    JobFile,
    JobSource,
    OnboardingReminder,
    SupplierResult,
    SystemSettings,
    TariffPackage,
    UserJourneyEvent,
    WebEmailVerificationToken,
    WebPasswordResetRequest,
    WebRegistrationAttempt,
    WebSession,
    WebUser,
    now_utc,
    parse_json_dict,
    parse_json_list,
)
from .procurement_sources import source_label, source_payloads_from_text
from .repository import (
    client_access_error,
    commercial_jobs_query,
    current_function_usage,
    ensure_client_telegram_account,
    ensure_pending_client_telegram_account,
    get_client_by_telegram_id,
    get_or_create_settings,
    is_pending_telegram_id,
    is_internal_job_record,
    new_pending_telegram_id,
    normalize_telegram_username,
    requested_function_units,
    seed_owner_client,
    supplier_target_for_client,
)
from .report_builder import write_quote_request_docx
from .schemas import (
    AiTestRequest,
    ClientCreate,
    ClientMergeRequest,
    ClientPatch,
    ClientTelegramAccountCreate,
    ClientTelegramAccountPatch,
    ClientTariffOverridePatch,
    BillingGrantCreate,
    LoginRequest,
    ManualJobCreate,
    SettingsPatch,
    TariffPackageCreate,
    TariffPackagePatch,
    WebEmailChangeRequest,
    WebLoginRequest,
    WebEmailVerificationConfirm,
    WebPasswordResetComplete,
    WebPasswordResetRequestCreate,
    WebRegisterRequest,
)
from .readiness import build_readiness
from .security import (
    ADMIN_COOKIE,
    admin_cookie_max_age,
    check_admin_credentials,
    create_admin_session,
    require_admin,
    verify_admin_session,
)
from .web_auth import (
    CSRF_HEADER,
    YANDEX_OAUTH_COOKIE,
    WebAuthContext,
    authenticate_web_user,
    build_telegram_oauth_url,
    build_yandex_oauth_url,
    clear_customer_session_cookie,
    clear_yandex_oauth_state_cookie,
    create_email_verification_token,
    create_web_session,
    create_web_user,
    extract_telegram_auth_payload,
    fetch_yandex_oauth_profile,
    generate_temporary_password,
    get_or_create_telegram_web_user,
    get_or_create_yandex_web_user,
    hash_password,
    send_email_verification,
    optional_web_context,
    require_customer_csrf,
    require_web_context,
    revoke_web_session,
    set_customer_session_cookie,
    set_yandex_oauth_state_cookie,
    validate_email,
    verify_email_token,
    verify_telegram_auth_payload,
    yandex_oauth_redirect_uri,
)
from .supplier_search import (
    _google_credentials,
    _provider_order,
    _yandex_credentials,
    get_minprom_registry_cache_status,
    store_minprom_registry_xlsx_cache,
)

ANALYTICS_EXCLUDED_WEB_EMAILS = {"79210629909@ya.ru"}
ANALYTICS_EXCLUDED_TELEGRAM_USERNAMES = {"lexelence", "lexs"}
ANALYTICS_EXCLUDED_TELEGRAM_IDS = {"320433711"}
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
logger = logging.getLogger(__name__)
from .outreach_api import router as outreach_router
from .mcp_api import router as mcp_router, admin_router as mcp_admin_router

app = FastAPI(title="TenderLex API", version="0.1.0")
app.include_router(outreach_router)
app.include_router(mcp_router)
app.include_router(mcp_admin_router)
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
CUSTOMER_AUTH_ATTEMPTS: dict[str, list[float]] = {}
CUSTOMER_REGISTRATION_HOUR_LIMIT = 3
CUSTOMER_REGISTRATION_DAY_LIMIT = 8
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _mark_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


@app.on_event("startup")
async def startup() -> None:
    config.storage_path.mkdir(parents=True, exist_ok=True)
    init_db()
    db = next(db_session())
    recovered_job_ids: list[str] = []
    try:
        settings = get_or_create_settings(db)
        seed_owner_client(db)
        cleanup_expired_jobs(db, settings)
        expire_stale_confirmations(db)
        recovered_job_ids = recover_interrupted_jobs(db)
        try:
            from .db import SessionLocal
            from .outreach_models import OutreachCampaign, OutreachSearchTask
            from .outreach_mail import run_campaign_worker, ACTIVE_CAMPAIGN_TASKS
            running_camps = db.query(OutreachCampaign).filter(OutreachCampaign.status == "running").all()
            for rc in running_camps:
                task = asyncio.create_task(run_campaign_worker(rc.id, SessionLocal))
                ACTIVE_CAMPAIGN_TASKS[rc.id] = task

            # Recover interrupted search tasks into paused state so candidates are not lost
            stale_searches = db.query(OutreachSearchTask).filter(OutreachSearchTask.status == "running").all()
            for s_task in stale_searches:
                s_task.status = "paused"
                s_task.message = "Сбор приостановлен при перезапуске сервера. Сайты сохранены. Нажмите «Продолжить»."
                try:
                    waves = json.loads(s_task.waves_json) if s_task.waves_json else []
                    for w in waves:
                        if w.get("status") == "running":
                            w["status"] = "paused"
                    s_task.waves_json = json.dumps(waves, ensure_ascii=False)
                except Exception:
                    pass
            # Launch background periodic IMAP poller (runs quietly every 45s)
            asyncio.create_task(_background_imap_loop())
        except Exception as e:
            logger.warning(f"Error resuming campaigns on startup: {e}")
    finally:
        db.close()
    for job_id in recovered_job_ids:
        enqueue_job(job_id)


async def _background_imap_loop() -> None:
    """Quietly and continuously fetches new incoming supplier replies in the background every 45s."""
    from .db import SessionLocal
    from .outreach_models import OutreachSettings
    from .outreach_mail import sync_imap_inbox

    await asyncio.sleep(10)
    while True:
        try:
            with SessionLocal() as db:
                settings = db.query(OutreachSettings).first()
                if settings and settings.imap_password and settings.imap_host:
                    await asyncio.to_thread(sync_imap_inbox, settings=settings, db=db, limit=50)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Background IMAP worker exception: {e}")
        await asyncio.sleep(45)


@app.get("/api/health")
def health(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return {
        "ok": True,
        "domain": settings.public_base_url,
        "logistics_enabled": settings.logistics_enabled,
    }


@app.get("/api/health/ready")
def readiness(response: Response, db: Session = Depends(db_session)) -> dict:
    payload = build_readiness(db)
    if not payload.get("ok"):
        response.status_code = 503
    return payload


@app.get("/api/public/site")
def public_site_api(db: Session = Depends(db_session)) -> dict:
    return public_site_payload(db)


def _customer_request_ip(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for", "") or "").split(",", 1)[0].strip()
    client_ip = forwarded or (request.client.host if request.client else "unknown")
    return client_ip[:80]


def _customer_auth_key(request: Request, email: str) -> str:
    client_ip = _customer_request_ip(request)
    return f"{client_ip}:{str(email or '').strip().lower()[:255]}"


def _client_ip(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def _check_customer_auth_rate(request: Request, email: str) -> str:
    key = _customer_auth_key(request, email)
    now = time.time()
    attempts = [item for item in CUSTOMER_AUTH_ATTEMPTS.get(key, []) if now - item < 600]
    CUSTOMER_AUTH_ATTEMPTS[key] = attempts
    if len(attempts) >= 8:
        raise HTTPException(status_code=429, detail="Слишком много попыток входа. Подождите несколько минут.")
    return key


def _record_customer_auth_failure(key: str) -> None:
    CUSTOMER_AUTH_ATTEMPTS[key] = [*CUSTOMER_AUTH_ATTEMPTS.get(key, []), time.time()]


def _record_customer_registration_attempt(db: Session, request: Request, email: str, status: str) -> None:
    db.add(
        WebRegistrationAttempt(
            email=str(email or "").strip().lower()[:255],
            ip_address=_customer_request_ip(request),
            status=status[:40],
            user_agent=str(request.headers.get("user-agent", ""))[:1000],
        )
    )
    db.commit()


def _check_customer_registration_rate(db: Session, request: Request, email: str) -> None:
    ip_address = _customer_request_ip(request)
    now = now_utc()
    hour_cutoff = now - timedelta(hours=1)
    day_cutoff = now - timedelta(days=1)
    hour_count = (
        db.query(WebRegistrationAttempt.id)
        .filter(WebRegistrationAttempt.ip_address == ip_address)
        .filter(WebRegistrationAttempt.created_at >= hour_cutoff)
        .count()
    )
    day_count = (
        db.query(WebRegistrationAttempt.id)
        .filter(WebRegistrationAttempt.ip_address == ip_address)
        .filter(WebRegistrationAttempt.created_at >= day_cutoff)
        .count()
    )
    if hour_count >= CUSTOMER_REGISTRATION_HOUR_LIMIT or day_count >= CUSTOMER_REGISTRATION_DAY_LIMIT:
        _record_customer_registration_attempt(db, request, email, "rate_limited")
        raise HTTPException(status_code=429, detail="Слишком много регистраций. Попробуйте позже или напишите нам.")


def _send_customer_verification_email(db: Session, user: WebUser, request: Request) -> bool:
    settings = get_or_create_settings(db)
    token, _record = create_email_verification_token(db, user, request=request)
    try:
        return send_email_verification(user, token, public_base_url=settings.public_base_url)
    except Exception:
        return False


@app.post("/api/customer/auth/register")
def customer_register_api(
    data: WebRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> dict:
    if str(data.website or "").strip():
        _record_customer_registration_attempt(db, request, data.email, "bot_blocked")
        raise HTTPException(status_code=400, detail="Не удалось создать кабинет.")
    if not bool(data.terms_accepted) or not bool(data.personal_data_consent):
        _record_customer_registration_attempt(db, request, data.email, "rejected_consent")
        raise HTTPException(
            status_code=400,
            detail="Для регистрации необходимо принять оферту и согласие на обработку персональных данных.",
        )
    _check_customer_registration_rate(db, request, data.email)
    key = _check_customer_auth_rate(request, data.email)
    try:
        user = create_web_user(
            db,
            email=data.email,
            password=data.password,
            name=data.name,
            email_verified=False,
            commit=False,
        )
        client_ip = _client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        doc_version = str(data.legal_version or LEGAL_VERSION).strip() or LEGAL_VERSION
        record_legal_acceptance(
            db,
            subject_type="web_user",
            subject_id=user.id,
            document_type=LEGAL_DOCUMENT_TERMS,
            source="web",
            document_version=doc_version,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        record_legal_acceptance(
            db,
            subject_type="web_user",
            subject_id=user.id,
            document_type=LEGAL_DOCUMENT_PERSONAL_DATA,
            source="web",
            document_version=doc_version,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        db.rollback()
        _record_customer_registration_attempt(db, request, data.email, "failed")
        _record_customer_auth_failure(key)
        detail = str(exc)
        status_code = 409 if "уже зарегистрирован" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        db.rollback()
        _record_customer_registration_attempt(db, request, data.email, "failed")
        _record_customer_auth_failure(key)
        raise exc
    _record_customer_registration_attempt(db, request, user.email, "created")
    email_sent = _send_customer_verification_email(db, user, request)
    token, csrf_token, session = create_web_session(db, user, request=request)
    set_customer_session_cookie(response, token)
    CUSTOMER_AUTH_ATTEMPTS.pop(key, None)
    payload = customer_session_payload(db, user, csrf_token=csrf_token, authenticated=True)
    payload["verification_email_sent"] = email_sent
    payload["message"] = (
        "Кабинет создан. Подтвердите email, чтобы запускать задачи."
        if email_sent
        else "Кабинет создан. Для подтверждения email напишите нам через контакты на сайте."
    )
    return payload


@app.post("/api/customer/auth/login")
def customer_login_api(
    data: WebLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> dict:
    key = _check_customer_auth_rate(request, data.email)
    user = authenticate_web_user(db, data.email, data.password)
    if not user:
        _record_customer_auth_failure(key)
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")
    token, csrf_token, session = create_web_session(db, user, request=request)
    set_customer_session_cookie(response, token)
    CUSTOMER_AUTH_ATTEMPTS.pop(key, None)
    return customer_session_payload(db, user, csrf_token=csrf_token, authenticated=True)


@app.get("/api/customer/auth/yandex/login")
def customer_yandex_login_api(
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> RedirectResponse:
    settings = get_or_create_settings(db)
    redirect_uri = yandex_oauth_redirect_uri(public_base_url=settings.public_base_url)
    state = secrets.token_urlsafe(32)
    try:
        auth_url = build_yandex_oauth_url(redirect_uri=redirect_uri, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    redirect_resp = RedirectResponse(url=auth_url, status_code=303)
    set_yandex_oauth_state_cookie(redirect_resp, state)
    return redirect_resp


@app.get("/api/customer/auth/yandex/url")
def customer_yandex_auth_url_api(
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> dict:
    settings = get_or_create_settings(db)
    redirect_uri = yandex_oauth_redirect_uri(public_base_url=settings.public_base_url)
    state = secrets.token_urlsafe(32)
    try:
        auth_url = build_yandex_oauth_url(redirect_uri=redirect_uri, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    set_yandex_oauth_state_cookie(response, state)
    return {"url": auth_url, "state": state}


@app.get("/api/customer/auth/yandex/callback")
def customer_yandex_callback_api(
    request: Request,
    response: Response,
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
    db: Session = Depends(db_session),
) -> RedirectResponse:
    target_error_url = "/cabinet?auth_error="
    if error:
        logger.warning("yandex_oauth_user_declined", extra={"error": error, "description": error_description})
        return RedirectResponse(url=f"{target_error_url}yandex_declined", status_code=303)

    if not code:
        return RedirectResponse(url=f"{target_error_url}no_code", status_code=303)

    expected_state = request.cookies.get(YANDEX_OAUTH_COOKIE, "")
    if not state or not expected_state or not hmac.compare_digest(state, expected_state):
        logger.warning("yandex_oauth_state_mismatch", extra={"received": state, "has_expected": bool(expected_state)})
        resp = RedirectResponse(url=f"{target_error_url}invalid_state", status_code=303)
        clear_yandex_oauth_state_cookie(resp)
        return resp

    settings = get_or_create_settings(db)
    redirect_uri = yandex_oauth_redirect_uri(public_base_url=settings.public_base_url)

    try:
        profile = fetch_yandex_oauth_profile(code, redirect_uri)
    except Exception as exc:
        logger.error("yandex_oauth_profile_error", extra={"error": str(exc)})
        resp = RedirectResponse(url=f"{target_error_url}fetch_failed", status_code=303)
        clear_yandex_oauth_state_cookie(resp)
        return resp

    try:
        user, is_new = get_or_create_yandex_web_user(
            db,
            yandex_user_id=profile["yandex_id"],
            email=profile["email"],
            name=profile.get("name", ""),
        )
    except Exception as exc:
        logger.error("yandex_oauth_user_creation_error", extra={"error": str(exc)})
        resp = RedirectResponse(url=f"{target_error_url}user_creation_failed", status_code=303)
        clear_yandex_oauth_state_cookie(resp)
        return resp

    token, csrf_token, session = create_web_session(db, user, request=request)
    resp = RedirectResponse(url="/cabinet", status_code=303)
    set_customer_session_cookie(resp, token)
    clear_yandex_oauth_state_cookie(resp)
    return resp


@app.get("/api/customer/auth/telegram/login")
def customer_telegram_login_api(
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> RedirectResponse:
    settings = get_or_create_settings(db)
    try:
        telegram_auth_url = build_telegram_oauth_url(public_base_url=settings.public_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url=telegram_auth_url, status_code=303)


@app.get("/api/customer/auth/telegram/callback")
def customer_telegram_callback_api(
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> RedirectResponse:
    target_error_url = "/cabinet?auth_error="
    query_params = dict(request.query_params)
    auth_data = extract_telegram_auth_payload(query_params)

    if not auth_data.get("hash") or not auth_data.get("id"):
        logger.warning(
            "telegram_callback_missing_data",
            extra={"received_keys": list(query_params.keys())},
        )
        return RedirectResponse(
            url=f"{target_error_url}telegram_no_data", status_code=303
        )

    if not verify_telegram_auth_payload(auth_data, config.bot_token):
        logger.warning(
            "telegram_auth_invalid_signature",
            extra={
                "params": {
                    k: v for k, v in auth_data.items() if k != "hash"
                }
            },
        )
        return RedirectResponse(
            url=f"{target_error_url}telegram_invalid", status_code=303
        )

    try:
        user, is_new = get_or_create_telegram_web_user(
            db,
            telegram_user_id=auth_data["id"],
            username=str(auth_data.get("username") or ""),
            first_name=str(auth_data.get("first_name") or ""),
            last_name=str(auth_data.get("last_name") or ""),
            photo_url=str(auth_data.get("photo_url") or ""),
        )
    except Exception as exc:
        logger.error("telegram_auth_user_creation_error", extra={"error": str(exc)})
        return RedirectResponse(
            url=f"{target_error_url}user_creation_failed", status_code=303
        )

    token, csrf_token, session = create_web_session(db, user, request=request)
    resp = RedirectResponse(url="/cabinet", status_code=303)
    set_customer_session_cookie(resp, token)
    return resp


@app.post("/api/customer/auth/telegram/verify")
def customer_telegram_verify_api(
    data: dict,
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
) -> dict:
    auth_data = extract_telegram_auth_payload(data) if isinstance(data, dict) else {}
    if not isinstance(auth_data, dict) or not auth_data.get("hash") or not auth_data.get("id"):
        raise HTTPException(
            status_code=400, detail="Не переданы данные авторизации Telegram."
        )

    if not verify_telegram_auth_payload(auth_data, config.bot_token):
        raise HTTPException(
            status_code=400,
            detail="Неверная подпись данных Telegram или время сессии истекло.",
        )

    try:
        user, is_new = get_or_create_telegram_web_user(
            db,
            telegram_user_id=auth_data["id"],
            username=str(auth_data.get("username") or ""),
            first_name=str(auth_data.get("first_name") or ""),
            last_name=str(auth_data.get("last_name") or ""),
            photo_url=str(auth_data.get("photo_url") or ""),
        )
    except Exception as exc:
        logger.error("telegram_auth_user_creation_error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    token, csrf_token, session = create_web_session(db, user, request=request)
    set_customer_session_cookie(response, token)
    return {
        "success": True,
        "is_new": is_new,
        "csrf_token": csrf_token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        },
    }


@app.post("/api/customer/auth/password-reset/request")
def customer_password_reset_request_api(
    data: WebPasswordResetRequestCreate,
    request: Request,
    db: Session = Depends(db_session),
) -> dict:
    key = _check_customer_auth_rate(request, data.email)
    _record_customer_auth_failure(key)
    try:
        email = validate_email(data.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = db.query(WebUser).filter(WebUser.email == email, WebUser.is_active.is_(True)).first()
    if user:
        recent_cutoff = now_utc() - timedelta(minutes=15)
        recent = (
            db.query(WebPasswordResetRequest.id)
            .filter(WebPasswordResetRequest.user_id == user.id)
            .filter(WebPasswordResetRequest.status == "open")
            .filter(WebPasswordResetRequest.created_at >= recent_cutoff)
            .first()
        )
        if not recent:
            db.add(
                WebPasswordResetRequest(
                    user_id=user.id,
                    email=email,
                    requested_ip=str(getattr(request.client, "host", "") or "")[:80],
                    user_agent=str(request.headers.get("user-agent", ""))[:1000],
                )
            )
            db.commit()
    return {
        "success": True,
        "message": "Если такой кабинет зарегистрирован, заявка отправлена. Мы поможем восстановить доступ через указанные на сайте контакты.",
    }


@app.post("/api/customer/auth/verify-email/request")
def customer_email_verification_request_api(
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    if context.user.is_email_verified:
        return {"success": True, "message": "Email уже подтверждён."}
    key = _check_customer_auth_rate(request, context.user.email)
    _record_customer_auth_failure(key)
    email_sent = _send_customer_verification_email(db, context.user, request)
    return {
        "success": True,
        "verification_email_sent": email_sent,
        "message": (
            "Письмо отправлено. Проверьте почту."
            if email_sent
            else "Для подтверждения email напишите нам через контакты на сайте."
        ),
    }


@app.get("/api/customer/auth/verify-email/confirm")
def customer_email_verification_confirm_link(token: str):
    return RedirectResponse(f"/cabinet?email_verify_token={quote(token, safe='')}", status_code=303)


@app.get("/api/customer/auth/unsubscribe")
def customer_unsubscribe_api(token: str = "", db: Session = Depends(db_session)):
    from .nurturing import unsubscribe_by_token

    success, message = unsubscribe_by_token(db, token)
    status_title = "Вы успешно отписались" if success else "Ошибка отписки"
    status_desc = (
        "Вы успешно отписались от уведомлений и обучающих рассылок TenderLex. Мы больше не будем присылать вам автоматические письма."
        if success
        else message
    )
    badge_color = "#0f766e" if success else "#e11d48"
    icon = "✅" if success else "⚠️"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{status_title} — TenderLex</title>
</head>
<body style="margin:0;padding:40px 16px;background:#f8fafc;font-family:Arial,Helvetica,sans-serif;color:#1e293b;display:flex;justify-content:center;align-items:center;min-height:80vh;">
  <div style="max-width:480px;width:100%;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:32px 28px;text-align:center;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);box-sizing:border-box;">
    <div style="font-size:36px;margin-bottom:12px;">{icon}</div>
    <h1 style="font-size:20px;font-weight:bold;color:#0f172a;margin:0 0 10px 0;">{status_title}</h1>
    <p style="font-size:14px;line-height:1.6;color:#475569;margin:0 0 24px 0;">{status_desc}</p>
    <a href="https://tenderlex.ru" style="display:inline-block;background:{badge_color};color:#ffffff;text-decoration:none;font-weight:bold;font-size:14px;padding:11px 24px;border-radius:8px;">На главную TenderLex</a>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200 if success else 400)


@app.post("/api/customer/auth/verify-email/confirm")
def customer_email_verification_confirm_api(data: WebEmailVerificationConfirm, db: Session = Depends(db_session)) -> dict:
    try:
        user = verify_email_token(db, data.token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": customer_user_to_dict(db, user)}


@app.patch("/api/customer/auth/email")
def customer_email_change_api(
    data: WebEmailChangeRequest,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    new_email = validate_email(data.email)
    current_email = context.user.email
    if new_email != current_email:
        existing = (
            db.query(WebUser.id)
            .filter(WebUser.email == new_email)
            .filter(WebUser.id != context.user.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже зарегистрирован.")
        context.user.email = new_email
        context.user.is_email_verified = False
        db.commit()
        db.refresh(context.user)

    key = _check_customer_auth_rate(request, context.user.email)
    _record_customer_auth_failure(key)
    email_sent = _send_customer_verification_email(db, context.user, request)
    payload = customer_session_payload(db, context.user, csrf_token=context.session.csrf_token if context.session else "", authenticated=True)
    payload["verification_email_sent"] = email_sent
    payload["message"] = (
        "Email обновлён. Проверьте новое письмо для подтверждения."
        if email_sent
        else "Email обновлён. Не удалось отправить письмо, попробуйте ещё раз."
    )
    return payload


@app.post("/api/customer/auth/logout")
def customer_logout_api(
    request: Request,
    response: Response,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    revoke_web_session(db, context.session)
    clear_customer_session_cookie(response)
    return {"ok": True}


@app.get("/api/customer/auth/session")
def customer_session_api(
    response: Response,
    context: WebAuthContext | None = Depends(optional_web_context),
    db: Session = Depends(db_session),
) -> dict:
    _mark_no_store(response)
    if not context:
        return {"authenticated": False}
    csrf_token = context.session.csrf_token if context.session else ""
    return customer_session_payload(db, context.user, csrf_token=csrf_token, authenticated=True)


@app.get("/api/customer/me")
def customer_me_api(
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    csrf_token = context.session.csrf_token if context.session else ""
    return customer_session_payload(db, context.user, csrf_token=csrf_token, authenticated=True)


@app.get("/api/customer/jobs")
def customer_jobs_api(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    include_pagination: bool = False,
    q: str = "",
    mode: str = "",
    policy: str = "",
    status: str = "",
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> list[dict] | dict:
    _mark_no_store(response)
    safe_limit = max(1, min(200, int(limit or 50)))
    safe_offset = max(0, int(offset or 0))
    query = commercial_jobs_query(db, context.user.client)
    clean_q = str(q or "").strip()
    if clean_q:
        pattern = f"%{clean_q}%"
        query = query.filter(
            or_(
                func.coalesce(Job.title, "").ilike(pattern),
                func.coalesce(Job.message, "").ilike(pattern),
                Job.files.any(JobFile.original_filename.ilike(pattern)),
            )
        )
    clean_mode = str(mode or "").strip()
    if clean_mode in {MODE_SUPPLIER_SEARCH, MODE_EXACT_PRODUCT, MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS}:
        query = query.filter(Job.mode == clean_mode)
    clean_policy = str(policy or "").strip()
    if clean_policy in {"normal", "minprom_registry_only", "minprom_registry_priority"}:
        query = query.filter(Job.supplier_search_policy == clean_policy)
    clean_status = str(status or "").strip()
    if clean_status:
        query = query.filter(Job.status == clean_status)
    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset(safe_offset).limit(safe_limit).all()
    items = [customer_job_to_dict(job) for job in jobs]
    if include_pagination:
        return {"items": items, "total": total, "limit": safe_limit, "offset": safe_offset}
    return items


@app.get("/api/customer/billing/transactions")
def customer_billing_transactions_api(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    kind: str = "",
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    _mark_no_store(response)
    safe_limit = max(1, min(100, int(limit or 50)))
    safe_offset = max(0, int(offset or 0))
    client = context.user.client
    if not client:
        return {"items": [], "total": 0, "limit": safe_limit, "offset": safe_offset}

    query = (
        db.query(BillingTransaction)
        .options(selectinload(BillingTransaction.job))
        .filter(BillingTransaction.client_id == client.id)
        .filter(BillingTransaction.operation.in_([OP_CHARGE, OP_GRANT, OP_RELEASE, OP_MANUAL_DEBIT]))
    )
    clean_kind = str(kind or "").strip()
    if clean_kind:
        query = query.filter(BillingTransaction.kind == clean_kind)

    total = query.count()
    rows = (
        query
        .order_by(BillingTransaction.created_at.desc())
        .offset(safe_offset)
        .limit(safe_limit)
        .all()
    )
    return {
        "items": [customer_billing_transaction_to_dict(row) for row in rows],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }


@app.post("/api/customer/jobs")
async def customer_create_job_route(
    request: Request,
    mode: str = Form(default=MODE_SUPPLIER_SEARCH),
    supplier_search_policy: str = Form(default=SUPPLIER_POLICY_NORMAL),
    text: str = Form(default=""),
    source_urls: str = Form(default=""),
    target_suppliers: int = Form(default=0),
    files: list[UploadFile] = File(default=[]),
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    return await create_customer_job_api(
        mode=mode,
        supplier_search_policy=supplier_search_policy,
        text=text,
        source_urls=source_urls,
        target_suppliers=target_suppliers,
        files=files,
        context=context,
        db=db,
    )


@app.get("/api/customer/jobs/{job_id}")
def customer_job_detail_api(
    job_id: str,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    job = _customer_job_or_404(db, job_id, context)
    return customer_job_to_dict(job, include_files=True)



@app.post("/api/customer/jobs/{job_id}/retry")
def customer_job_retry_api(
    job_id: str,
    policy: str | None = Query(default=None),
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    job = _customer_job_or_404(db, job_id, context)
    if policy:
        normalized = _normalize_supplier_search_policy_for_job(job.mode, policy)
        job.supplier_search_policy = normalized
    job.status = "pending"
    job.progress = 0
    job.error = ""
    job.message = "Повторный запуск задачи" + (" (обычный поиск)" if getattr(job, "supplier_search_policy", "normal") == "normal" else "")
    job.updated_at = now_utc()
    db.commit()
    enqueue_job(job.id)
    return {"ok": True, "message": "Задача успешно перезапущена"}


@app.get("/api/customer/jobs/{job_id}/download")
def customer_job_download_route(
    job_id: str,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
):
    return download_customer_job_api(job_id, context=context, db=db)


@app.get("/api/customer/jobs/{job_id}/download/{file_kind}")
def customer_job_file_download_route(
    job_id: str,
    file_kind: str,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
):
    return download_customer_job_file_api(job_id, file_kind, context=context, db=db)


@app.get("/api/customer/jobs/{job_id}/quote-request")
def customer_job_quote_request_route(
    job_id: str,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    return customer_quote_request_api(job_id, context=context, db=db)


@app.post("/api/customer/jobs/{job_id}/cancel")
def customer_job_cancel_route(
    job_id: str,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    return cancel_customer_job_api(job_id, context=context, db=db)


@app.post("/api/customer/jobs/{job_id}/quote-request/docx")
async def customer_job_quote_request_docx_route(
    job_id: str,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
):
    require_customer_csrf(request, context)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Некорректный запрос.")
    return download_customer_quote_request_docx_api(
        job_id,
        content=str(payload.get("content") or ""),
        filename=str(payload.get("filename") or ""),
        context=context,
        db=db,
    )


@app.post("/api/customer/jobs/{job_id}/accept-partial")
def customer_accept_partial_route(
    job_id: str,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
):
    require_customer_csrf(request, context)
    return accept_customer_partial_job_api(job_id, context=context, db=db)


@app.post("/api/customer/jobs/{job_id}/decline-partial")
def customer_decline_partial_route(
    job_id: str,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    return decline_customer_partial_job_api(job_id, context=context, db=db)


@app.post("/api/customer/jobs/{job_id}/find-more-suppliers")
async def customer_find_more_suppliers_route(
    job_id: str,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    additional_prompt = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            additional_prompt = str(body.get("additional_prompt") or "").strip()
    except Exception:
        pass
    return create_additional_supplier_search_api(job_id, context=context, db=db, additional_prompt=additional_prompt)


@app.post("/api/customer/jobs/{job_id}/start-supplier-search")
async def customer_start_supplier_search_route(
    job_id: str,
    request: Request,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> dict:
    require_customer_csrf(request, context)
    if not context.user.is_email_verified:
        raise HTTPException(status_code=403, detail="Подтвердите email, чтобы запускать задачи.")
    supplier_search_policy = SUPPLIER_POLICY_NORMAL
    include_alternatives = True
    additional_prompt = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            supplier_search_policy = str(body.get("supplier_search_policy") or SUPPLIER_POLICY_NORMAL).strip()
            include_alternatives = bool(body.get("include_alternatives", True))
            additional_prompt = str(body.get("additional_prompt") or "").strip()
    except Exception:
        pass
    original_job = _customer_job_or_404(db, job_id, context)
    job = create_supplier_search_from_exact_product(
        db,
        client=context.user.client,
        original_job=original_job,
        created_by_telegram_id=f"web:{context.user.id}",
        supplier_search_policy=supplier_search_policy,
        include_alternatives=include_alternatives,
        additional_prompt=additional_prompt,
    )
    return {
        "success": True,
        "message": "Поиск поставщиков успешно запущен на основе подобранных товаров и аналогов.",
        "job": customer_job_to_dict(job, db=db),
    }


@app.post("/api/auth/login")
def login(data: LoginRequest, request: Request, response: Response) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = [item for item in LOGIN_ATTEMPTS.get(client_ip, []) if now - item < 600]
    if len(attempts) >= 8:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    if not check_admin_credentials(data.username, data.password):
        attempts.append(now)
        LOGIN_ATTEMPTS[client_ip] = attempts
        raise HTTPException(status_code=401, detail="Invalid login or password")
    LOGIN_ATTEMPTS.pop(client_ip, None)
    response.set_cookie(
        ADMIN_COOKIE,
        create_admin_session(data.username),
        max_age=admin_cookie_max_age(),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"ok": True, "username": data.username.strip()}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/session")
def auth_session(request: Request) -> dict:
    return {"ok": verify_admin_session(request.cookies.get(ADMIN_COOKIE, ""))}


@app.get("/api/auth/me", dependencies=[Depends(require_admin)])
def auth_me() -> dict:
    return {"ok": True}


@app.get("/api/dashboard", dependencies=[Depends(require_admin)])
def dashboard(db: Session = Depends(db_session)) -> dict:
    now = now_utc()
    week_ago = now - timedelta(days=7)
    return {
        "clients": db.query(Client).count(),
        "active_clients": db.query(Client).filter(Client.is_active.is_(True)).count(),
        "jobs": db.query(Job).count(),
        "running_jobs": db.query(Job).filter(Job.status.in_(["pending", "running"])).count(),
        "completed_jobs": db.query(Job).filter(Job.status.in_(["completed", "partial"])).count(),
        "failed_jobs": db.query(Job).filter(Job.status == "failed", Job.created_at >= week_ago).count(),
        "failed_jobs_total": db.query(Job).filter(Job.status == "failed").count(),
        "suppliers": db.query(SupplierResult).count(),
    }


@app.get("/api/ops/system-status", dependencies=[Depends(require_admin)])
async def system_status_ops(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    billing = await _fetch_yandex_billing_balance()
    return build_system_status(settings, db, yandex_balance=billing.get("balance"))


@app.get("/api/ops/supplier-quality", dependencies=[Depends(require_admin)])
def supplier_quality_ops(db: Session = Depends(db_session)) -> dict:
    jobs = (
        db.query(Job)
        .filter(Job.mode == "supplier_search")
        .order_by(Job.created_at.desc())
        .limit(100)
        .all()
    )
    return build_supplier_quality_snapshot(jobs)


@app.get("/api/ops/minprom-registry", dependencies=[Depends(require_admin)])
def minprom_registry_status_ops() -> dict:
    return get_minprom_registry_cache_status()


@app.post("/api/ops/minprom-registry/upload", dependencies=[Depends(require_admin)])
async def minprom_registry_upload_ops(file: UploadFile = File(...)) -> dict:
    filename = str(file.filename or "")
    payload = await file.read()
    try:
        return store_minprom_registry_xlsx_cache(payload, filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_yandex_billing_cache: dict = {"data": None, "timestamp": 0.0}
_YANDEX_BILLING_CACHE_TTL = 3600


async def _fetch_yandex_billing_balance() -> dict:
    global _yandex_billing_cache
    if (
        _yandex_billing_cache["data"] is not None
        and (time.time() - _yandex_billing_cache["timestamp"]) < _YANDEX_BILLING_CACHE_TTL
    ):
        return _yandex_billing_cache["data"]

    key_path = Path(__file__).parent.parent.parent / ".yandex_sa_key.json"
    if not key_path.exists():
        return {"balance": 0.0, "currency": "RUB", "is_active": False, "error": "key_not_found"}

    try:
        with open(key_path, "r") as f:
            obj = json.load(f)
        service_account_id = obj.get("service_account_id")
        key_id = obj.get("id")
        private_key = obj.get("private_key")
        if not service_account_id or not key_id or not private_key:
            return {"balance": 0.0, "currency": "RUB", "is_active": False, "error": "invalid_key"}

        now = int(time.time())
        payload = {
            "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            "iss": service_account_id,
            "iat": now,
            "exp": now + 3600,
        }
        encoded_token = jwt.encode(payload, private_key, algorithm="PS256", headers={"kid": key_id})

        async with httpx.AsyncClient(timeout=10.0) as client:
            iam_response = await client.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                json={"jwt": encoded_token},
            )
            if iam_response.status_code != 200:
                return {"balance": 0.0, "currency": "RUB", "is_active": False, "error": "iam_token_failed"}
            token = iam_response.json().get("iamToken")
            if not token:
                return {"balance": 0.0, "currency": "RUB", "is_active": False, "error": "iam_token_missing"}

            billing_id = obj.get("billing_account_id", "dn2i7mph462v2u6ff922")
            billing_response = await client.get(
                f"https://billing.api.cloud.yandex.net/billing/v1/billingAccounts/{billing_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if billing_response.status_code != 200:
                return {"balance": 0.0, "currency": "RUB", "is_active": False, "error": "billing_api_failed"}

            data = billing_response.json()
            result = {
                "balance": float(data.get("balance", 0.0)),
                "currency": data.get("currency", "RUB"),
                "is_active": data.get("active", False),
            }
            _yandex_billing_cache["data"] = result
            _yandex_billing_cache["timestamp"] = time.time()
            return result
    except Exception:
        return {"balance": 0.0, "currency": "RUB", "is_active": False, "error": "exception"}


@app.get("/api/ops/yandex-billing", dependencies=[Depends(require_admin)])
async def yandex_billing_ops() -> dict:
    return await _fetch_yandex_billing_balance()


@app.get("/api/analytics/bot", dependencies=[Depends(require_admin)])
def bot_analytics_api(period_days: int = 30, db: Session = Depends(db_session)) -> dict:
    safe_days = min(365, max(1, int(period_days or 30)))
    return build_bot_analytics(db, period_days=safe_days)


@app.get("/api/seo-analytics", dependencies=[Depends(require_admin)])
def seo_analytics_api(refresh: bool = False) -> dict:
    from app.yandex_seo import get_cached_or_fresh_analytics
    return get_cached_or_fresh_analytics(force_refresh=refresh)


@app.post("/api/seo-analytics/send-digest", dependencies=[Depends(require_admin)])
async def send_seo_digest_api() -> dict:
    from app.yandex_seo import send_seo_telegram_digest
    return await send_seo_telegram_digest()


@app.post("/api/seo-analytics/recrawl", dependencies=[Depends(require_admin)])
def seo_recrawl_api() -> dict:
    from app.yandex_seo import submit_sitemap_recrawl
    return submit_sitemap_recrawl()


@app.post("/api/seo-analytics/recommendations/{rec_id}/action", dependencies=[Depends(require_admin)])
def seo_rec_action_api(rec_id: str, payload: dict) -> dict:
    from app.yandex_seo import handle_recommendation_action
    action = payload.get("action", "pending")
    return handle_recommendation_action(rec_id, action)


@app.get("/api/settings", dependencies=[Depends(require_admin)])
def get_settings_api(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return settings_to_public_dict(settings)


@app.get("/api/settings/keys", dependencies=[Depends(require_admin)])
def get_settings_keys(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    # Mirrors EmailAgent behavior for editing custom provider JSON from the UI.
    return {
        "custom_ai_providers_json": settings.custom_ai_providers_json,
        "supplier_search_adapter_api_key": settings.supplier_search_adapter_api_key,
        "yandex_search_api_key": settings.yandex_search_api_key,
        "google_search_api_key": settings.google_search_api_key,
        "yookassa_secret_key": settings.yookassa_secret_key,
    }


@app.patch("/api/settings", dependencies=[Depends(require_admin)])
def patch_settings(data: SettingsPatch, db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    # Product rule: ATI/logistics is disabled for TenderLex.
    settings.logistics_enabled = False
    db.commit()
    db.refresh(settings)
    return {"success": True, "settings": settings_to_public_dict(settings)}


@app.get("/api/tariffs", dependencies=[Depends(require_admin)])
def list_tariffs_api(active_only: bool = False, db: Session = Depends(db_session)) -> list[dict]:
    return [tariff_to_dict(item) for item in list_tariffs(db, active_only=active_only)]


def _validate_tariff_unit_price(
    db: Session,
    *,
    kind: str,
    units: int,
    price_kopeks: int,
    is_active: bool,
    exclude_id: str | None = None,
) -> None:
    if not is_active or units <= 0:
        return
    existing = db.query(TariffPackage).filter(
        TariffPackage.kind == kind,
        TariffPackage.is_active.is_(True),
    )
    if exclude_id:
        existing = existing.filter(TariffPackage.id != exclude_id)
    other = existing.first()
    if other and other.units and other.units > 0:
        existing_unit_price = round(other.price_kopeks / other.units)
        new_unit_price = round(price_kopeks / units)
        if existing_unit_price != new_unit_price:
            raise HTTPException(
                status_code=400,
                detail="Все активные тарифы услуги должны иметь одинаковую цену за единицу",
            )


@app.post("/api/tariffs", dependencies=[Depends(require_admin)])
def create_tariff_api(data: TariffPackageCreate, db: Session = Depends(db_session)) -> dict:
    if data.kind not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown tariff kind")
    _validate_tariff_unit_price(
        db,
        kind=data.kind,
        units=data.units,
        price_kopeks=data.price_kopeks,
        is_active=data.is_active,
    )
    package = TariffPackage(**data.model_dump())
    db.add(package)
    db.commit()
    db.refresh(package)
    invalidate_tariff_packages_cache(db)
    return tariff_to_dict(package)


@app.patch("/api/tariffs/{package_id}", dependencies=[Depends(require_admin)])
def patch_tariff_api(package_id: str, data: TariffPackagePatch, db: Session = Depends(db_session)) -> dict:
    package = db.get(TariffPackage, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Tariff package not found")
    payload = data.model_dump(exclude_unset=True)
    if "kind" in payload and payload["kind"] not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown tariff kind")
    candidate_kind = payload.get("kind", package.kind)
    candidate_units = payload.get("units", package.units)
    candidate_price = payload.get("price_kopeks", package.price_kopeks)
    candidate_active = payload.get("is_active", package.is_active)
    _validate_tariff_unit_price(
        db,
        kind=candidate_kind,
        units=candidate_units,
        price_kopeks=candidate_price,
        is_active=candidate_active,
        exclude_id=package.id,
    )
    for key, value in payload.items():
        if value is not None:
            setattr(package, key, value)
    db.commit()
    db.refresh(package)
    invalidate_tariff_packages_cache(db)
    return tariff_to_dict(package)


@app.delete("/api/tariffs/{package_id}", dependencies=[Depends(require_admin)])
def delete_tariff_api(package_id: str, db: Session = Depends(db_session)) -> dict:
    package = db.get(TariffPackage, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Tariff package not found")
    db.delete(package)
    db.commit()
    invalidate_tariff_packages_cache()
    return {"success": True}


@app.get("/api/clients", dependencies=[Depends(require_admin)])
def list_clients(db: Session = Depends(db_session)) -> list[dict]:
    clients = (
        db.query(Client)
        .options(
            selectinload(Client.telegram_accounts),
            selectinload(Client.web_users),
            selectinload(Client.tariff_overrides),
        )
        .order_by(Client.created_at.desc())
        .all()
    )
    return [client_to_dict(client, db=db) for client in clients]


def _normalized_usernames(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        username = normalize_telegram_username(value)
        if username and username not in seen:
            normalized.append(username)
            seen.add(username)
    return normalized


@app.post("/api/clients", dependencies=[Depends(require_admin)])
def create_client(data: ClientCreate, db: Session = Depends(db_session)) -> dict:
    telegram_id = data.telegram_id.strip()
    usernames = _normalized_usernames([data.username, *data.telegram_usernames])
    if not telegram_id and not usernames:
        raise HTTPException(status_code=400, detail="Telegram username or Telegram ID is required")
    if telegram_id:
        existing = db.query(Client).filter(Client.telegram_id == telegram_id).first()
        existing_account = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == telegram_id).first()
        if existing_account:
            existing = existing_account.client
        if existing:
            raise HTTPException(status_code=409, detail="Client with this Telegram ID already exists")
    payload = data.model_dump(exclude={"telegram_usernames"})
    payload["telegram_id"] = telegram_id or new_pending_telegram_id()
    payload["username"] = usernames[0] if usernames else normalize_telegram_username(data.username)
    client = Client(**payload)
    db.add(client)
    db.flush()
    try:
        if telegram_id:
            ensure_client_telegram_account(
                db,
                client,
                telegram_id,
                username=usernames[0] if usernames else client.username,
                name=client.name,
                notes="Primary Telegram account",
            )
            for username in usernames[1:]:
                ensure_pending_client_telegram_account(db, client, username, name=client.name)
        else:
            for username in usernames:
                ensure_pending_client_telegram_account(db, client, username, name=client.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    db.refresh(client)
    return client_to_dict(client, db=db)


@app.patch("/api/clients/{client_id}", dependencies=[Depends(require_admin)])
def update_client(client_id: str, data: ClientPatch, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client_to_dict(client, db=db)


def _force_delete_client(db: Session, client: Client) -> None:
    jobs = db.query(Job).filter(Job.client_id == client.id).all()
    job_ids = [job.id for job in jobs]
    if job_ids:
        db.query(SupplierResult).filter(SupplierResult.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(JobFile).filter(JobFile.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(JobSource).filter(JobSource.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(BillingTransaction).filter(BillingTransaction.job_id.in_(job_ids)).delete(synchronize_session=False)

    web_users = db.query(WebUser).filter(WebUser.client_id == client.id).all()
    web_user_ids = [wu.id for wu in web_users]
    if web_user_ids:
        db.query(WebSession).filter(WebSession.user_id.in_(web_user_ids)).delete(synchronize_session=False)
        db.query(WebPasswordResetRequest).filter(WebPasswordResetRequest.user_id.in_(web_user_ids)).delete(synchronize_session=False)
        db.query(WebEmailVerificationToken).filter(WebEmailVerificationToken.user_id.in_(web_user_ids)).delete(synchronize_session=False)
        db.query(AccountLinkToken).filter(AccountLinkToken.web_user_id.in_(web_user_ids)).delete(synchronize_session=False)
        db.query(WebUser).filter(WebUser.client_id == client.id).delete(synchronize_session=False)

    db.query(AccountLinkToken).filter(
        (AccountLinkToken.client_id == client.id) | (AccountLinkToken.conflict_client_id == client.id)
    ).delete(synchronize_session=False)
    db.query(UserJourneyEvent).filter(UserJourneyEvent.client_id == client.id).delete(synchronize_session=False)
    db.query(OnboardingReminder).filter(OnboardingReminder.client_id == client.id).delete(synchronize_session=False)
    db.query(ClientTariffOverride).filter(ClientTariffOverride.client_id == client.id).delete(synchronize_session=False)
    db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == client.id).delete(synchronize_session=False)
    db.query(BillingTransaction).filter(BillingTransaction.client_id == client.id).delete(synchronize_session=False)

    for job in jobs:
        shutil.rmtree(config.storage_path / "jobs" / job.id, ignore_errors=True)
        db.delete(job)
    db.delete(client)


@app.delete("/api/clients/{client_id}", dependencies=[Depends(require_admin)])
def delete_client(client_id: str, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    _force_delete_client(db, client)
    db.commit()
    return {"success": True}


@app.post("/api/clients/{client_id}/merge", dependencies=[Depends(require_admin)])
def merge_client(client_id: str, data: ClientMergeRequest, db: Session = Depends(db_session)) -> dict:
    target = db.get(Client, client_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target client not found")
    source = db.get(Client, data.source_client_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source client not found")
    if source.id == target.id:
        raise HTTPException(status_code=400, detail="Choose another client to merge")
    if target.web_users and source.web_users:
        raise HTTPException(status_code=409, detail="У целевого и исходного клиента уже есть web-кабинеты. Оставьте один web-кабинет и повторите объединение.")

    target_needs_primary = not target.telegram_id or is_pending_telegram_id(target.telegram_id)
    source_primary_id = "" if is_pending_telegram_id(source.telegram_id) else source.telegram_id
    if target_needs_primary and source_primary_id:
        source.telegram_id = new_pending_telegram_id()
        target.telegram_id = source_primary_id
    if not target.username and source.username:
        target.username = source.username
    if not target.name and source.name:
        target.name = source.name
    target.is_active = bool(target.is_active or source.is_active)
    target.allowed_supplier_search = bool(target.allowed_supplier_search or source.allowed_supplier_search)
    target.allowed_procurement_report = bool(target.allowed_procurement_report or source.allowed_procurement_report)
    target.monthly_job_limit = max(int(target.monthly_job_limit or 0), int(source.monthly_job_limit or 0))
    target.monthly_supplier_search_limit = max(int(target.monthly_supplier_search_limit or 0), int(source.monthly_supplier_search_limit or 0))
    target.monthly_procurement_report_limit = max(int(target.monthly_procurement_report_limit or 0), int(source.monthly_procurement_report_limit or 0))
    target.monthly_file_limit = max(int(target.monthly_file_limit or 0), int(source.monthly_file_limit or 0))
    target.supplier_target_min = max(int(target.supplier_target_min or 0), int(source.supplier_target_min or 0))
    target.money_balance_kopeks = int(target.money_balance_kopeks or 0) + int(source.money_balance_kopeks or 0)
    target.money_reserved_kopeks = int(target.money_reserved_kopeks or 0) + int(source.money_reserved_kopeks or 0)
    merge_note = f"Объединён клиент: {source.name or source.username or source.telegram_id or source.id}"
    target.notes = "\n".join(item for item in [target.notes, merge_note] if item).strip()

    db.query(Job).filter(Job.client_id == source.id).update({Job.client_id: target.id}, synchronize_session=False)
    db.query(BillingTransaction).filter(BillingTransaction.client_id == source.id).update({BillingTransaction.client_id: target.id}, synchronize_session=False)
    db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == source.id).update({ClientTelegramAccount.client_id: target.id}, synchronize_session=False)
    db.query(WebUser).filter(WebUser.client_id == source.id).update({WebUser.client_id: target.id}, synchronize_session=False)
    db.query(ClientTariffOverride).filter(ClientTariffOverride.client_id == source.id).update({ClientTariffOverride.client_id: target.id}, synchronize_session=False)
    db.query(UserJourneyEvent).filter(UserJourneyEvent.client_id == source.id).update({UserJourneyEvent.client_id: target.id}, synchronize_session=False)
    db.query(OnboardingReminder).filter(OnboardingReminder.client_id == source.id).update({OnboardingReminder.client_id: target.id}, synchronize_session=False)
    db.query(AccountLinkToken).filter(AccountLinkToken.client_id == source.id).update({AccountLinkToken.client_id: target.id}, synchronize_session=False)
    db.flush()
    db.delete(source)
    db.commit()
    db.refresh(target)
    return {"success": True, "client": client_to_dict(target, db=db)}


@app.post("/api/clients/{client_id}/billing/grants", dependencies=[Depends(require_admin)])
def grant_client_billing_units(client_id: str, data: BillingGrantCreate, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    package = db.get(TariffPackage, data.package_id) if data.package_id else None
    operation = (data.operation or "grant").strip().lower()
    if operation not in {"grant", "debit", "manual_debit"}:
        raise HTTPException(status_code=400, detail="Unknown billing operation")
    if data.package_id and not package:
        raise HTTPException(status_code=404, detail="Tariff package not found")
    if package and operation != "grant":
        raise HTTPException(status_code=400, detail="Tariff package can only be used for grants")
    kind = package.kind if package else data.kind
    units = package.units if package else data.units
    if kind == KIND_MONEY:
        if package:
            raise HTTPException(status_code=400, detail="Money balance can only be changed directly")
        try:
            if operation == "grant":
                transaction = grant_money_balance(
                    db,
                    client,
                    amount_kopeks=data.amount_kopeks,
                    note=data.note or "Ручное пополнение баланса",
                    created_by="admin",
                    idempotency_key=data.idempotency_key or "",
                )
            else:
                transaction = debit_money_balance(
                    db,
                    client,
                    amount_kopeks=data.amount_kopeks,
                    note=data.note or "Ручное списание с баланса",
                    created_by="admin",
                    idempotency_key=data.idempotency_key or "",
                )
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.refresh(client)
        return {
            "success": True,
            "transaction": transaction_to_dict(transaction),
            "client": client_to_dict(client, db=db),
        }
    if kind not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown billing kind")
    try:
        if operation == "grant":
            note = data.note or (f"Начислен пакет «{package.name}»" if package else "Ручное пополнение пакета")
            transaction = grant_package_units(
                db,
                client,
                kind=kind,
                units=units,
                amount_kopeks=data.amount_kopeks,
                package_id=package.id if package else data.package_id,
                note=note,
                created_by="admin",
                idempotency_key=data.idempotency_key or "",
            )
        else:
            transaction = debit_package_units(
                db,
                client,
                kind=kind,
                units=units,
                amount_kopeks=data.amount_kopeks,
                note=data.note or "Ручное списание с баланса",
                created_by="admin",
                idempotency_key=data.idempotency_key or "",
            )
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(client)
    return {
        "success": True,
        "transaction": transaction_to_dict(transaction),
        "client": client_to_dict(client, db=db),
    }


@app.patch("/api/clients/{client_id}/tariff-overrides/{kind}", dependencies=[Depends(require_admin)])
def patch_client_tariff_override(
    client_id: str,
    kind: str,
    data: ClientTariffOverridePatch,
    db: Session = Depends(db_session),
) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    normalized_kind = str(kind or data.kind or "").strip()
    if normalized_kind not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown tariff kind")
    override = (
        db.query(ClientTariffOverride)
        .filter(ClientTariffOverride.client_id == client.id)
        .filter(ClientTariffOverride.kind == normalized_kind)
        .first()
    )
    if not override:
        override = ClientTariffOverride(client_id=client.id, kind=normalized_kind)
        db.add(override)
    override.price_kopeks = int(data.price_kopeks or 0)
    override.is_enabled = bool(data.is_enabled)
    override.note = data.note or ""
    override.updated_at = now_utc()
    db.commit()
    db.refresh(client)
    return {"success": True, "client": client_to_dict(client, db=db)}


@app.post("/api/clients/{client_id}/web-users/{user_id}/verify-email", dependencies=[Depends(require_admin)])
def admin_verify_web_user_email(client_id: str, user_id: str, db: Session = Depends(db_session)) -> dict:
    user = db.get(WebUser, user_id)
    if not user or user.client_id != client_id:
        raise HTTPException(status_code=404, detail="Web user not found")
    user.is_email_verified = True
    db.query(WebEmailVerificationToken).filter(
        WebEmailVerificationToken.user_id == user.id,
        WebEmailVerificationToken.used_at.is_(None),
    ).update({WebEmailVerificationToken.used_at: now_utc()}, synchronize_session=False)
    db.commit()
    return {"success": True, "client": client_to_dict(user.client, db=db)}


@app.delete("/api/clients/{client_id}/web-users/{user_id}", dependencies=[Depends(require_admin)])
def delete_client_web_user(client_id: str, user_id: str, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    user = db.get(WebUser, user_id)
    if not user or user.client_id != client_id:
        raise HTTPException(status_code=404, detail="Web user not found")

    db.query(WebSession).filter(WebSession.user_id == user.id).delete(synchronize_session=False)
    db.query(WebPasswordResetRequest).filter(WebPasswordResetRequest.user_id == user.id).delete(synchronize_session=False)
    db.query(WebEmailVerificationToken).filter(WebEmailVerificationToken.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    if not db.query(WebUser.id).filter(WebUser.client_id == client.id, WebUser.id != user.id).first():
        client.telegram_id = _primary_telegram_id_after_web_delete(client)
    db.commit()
    db.refresh(client)
    return {"success": True, "client": client_to_dict(client, db=db)}


def _primary_telegram_id_after_web_delete(client: Client) -> str:
    current_id = str(client.telegram_id or "")
    if current_id and not current_id.startswith("web:"):
        return current_id
    accounts = [
        account
        for account in client.telegram_accounts
        if account.telegram_id and not is_pending_telegram_id(account.telegram_id) and not str(account.telegram_id).startswith("web:")
    ]
    if not accounts:
        client.username = ""
        return new_pending_telegram_id()
    primary = sorted(accounts, key=lambda item: item.created_at, reverse=True)[0]
    if not client.username and primary.username:
        client.username = primary.username
    return primary.telegram_id


@app.get("/api/web-password-resets", dependencies=[Depends(require_admin)])
def list_web_password_resets(status: str = "open", db: Session = Depends(db_session)) -> list[dict]:
    query = db.query(WebPasswordResetRequest)
    if status and status != "all":
        query = query.filter(WebPasswordResetRequest.status == status)
    requests = query.order_by(WebPasswordResetRequest.created_at.desc()).limit(100).all()
    return [web_password_reset_to_dict(item) for item in requests]


@app.post("/api/web-password-resets/{request_id}/complete", dependencies=[Depends(require_admin)])
def complete_web_password_reset(request_id: str, data: WebPasswordResetComplete, db: Session = Depends(db_session)) -> dict:
    reset_request = db.get(WebPasswordResetRequest, request_id)
    if not reset_request:
        raise HTTPException(status_code=404, detail="Password reset request not found")
    user = reset_request.user
    if not user or not user.is_active:
        raise HTTPException(status_code=409, detail="Пользователь не найден или отключён.")
    temporary_password = str(data.password or "").strip() or generate_temporary_password()
    try:
        user.password_hash = hash_password(temporary_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.query(WebSession).filter(WebSession.user_id == user.id, WebSession.revoked_at.is_(None)).update(
        {WebSession.revoked_at: now_utc()},
        synchronize_session=False,
    )
    reset_request.status = "completed"
    reset_request.admin_note = data.note
    reset_request.resolved_by = "admin"
    reset_request.resolved_at = now_utc()
    db.commit()
    return {
        "success": True,
        "temporary_password": temporary_password,
        "request": web_password_reset_to_dict(reset_request),
        "client": client_to_dict(user.client, db=db),
    }


@app.post("/api/web-password-resets/{request_id}/ignore", dependencies=[Depends(require_admin)])
def ignore_web_password_reset(request_id: str, data: WebPasswordResetComplete, db: Session = Depends(db_session)) -> dict:
    reset_request = db.get(WebPasswordResetRequest, request_id)
    if not reset_request:
        raise HTTPException(status_code=404, detail="Password reset request not found")
    reset_request.status = "ignored"
    reset_request.admin_note = data.note
    reset_request.resolved_by = "admin"
    reset_request.resolved_at = now_utc()
    db.commit()
    return {"success": True, "request": web_password_reset_to_dict(reset_request)}


def _client_display_name(client: Client | None) -> str:
    if not client:
        return "без имени"
    return client.name or (f"@{client.username}" if client.username else "") or client.telegram_id or "без имени"


def _transfer_required_message(source_client: Client) -> str:
    return (
        "Telegram-аккаунт уже привязан к клиенту "
        f"«{_client_display_name(source_client)}». Подтвердите перенос, чтобы подключить "
        "этого менеджера к выбранному клиенту."
    )


def _find_existing_telegram_account(
    db: Session,
    *,
    telegram_id: str = "",
    username: str = "",
) -> ClientTelegramAccount | None:
    by_id = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.telegram_id == telegram_id)
        .first()
        if telegram_id
        else None
    )
    by_username = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.username == username)
        .first()
        if username
        else None
    )
    if by_id and by_username and by_id.id != by_username.id:
        raise HTTPException(
            status_code=409,
            detail="Telegram ID и username уже привязаны к разным клиентам. Проверьте данные перед переносом.",
        )
    return by_id or by_username


def _set_client_primary_from_accounts(db: Session, client: Client, *, moved_account_id: str = "") -> None:
    remaining = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.client_id == client.id)
        .filter(ClientTelegramAccount.id != moved_account_id)
        .order_by(ClientTelegramAccount.created_at.desc())
        .all()
    )
    if remaining:
        primary = remaining[0]
        client.telegram_id = primary.telegram_id
        client.username = primary.username
        return
    client.telegram_id = new_pending_telegram_id()
    client.username = ""
    client.is_active = False
    note = "Telegram-аккаунты перенесены к другому клиенту"
    client.notes = f"{client.notes}\n{note}".strip() if client.notes else note


def _move_existing_telegram_account(
    db: Session,
    *,
    target_client: Client,
    account: ClientTelegramAccount,
    data: ClientTelegramAccountCreate,
    username: str,
    telegram_id: str,
) -> ClientTelegramAccount:
    source_client = account.client
    if source_client.id == target_client.id:
        if telegram_id:
            account.telegram_id = telegram_id
        if username:
            account.username = username
        if data.name:
            account.name = data.name
        account.is_active = data.is_active
        if data.notes:
            account.notes = data.notes
        return account

    source_account_count = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.client_id == source_client.id)
        .count()
    )
    merge_source_client = bool(client_uses_trial_access(db, source_client) and source_account_count == 1)

    target_needs_primary = (
        not target_client.telegram_id
        or is_pending_telegram_id(target_client.telegram_id)
    )
    account.client = target_client
    if telegram_id:
        account.telegram_id = telegram_id
    if username:
        account.username = username
    if data.name:
        account.name = data.name
    account.is_active = data.is_active
    if data.notes:
        account.notes = data.notes
    elif account.notes.startswith("Trial "):
        account.notes = ""

    if not target_client.username and account.username:
        target_client.username = account.username

    if merge_source_client:
        if target_needs_primary:
            source_client.telegram_id = new_pending_telegram_id()
        db.query(Job).filter(Job.client_id == source_client.id).update(
            {Job.client_id: target_client.id},
            synchronize_session=False,
        )
        db.query(BillingTransaction).filter(BillingTransaction.client_id == source_client.id).update(
            {BillingTransaction.client_id: target_client.id},
            synchronize_session=False,
        )
        db.flush()
        db.delete(source_client)
    else:
        _set_client_primary_from_accounts(db, source_client, moved_account_id=account.id)
        db.flush()
    if target_needs_primary:
        target_client.telegram_id = account.telegram_id
    return account


@app.post("/api/clients/{client_id}/telegram-accounts", dependencies=[Depends(require_admin)])
def create_client_telegram_account(client_id: str, data: ClientTelegramAccountCreate, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    telegram_id = data.telegram_id.strip()
    username = normalize_telegram_username(data.username)
    if not telegram_id and not username:
        raise HTTPException(status_code=400, detail="Telegram username or Telegram ID is required")
    try:
        if telegram_id:
            existing_account = _find_existing_telegram_account(db, telegram_id=telegram_id, username=username)
            existing_client = db.query(Client).filter(Client.telegram_id == telegram_id).first()
            if existing_account and existing_account.client_id != client.id:
                if not data.transfer_existing:
                    raise HTTPException(status_code=409, detail=_transfer_required_message(existing_account.client))
                account = _move_existing_telegram_account(
                    db,
                    target_client=client,
                    account=existing_account,
                    data=data,
                    username=username,
                    telegram_id=telegram_id,
                )
            elif existing_client and existing_client.id != client.id:
                if not data.transfer_existing:
                    raise HTTPException(status_code=409, detail=_transfer_required_message(existing_client))
                existing_account = ensure_client_telegram_account(
                    db,
                    existing_client,
                    telegram_id,
                    username=existing_client.username,
                    name=existing_client.name,
                )
                account = _move_existing_telegram_account(
                    db,
                    target_client=client,
                    account=existing_account,
                    data=data,
                    username=username or existing_account.username,
                    telegram_id=telegram_id,
                )
            elif existing_account:
                account = _move_existing_telegram_account(
                    db,
                    target_client=client,
                    account=existing_account,
                    data=data,
                    username=username,
                    telegram_id=telegram_id,
                )
            else:
                account = ClientTelegramAccount(
                    client_id=client.id,
                    telegram_id=telegram_id,
                    username=username,
                    name=data.name,
                    is_active=data.is_active,
                    notes=data.notes,
                )
                db.add(account)
                if is_pending_telegram_id(client.telegram_id):
                    client.telegram_id = telegram_id
                if not client.username and username:
                    client.username = username
        else:
            existing_account = _find_existing_telegram_account(db, username=username)
            if existing_account and existing_account.client_id != client.id:
                if not data.transfer_existing:
                    raise HTTPException(status_code=409, detail=_transfer_required_message(existing_account.client))
                account = _move_existing_telegram_account(
                    db,
                    target_client=client,
                    account=existing_account,
                    data=data,
                    username=username,
                    telegram_id="",
                )
            elif existing_account:
                account = _move_existing_telegram_account(
                    db,
                    target_client=client,
                    account=existing_account,
                    data=data,
                    username=username,
                    telegram_id="",
                )
            else:
                account = ensure_pending_client_telegram_account(
                    db,
                    client,
                    username,
                    name=data.name,
                    notes=data.notes,
                )
                account.is_active = data.is_active
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    db.refresh(account)
    return telegram_account_to_dict(account)


@app.patch("/api/clients/{client_id}/telegram-accounts/{account_id}", dependencies=[Depends(require_admin)])
def update_client_telegram_account(
    client_id: str,
    account_id: str,
    data: ClientTelegramAccountPatch,
    db: Session = Depends(db_session),
) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    account = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.id == account_id)
        .filter(ClientTelegramAccount.client_id == client_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Telegram account not found")
    payload = data.model_dump(exclude_unset=True)
    if "telegram_id" in payload:
        next_telegram_id = str(payload.pop("telegram_id") or "").strip()
        if next_telegram_id:
            existing_account = (
                db.query(ClientTelegramAccount)
                .filter(ClientTelegramAccount.telegram_id == next_telegram_id)
                .first()
            )
            if existing_account and existing_account.id != account.id:
                raise HTTPException(status_code=409, detail="Telegram ID is already linked to a client")
            existing_client = db.query(Client).filter(Client.telegram_id == next_telegram_id).first()
            if existing_client and existing_client.id != client.id:
                raise HTTPException(status_code=409, detail="Telegram ID is already linked to a client")
            previous_telegram_id = account.telegram_id
            account.telegram_id = next_telegram_id
            if (
                not client.telegram_id
                or is_pending_telegram_id(client.telegram_id)
                or client.telegram_id == previous_telegram_id
            ):
                client.telegram_id = next_telegram_id
    if "username" in payload:
        next_username = normalize_telegram_username(str(payload.pop("username") or ""))
        if next_username:
            existing_username = (
                db.query(ClientTelegramAccount)
                .filter(ClientTelegramAccount.username == next_username)
                .first()
            )
            if existing_username and existing_username.id != account.id:
                raise HTTPException(status_code=409, detail="Telegram username is already linked to a client")
        account.username = next_username
        if next_username and not client.username:
            client.username = next_username
    for key, value in payload.items():
        if value is not None:
            setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return telegram_account_to_dict(account)


@app.delete("/api/clients/{client_id}/telegram-accounts/{account_id}", dependencies=[Depends(require_admin)])
def delete_client_telegram_account(
    client_id: str,
    account_id: str,
    db: Session = Depends(db_session),
) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    account = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.id == account_id)
        .filter(ClientTelegramAccount.client_id == client_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Telegram account not found")
    remaining_accounts = [item for item in client.telegram_accounts if item.id != account.id]
    db.delete(account)
    if remaining_accounts:
        primary = sorted(remaining_accounts, key=lambda item: item.created_at, reverse=True)[0]
        if client.telegram_id == account.telegram_id or not client.telegram_id:
            client.telegram_id = primary.telegram_id
        if client.username == account.username or not client.username:
            client.username = primary.username
    else:
        client.telegram_id = new_pending_telegram_id()
        client.username = ""
    db.commit()
    return {"success": True, "client": client_to_dict(client, db=db)}


@app.get("/api/jobs", dependencies=[Depends(require_admin)])
def list_jobs(
    include_internal: bool = False,
    limit: int = 2000,
    db: Session = Depends(db_session),
) -> list[dict]:
    safe_limit = max(1, min(10000, int(limit or 2000)))
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(safe_limit * 2).all()
    visible_jobs = jobs if include_internal else [job for job in jobs if not is_internal_job(job)]
    settings = get_or_create_settings(db)
    return [job_to_dict(job, settings=settings, db=db) for job in visible_jobs[:safe_limit]]


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_admin)])
def get_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    settings = get_or_create_settings(db)
    return job_to_dict(job, include_files=True, settings=settings, db=db)


@app.get("/api/jobs/{job_id}/download", dependencies=[Depends(require_admin)])
def download_job(job_id: str, db: Session = Depends(db_session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    output = package_job_outputs(job)
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(output, filename=output.name)


@app.get("/api/jobs/{job_id}/download/{file_kind}", dependencies=[Depends(require_admin)])
def download_job_file(job_id: str, file_kind: str, db: Session = Depends(db_session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    normalized_kind = str(file_kind or "").strip()
    output = None
    for item in package_job_output_items(job):
        if str(item.get("kind") or "") == normalized_kind:
            output = Path(str(item.get("path") or ""))
            break
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(output, filename=output.name)


@app.get("/api/jobs/{job_id}/input-files/{file_id}/download", dependencies=[Depends(require_admin)])
def download_job_input_file(job_id: str, file_id: str, db: Session = Depends(db_session)):
    file = (
        db.query(JobFile)
        .filter(JobFile.id == file_id)
        .filter(JobFile.job_id == job_id)
        .first()
    )
    if not file:
        raise HTTPException(status_code=404, detail="Input file not found")
    path = Path(str(file.stored_path or ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
    return FileResponse(path, filename=file.original_filename or path.name)


@app.get("/api/jobs/{job_id}/evidence", dependencies=[Depends(require_admin)])
def get_job_evidence(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return read_job_evidence_payload(job)


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_admin)])
def retry_job(job_id: str, policy: str | None = Query(default=None), db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if policy:
        job.supplier_search_policy = _normalize_supplier_search_policy_for_job(job.mode, policy)
    job.status = "pending"
    job.progress = 0
    job.error = ""
    job.message = "Повторный запуск задачи"
    db.commit()
    enqueue_job(job.id)
    return {"success": True, "job": job_to_dict(job)}


@app.post("/api/jobs/{job_id}/cancel", dependencies=[Depends(require_admin)])
def cancel_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in TERMINAL_JOB_STATUSES:
        return {"success": True, "job": job_to_dict(job), "note": "Job already in terminal status"}
    release_job_reservation(db, job, note="Резерв возвращён: задача отменена администратором")
    job.status = "cancelled"
    job.progress = 100
    job.error = "Отменено администратором"
    job.message = "Задача отменена"
    job.completed_at = now_utc()
    job.updated_at = now_utc()
    db.commit()
    cancel_running_job(job_id)
    return {"success": True, "job": job_to_dict(job)}


@app.post("/api/jobs/force-stale", dependencies=[Depends(require_admin)])
def force_fail_stale_jobs(
    max_minutes: int = 45,
    db: Session = Depends(db_session),
) -> dict:
    """Force-fail any job stuck in 'running' longer than max_minutes without update."""
    cutoff = now_utc() - timedelta(minutes=max(5, min(240, max_minutes)))
    stale_jobs = (
        db.query(Job)
        .filter(Job.status == "running", Job.updated_at < cutoff)
        .all()
    )
    cancelled = []
    for job in stale_jobs:
        release_job_reservation(db, job, note="Резерв возвращён: задача зависла и принудительно остановлена")
        job.status = "cancelled"
        job.progress = 100
        job.error = f"Принудительная остановка: задача зависла (без обновления >{max_minutes} мин)"
        job.message = "Задача принудительно остановлена"
        job.completed_at = now_utc()
        job.updated_at = now_utc()
        cancel_running_job(job.id)
        cancelled.append(job.id)
    if cancelled:
        db.commit()
    return {"cancelled": cancelled, "count": len(cancelled)}


@app.post("/api/jobs/resolve-failed", dependencies=[Depends(require_admin)])
def resolve_all_failed_jobs(db: Session = Depends(db_session)) -> dict:
    """Mark all failed jobs as resolved so they no longer trigger error alerts."""
    failed_jobs = db.query(Job).filter(Job.status == "failed").all()
    count = len(failed_jobs)
    for job in failed_jobs:
        job.status = "resolved"
        job.updated_at = now_utc()
    if count > 0:
        db.commit()
    return {"success": True, "resolved_count": count}


@app.post("/api/jobs/{job_id}/resolve", dependencies=[Depends(require_admin)])
def resolve_single_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    """Mark a single failed job as resolved."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "resolved"
    job.updated_at = now_utc()
    db.commit()
    return {"success": True, "job": job_to_dict(job)}


def read_job_evidence_payload(job: Job, *, storage_root: Path | None = None) -> dict:
    evidence_path = str(getattr(job, "evidence_path", "") or "")
    if not evidence_path:
        raise HTTPException(status_code=404, detail="Evidence not found")
    root = (storage_root or config.storage_path).resolve()
    path = Path(evidence_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Evidence is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Evidence JSON root must be an object")
    return payload


def build_supplier_quality_snapshot(jobs: list[Job], *, storage_root: Path | None = None) -> dict:
    status_counts: dict[str, int] = {}
    provider_status_counts: dict[str, dict[str, int]] = {}
    total_verified = 0
    supplier_jobs = 0
    underfilled = 0
    ai_required_failures = 0
    ai_degraded_jobs = 0
    durations: list[float] = []
    recent_failures: list[dict] = []

    for job in jobs:
        if str(getattr(job, "mode", "") or "") not in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}:
            continue
        if is_internal_job(job):
            continue
        supplier_jobs += 1
        status = str(getattr(job, "status", "") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        verified = int(getattr(job, "verified_count", 0) or 0)
        target = int(getattr(job, "target_suppliers", 0) or 0)
        total_verified += verified
        if status in {"completed", "partial", "needs_review", STATUS_AWAITING_CUSTOMER_CONFIRMATION, STATUS_CUSTOMER_DECLINED, STATUS_CONFIRMATION_EXPIRED, STATUS_DELIVERY_EXPIRED} and target and verified < target:
            underfilled += 1
        created_at = getattr(job, "created_at", None)
        completed_at = getattr(job, "completed_at", None)
        if created_at and completed_at:
            durations.append(max(0.0, (completed_at - created_at).total_seconds()))
        evidence = _safe_read_job_evidence(job, storage_root=storage_root)
        if evidence.get("ai_required") and status == "failed":
            ai_required_failures += 1
        if (
            evidence.get("candidate_rerank", {}).get("status") == "fallback_after_empty_ai_selection"
            or evidence.get("ai_degraded")
        ):
            ai_degraded_jobs += 1
        search_reports = evidence.get("search", {}).get("reports", [])
        if isinstance(search_reports, list):
            for report in search_reports:
                if not isinstance(report, dict):
                    continue
                provider = str(report.get("provider") or "unknown")
                provider_status = str(report.get("status") or "unknown")
                provider_status_counts.setdefault(provider, {})
                provider_status_counts[provider][provider_status] = provider_status_counts[provider].get(provider_status, 0) + 1
        if status == "failed" and len(recent_failures) < 10:
            recent_failures.append(
                {
                    "id": str(getattr(job, "id", "") or ""),
                    "title": human_job_title(job),
                    "error": str(getattr(job, "error", "") or "")[:500],
                    "ai_required": bool(evidence.get("ai_required")),
                    "stage": str(evidence.get("stage") or ""),
                    "created_at": created_at.isoformat() if created_at else None,
                }
            )

    alerts = build_supplier_quality_alerts(
        supplier_jobs=supplier_jobs,
        status_counts=status_counts,
        provider_status_counts=provider_status_counts,
        ai_required_failures=ai_required_failures,
        underfilled_terminal_jobs=underfilled,
        average_duration_seconds=round(sum(durations) / len(durations), 2) if durations else 0,
    )
    if ai_degraded_jobs > 0 and not any(a.get("code") == "ai_degraded_jobs" for a in alerts):
        alerts.append({
            "code": "ai_degraded_jobs",
            "level": "warning",
            "message": f"Выявлены задачи с деградацией ИИ ({ai_degraded_jobs})",
        })

    return {
        "window_size": supplier_jobs,
        "status_counts": dict(sorted(status_counts.items())),
        "average_verified_count": round(total_verified / supplier_jobs, 2) if supplier_jobs else 0,
        "average_duration_seconds": round(sum(durations) / len(durations), 2) if durations else 0,
        "underfilled_terminal_jobs": underfilled,
        "ai_required_failures": ai_required_failures,
        "ai_degraded_jobs": ai_degraded_jobs,
        "provider_status_counts": {
            provider: dict(sorted(counts.items()))
            for provider, counts in sorted(provider_status_counts.items())
        },
        "recent_failures": recent_failures,
        "alerts": alerts,
    }


def build_supplier_quality_alerts(
    *,
    supplier_jobs: int,
    status_counts: dict[str, int],
    provider_status_counts: dict[str, dict[str, int]],
    ai_required_failures: int,
    underfilled_terminal_jobs: int,
    average_duration_seconds: float,
) -> list[dict]:
    alerts: list[dict] = []
    failed = status_counts.get("failed", 0)
    if supplier_jobs and failed / supplier_jobs >= 0.2:
        alerts.append({"severity": "critical", "code": "supplier_failure_rate", "message": f"Supplier failure rate is {failed}/{supplier_jobs}."})
    if ai_required_failures:
        alerts.append({"severity": "critical", "code": "ai_required_failures", "message": f"AI-required supplier failures: {ai_required_failures}."})
    if underfilled_terminal_jobs:
        alerts.append({"severity": "warning", "code": "underfilled_reports", "message": f"Underfilled terminal supplier reports: {underfilled_terminal_jobs}."})
    if average_duration_seconds >= 1800:
        alerts.append({"severity": "warning", "code": "slow_supplier_jobs", "message": f"Average supplier job duration is {average_duration_seconds}s."})
    primary_search_has_ok = any(provider_status_counts.get(provider, {}).get("ok", 0) > 0 for provider in ("yandex", "google"))
    for provider, counts in sorted(provider_status_counts.items()):
        total = sum(counts.values())
        if provider in {"tavily", "ddgs"} and primary_search_has_ok:
            continue
        if total and counts.get("ok", 0) == 0:
            alerts.append({"severity": "warning", "code": "search_provider_no_ok", "message": f"{provider} has no ok searches in the current window."})
    return alerts


def _safe_read_job_evidence(job: Job, *, storage_root: Path | None = None) -> dict:
    try:
        return read_job_evidence_payload(job, storage_root=storage_root)
    except HTTPException:
        return {}


@app.post("/api/jobs/manual", dependencies=[Depends(require_admin)])
def create_manual_job(data: ManualJobCreate, db: Session = Depends(db_session)) -> dict:
    if data.mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Unknown job mode")
    raise HTTPException(status_code=400, detail="Upload a document through /api/upload or Telegram before creating a job.")


@app.post("/api/upload", dependencies=[Depends(require_admin)])
async def upload_job(
    telegram_id: str,
    mode: str = "supplier_search",
    files: list[UploadFile] = File(default=[]),
    source_urls: str = Form(default=""),
    db: Session = Depends(db_session),
) -> dict:
    if mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Unknown job mode")
    sources = source_payloads_from_text(source_urls)
    if sources and mode not in {MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS, MODE_EXACT_PRODUCT}:
        raise HTTPException(
            status_code=400,
            detail="Supplier search requires a technical assignment file; procurement numbers and links are accepted for documentation analysis and exact product matching.",
        )
    if not files and not sources:
        raise HTTPException(status_code=400, detail="Upload at least one document or provide a procurement notice number/source URL")
    client, account_error = get_client_by_telegram_id(db, telegram_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    settings = get_or_create_settings(db)
    supplier_search_count = len(files) if mode == MODE_SUPPLIER_SEARCH and len(files) > 1 else 1
    access_error = account_error or client_access_error(
        db,
        client,
        mode,
        incoming_file_count=len(files),
        supplier_search_count=supplier_search_count,
    )
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(status_code=400, detail="Too many files")
    payload = []
    for file in files:
        content = await file.read()
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"{file.filename} is too large")
        payload.append((file.filename or "upload", content))
    if mode == MODE_SUPPLIER_SEARCH and len(payload) > 1:
        jobs = []
        for filename, content in payload:
            job = create_job(
                db,
                client_id=client.id,
                created_by_telegram_id=telegram_id,
                mode=mode,
                title=Path(filename).stem,
                target_suppliers=supplier_target_for_client(settings, client),
                files=[(filename, content)],
                sources=[],
            )
            reserve_job_units(db, client, job)
            enqueue_job(job.id)
            jobs.append(job_to_dict(job))
        return {"batch": True, "count": len(jobs), "jobs": jobs}

    title = Path(files[0].filename).stem if files else source_label(sources[0]["value"])

    # Protection against double-clicks / instant re-submissions (< 5 seconds)
    recent_job = db.query(Job).filter(
        Job.client_id == client.id,
        Job.created_by_telegram_id == telegram_id,
        Job.mode == mode,
        Job.created_at >= datetime.now(timezone.utc) - timedelta(seconds=5),
    ).order_by(Job.created_at.desc()).first()
    
    if recent_job:
        logger.warning("Duplicate job creation request suppressed (double-click within 5s)", recent_job_id=recent_job.id)
        return job_to_dict(recent_job)

    job = create_job(
        db,
        client_id=client.id,
        created_by_telegram_id=telegram_id,
        mode=mode,
        title=title,
        target_suppliers=supplier_target_for_client(settings, client),
        files=payload,
        sources=sources,
    )
    reserve_job_units(db, client, job, supplier_search_count=supplier_search_count)
    enqueue_job(job.id)
    return job_to_dict(job)


@app.post("/api/ai/test", dependencies=[Depends(require_admin)])
async def test_ai(data: AiTestRequest, db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    override = f"{data.provider}:{data.model}" if data.provider and data.model else None
    metadata: dict = {}
    try:
        text = await call_llm(
            settings,
            data.prompt,
            tier="light",
            routing_key=data.routing_key,
            override=override,
            timeout_seconds=45,
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Проверка модели не прошла: {exc}",
        ) from exc
    return {
        "success": True,
        "response": text[:1000],
        "provider_id": metadata.get("provider_id", data.provider or ""),
        "provider_name": metadata.get("provider_name", data.provider or ""),
        "model": metadata.get("model", data.model or ""),
        "attempted_models": metadata.get("attempted_models", []),
    }


def settings_to_public_dict(settings: SystemSettings) -> dict:
    data = settings.to_dict(include_secrets=False)
    data["supplier_search_ui"] = supplier_search_ui(settings)
    return data


def build_bot_analytics(db: Session, *, period_days: int = 30) -> dict:
    now = now_utc()
    cutoff = now - timedelta(days=period_days)
    settings = get_or_create_settings(db)
    all_clients = db.query(Client).all()
    excluded_client_ids = _analytics_excluded_client_ids(all_clients)
    clients = [client for client in all_clients if client.id not in excluded_client_ids]
    accounts = [account for account in db.query(ClientTelegramAccount).all() if account.client_id not in excluded_client_ids]
    period_jobs_raw = (
        db.query(Job)
        .filter(Job.created_at >= cutoff)
        .order_by(Job.created_at.desc())
        .all()
    )
    period_jobs = [job for job in period_jobs_raw if not is_internal_job_record(job) and job.client_id not in excluded_client_ids]
    all_jobs = [job for job in db.query(Job).all() if not is_internal_job_record(job) and job.client_id not in excluded_client_ids]
    billing_period = [
        item
        for item in db.query(BillingTransaction).filter(BillingTransaction.created_at >= cutoff).all()
        if item.client_id not in excluded_client_ids
    ]
    grants_all = [
        item
        for item in db.query(BillingTransaction).filter(BillingTransaction.operation == "grant").all()
        if item.client_id not in excluded_client_ids and (item.created_by or "").strip().lower() != "system"
    ]

    clients_with_jobs = {job.client_id for job in all_jobs if job.client_id}
    period_clients_with_jobs = {job.client_id for job in period_jobs if job.client_id}
    clients_with_grants = {item.client_id for item in grants_all if item.client_id}
    trial_clients = [client for client in clients if client.is_trial]
    trial_clients_with_jobs = [client for client in trial_clients if client.id in clients_with_jobs]
    trial_clients_with_grants = [client for client in trial_clients if client.id in clients_with_grants]
    active_telegram_ids = {
        str(job.created_by_telegram_id or "").strip()
        for job in period_jobs
        if str(job.created_by_telegram_id or "").strip()
    }

    jobs_by_mode = _count_by(period_jobs, lambda job: str(job.mode or ""))
    jobs_by_status = _count_by(period_jobs, lambda job: str(job.status or ""))
    daily = _daily_job_series(period_jobs, now=now, period_days=min(period_days, 45))
    billing_by_kind = _billing_period_summary(billing_period)
    top_clients = _analytics_top_clients(db, clients, period_jobs)
    trial_followups = _analytics_trial_followups(db, trial_clients, all_jobs, clients_with_grants)
    yookassa_ready = _settings_yookassa_ready(settings)

    return {
        "period_days": period_days,
        "generated_at": now.isoformat(),
        "summary": {
            "clients_total": len(clients),
            "active_clients": sum(1 for client in clients if client.is_active),
            "telegram_accounts": len(accounts),
            "trial_clients": len(trial_clients),
            "period_jobs": len(period_jobs),
            "period_active_users": len(active_telegram_ids),
            "period_active_clients": len(period_clients_with_jobs),
            "clients_with_usage": len(clients_with_jobs),
            "clients_with_grants": len(clients_with_grants),
        },
        "funnel": {
            "trial_started": len(trial_clients),
            "trial_used_bot": len(trial_clients_with_jobs),
            "trial_with_grants": len(trial_clients_with_grants),
            "trial_to_grant_percent": _percent(len(trial_clients_with_grants), len(trial_clients)),
            "usage_to_grant_percent": _percent(len(clients_with_grants), len(clients_with_jobs)),
        },
        "jobs": {
            "by_mode": _mode_count_items(jobs_by_mode),
            "by_status": _status_count_items(jobs_by_status),
            "daily": daily,
        },
        "billing": {
            "period": billing_by_kind,
            "payment_provider": settings.payment_provider or "manual",
            "yookassa_ready": yookassa_ready,
        },
        "top_clients": top_clients,
        "trial_followups": trial_followups,
    }


def _count_by(items: list, key_fn) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        key = key_fn(item) or "unknown"
        result[key] = result.get(key, 0) + 1
    return result


def _percent(part: int, total: int) -> int:
    return 0 if total <= 0 else min(100, round(part * 100 / total))


def _mode_count_items(counts: dict[str, int]) -> list[dict]:
    return [
        {"mode": mode, "label": mode_label(mode), "count": count}
        for mode, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _status_count_items(counts: dict[str, int]) -> list[dict]:
    return [
        {"status": status, "label": human_status_label(status), "count": count}
        for status, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def human_status_label(status: str) -> str:
    labels = {
        "pending": "в очереди",
        "running": "в работе",
        "completed": "готово",
        "partial": "частично",
        "needs_review": "нужна проверка",
        "failed": "ошибка",
        "awaiting_customer_confirmation": "ожидает клиента",
        "customer_declined": "отклонено",
        "confirmation_expired": "истёк срок",
        "cancelled": "отменено",
    }
    return labels.get(str(status or ""), str(status or "") or "неизвестно")


def _as_moscow(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MOSCOW_TZ)


def client_display_name(client: Client) -> str:
    return client.name or (f"@{client.username}" if client.username else "") or client.telegram_id or "без имени"


def _daily_job_series(jobs: list[Job], *, now, period_days: int) -> list[dict]:
    start = (_as_moscow(now) - timedelta(days=period_days - 1)).date()
    buckets = {
        (start + timedelta(days=index)).isoformat(): {
            "date": (start + timedelta(days=index)).isoformat(),
            "supplier_search": 0,
            "procurement_report": 0,
            "analysis_and_suppliers": 0,
            "total": 0,
        }
        for index in range(period_days)
    }
    for job in jobs:
        if not job.created_at:
            continue
        key = _as_moscow(job.created_at).date().isoformat()
        if key not in buckets:
            continue
        mode = str(job.mode or "")
        if mode in buckets[key]:
            buckets[key][mode] += 1
        buckets[key]["total"] += 1
    return list(buckets.values())


def _billing_period_summary(transactions: list[BillingTransaction]) -> list[dict]:
    rows: dict[str, dict] = {}
    for item in transactions:
        kind = str(item.kind or "")
        row = rows.setdefault(
            kind,
            {
                "kind": kind,
                "label": billing_kind_label(kind),
                "granted": 0,
                "reserved": 0,
                "charged": 0,
                "released": 0,
                "manual_debited": 0,
                "granted_amount_kopeks": 0,
                "reserved_amount_kopeks": 0,
                "charged_amount_kopeks": 0,
                "released_amount_kopeks": 0,
            },
        )
        units = int(item.units or 0)
        amount = int(item.amount_kopeks or 0)
        if item.operation == "grant":
            row["granted"] += units
            row["granted_amount_kopeks"] += amount
        elif item.operation == "reserve":
            row["reserved"] += units
            row["reserved_amount_kopeks"] += amount
        elif item.operation == "charge":
            row["charged"] += units
            row["charged_amount_kopeks"] += amount
        elif item.operation == "release":
            row["released"] += units
            row["released_amount_kopeks"] += amount
        elif item.operation == "manual_debit":
            row["manual_debited"] += units
    return sorted(rows.values(), key=lambda item: item["label"])


def _analytics_excluded_client_ids(clients: list[Client]) -> set[str]:
    excluded_ids: set[str] = set()
    for client in clients:
        if _analytics_client_is_excluded(client):
            excluded_ids.add(client.id)
    return excluded_ids


def _analytics_client_is_excluded(client: Client) -> bool:
    telegram_id = str(client.telegram_id or "").strip()
    username = normalize_telegram_username(client.username)
    web_emails = {str(user.email or "").strip().lower() for user in getattr(client, "web_users", []) or []}
    telegram_usernames = {normalize_telegram_username(account.username) for account in getattr(client, "telegram_accounts", []) or []}
    telegram_ids = {str(account.telegram_id or "").strip() for account in getattr(client, "telegram_accounts", []) or []}
    return bool(
        web_emails & ANALYTICS_EXCLUDED_WEB_EMAILS
        or username in ANALYTICS_EXCLUDED_TELEGRAM_USERNAMES
        or telegram_id in ANALYTICS_EXCLUDED_TELEGRAM_IDS
        or telegram_usernames & ANALYTICS_EXCLUDED_TELEGRAM_USERNAMES
        or telegram_ids & ANALYTICS_EXCLUDED_TELEGRAM_IDS
    )


def _analytics_top_clients(db: Session, clients: list[Client], period_jobs: list[Job]) -> list[dict]:
    jobs_by_client: dict[str, list[Job]] = {}
    for job in period_jobs:
        if job.client_id:
            jobs_by_client.setdefault(job.client_id, []).append(job)
    client_map = {client.id: client for client in clients}
    rows: list[dict] = []
    for client_id, jobs in jobs_by_client.items():
        client = client_map.get(client_id)
        if not client:
            continue
        rows.append(_analytics_client_row(db, client, jobs))
    return sorted(rows, key=lambda item: (-item["jobs_total"], item["name"]))[:12]


def _analytics_trial_followups(
    db: Session,
    trial_clients: list[Client],
    all_jobs: list[Job],
    clients_with_grants: set[str],
) -> list[dict]:
    jobs_by_client: dict[str, list[Job]] = {}
    for job in all_jobs:
        if job.client_id:
            jobs_by_client.setdefault(job.client_id, []).append(job)
    rows: list[dict] = []
    for client in trial_clients:
        jobs = jobs_by_client.get(client.id, [])
        if not jobs or client.id in clients_with_grants:
            continue
        rows.append(_analytics_client_row(db, client, jobs))
    return sorted(rows, key=lambda item: item["last_job_at"] or "", reverse=True)[:20]


def _analytics_client_row(db: Session, client: Client, jobs: list[Job]) -> dict:
    supplier_jobs = sum(1 for job in jobs if job.mode in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS})
    report_jobs = sum(1 for job in jobs if job.mode in {MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS})
    completed = sum(1 for job in jobs if job.status == "completed")
    failed = sum(1 for job in jobs if job.status == "failed")
    last_job_at = max((job.created_at for job in jobs if job.created_at), default=None)
    balances = client_balance_summary(db, client)
    return {
        "client_id": client.id,
        "name": client_display_name(client),
        "telegram_id": "" if is_pending_telegram_id(client.telegram_id) else client.telegram_id,
        "username": client.username,
        "is_trial": client_uses_trial_access(db, client) if db else bool(client.is_trial),
        "is_active": bool(client.is_active),
        "jobs_total": len(jobs),
        "supplier_jobs": supplier_jobs,
        "report_jobs": report_jobs,
        "completed_jobs": completed,
        "failed_jobs": failed,
        "last_job_at": last_job_at.isoformat() if last_job_at else None,
        "supplier_available": balances["supplier_search"].get("available"),
        "report_available": balances["procurement_report"].get("available"),
    }


def _settings_yookassa_ready(settings: SystemSettings) -> bool:
    return bool(
        str(settings.payment_provider or "").lower() == "yookassa"
        and str(settings.yookassa_shop_id or "").strip()
        and str(settings.yookassa_secret_key or "").strip()
    )


def public_site_payload(db: Session) -> dict:
    settings = get_or_create_settings(db)
    tariffs = [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True)]
    return {
        "site": {
            "name": "TenderLex",
            "domain": "https://tenderlex.ru",
            "headline": "Анализ закупок и поиск поставщиков на сайте и в Telegram",
            "description": (
                "TenderLex анализирует закупочную документацию, помогает увидеть риски и собирает "
                "поставщиков с email, телефонами, сайтами, страницами контактов и комментариями. "
                "Новые пользователи могут попробовать оба сценария на сайте или в Telegram."
            ),
        },
        "bot": {
            "telegram": settings.bot_telegram,
            "telegram_url": telegram_public_url(settings.bot_telegram),
        },
        "contacts": {
            "email": settings.contact_email,
            "phone": None,
            "phone_url": None,
            "telegram": settings.contact_telegram,
            "telegram_url": telegram_public_url(settings.contact_telegram),
            "max": None,
            "max_url": None,
            "website": settings.contact_website,
            "website_url": website_public_url(settings.contact_website),
        },
        "trial": {
            "enabled": bool(settings.trial_enabled),
            "supplier_search_limit": max(0, int(settings.trial_supplier_search_limit or 0)),
            "procurement_report_limit": max(0, int(settings.trial_procurement_report_limit or 0)),
            "file_limit": max(0, int(settings.trial_file_limit or 0)),
        },
        "tariffs": tariffs,
        "tariff_groups": {
            "exact_product": [item for item in tariffs if item["kind"] == "exact_product"],
            "supplier_search": [item for item in tariffs if item["kind"] == "supplier_search"],
            "procurement_report": [item for item in tariffs if item["kind"] == "procurement_report"],
            "supplier_search_extra": [item for item in tariffs if item["kind"] == "supplier_search_extra"],
        },
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def tariff_to_public_dict(package: TariffPackage) -> dict:
    return {
        "id": package.id,
        "kind": package.kind,
        "label": billing_kind_label(package.kind),
        "name": package.name,
        "units": package.units,
        "price_kopeks": package.price_kopeks,
        "price_rub": round(package.price_kopeks / 100, 2),
        "description": package.description,
        "sort_order": package.sort_order,
    }


def telegram_public_url(value: str) -> str:
    username = str(value or "").strip()
    if not username:
        return ""
    if username.startswith("http://") or username.startswith("https://"):
        return username
    username = username.lstrip("@")
    return f"https://t.me/{username}" if username else ""


def website_public_url(value: str) -> str:
    website = str(value or "").strip()
    if not website:
        return ""
    if website.startswith("http://") or website.startswith("https://"):
        return website
    return f"https://{website}"


def max_public_url(value: str) -> str:
    contact = str(value or "").strip()
    if not contact:
        return ""
    if contact.startswith(("http://", "https://")):
        return contact
    if contact.startswith("max.ru/"):
        return f"https://{contact}"
    handle = contact.lstrip("@").strip("/")
    if re.fullmatch(r"(?=.*[A-Za-z])[A-Za-z0-9_.-]{3,80}", handle):
        return f"https://max.ru/{handle}"
    return ""


def customer_session_payload(db: Session, user: WebUser, *, csrf_token: str = "", authenticated: bool = True) -> dict:
    settings = get_or_create_settings(db)
    return {
        "authenticated": authenticated,
        "csrf_token": csrf_token,
        "csrf_header": CSRF_HEADER,
        "user": customer_user_to_dict(db, user),
        "balance": client_usage_summary(db, user.client),
        "limits": {
            "max_upload_mb": int(settings.max_upload_mb or 50),
            "max_files_per_batch": int(settings.max_files_per_batch or 20),
            "default_supplier_target": supplier_target_for_client(settings, user.client),
        },
        "trial": {
            "enabled": bool(settings.trial_enabled),
            "supplier_search_limit": max(0, int(settings.trial_supplier_search_limit or 0)),
            "procurement_report_limit": max(0, int(settings.trial_procurement_report_limit or 0)),
            "file_limit": max(0, int(settings.trial_file_limit or 0)),
        },
        "tariffs": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True)],
        "tariff_groups": {
            "exact_product": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True) if item.kind == "exact_product"],
            "supplier_search": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True) if item.kind == "supplier_search"],
            "procurement_report": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True) if item.kind == "procurement_report"],
            "supplier_search_extra": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True) if item.kind == "supplier_search_extra"],
        },
        "contacts": {
            "email": settings.contact_email,
            "phone": None,
            "phone_url": None,
            "telegram": settings.contact_telegram,
            "telegram_url": telegram_public_url(settings.contact_telegram),
            "max": getattr(settings, "contact_max", None) or None,
            "max_url": max_public_url(getattr(settings, "contact_max_link", "") or getattr(settings, "contact_max", "")),
        },
        "payment": {
            "provider": settings.payment_provider or "manual",
            "instructions": settings.payment_instructions or "",
            "yookassa_ready": _settings_yookassa_ready(settings),
        },
    }


def customer_user_to_dict(db: Session, user: WebUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_active": bool(user.is_active),
        "is_email_verified": bool(user.is_email_verified),
        "client_id": user.client_id,
        "is_trial": client_uses_trial_access(db, user.client) if user.client else False,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def customer_billing_transaction_to_dict(transaction: BillingTransaction) -> dict:
    op = str(transaction.operation or "")
    amount_kopeks = int(transaction.amount_kopeks or 0)
    amount_rub = round(amount_kopeks / 100, 2)

    job = transaction.job
    if job:
        kind_label = mode_label(str(job.mode or "")) if getattr(job, "mode", None) else billing_kind_label(str(transaction.kind or ""))
        subject = _customer_job_subject_from_evidence(job) or _clean_customer_job_subject(str(job.title or ""))
        if subject and subject.lower() not in {
            "подбор товара и аналогов",
            "поиск поставщиков",
            "анализ документации",
            "анализ + поиск",
            "точный товар и аналоги",
        }:
            title = f"ТЗ: {subject}" if not subject.startswith("ТЗ:") else subject
        else:
            title = ""
    else:
        kind_label = billing_kind_label(str(transaction.kind or ""))
        raw_note = str(transaction.note or "").strip()
        if raw_note.lower() in {"пополнение баланса", "резерв перед запуском задачи", "результат отправлен клиенту"}:
            title = ""
        else:
            title = raw_note

    if op == OP_CHARGE:
        op_label = "Списание"
    elif op == OP_GRANT:
        op_label = "Пополнение"
    elif op == OP_RELEASE:
        op_label = "Возврат"
    elif op == OP_MANUAL_DEBIT:
        op_label = "Корректировка"
    elif op == OP_RESERVE:
        op_label = "Резерв"
    else:
        op_label = operation_label(op)

    return {
        "id": transaction.id,
        "job_id": transaction.job_id,
        "operation": op,
        "operation_label": op_label,
        "kind": str(transaction.kind or ""),
        "kind_label": kind_label,
        "title": title,
        "note": str(transaction.note or ""),
        "units": int(transaction.units or 0),
        "amount_kopeks": amount_kopeks,
        "amount_rub": amount_rub,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
    }


def customer_job_to_dict(job: Job, include_files: bool = False, *, db: Session | None = None) -> dict:
    supplier_units, report_units = requested_function_units(job.mode)
    result_files = customer_job_result_files(job)
    confirmation_kind = str(getattr(job, "confirmation_kind", "") or "")
    result_offer = result_offer_to_dict(db, job) if confirmation_kind else None
    status_lbl = human_status_label(job.status)
    if job.status == "failed" and getattr(job, "supplier_search_policy", "") == SUPPLIER_POLICY_MINPROM_ONLY and ("реестр" in (job.error or "").lower() or "реестр" in (job.message or "").lower()):
        status_lbl = "нет в реестре"
    data = {
        "id": job.id,
        "client_id": job.client_id,
        "mode": job.mode,
        "mode_label": mode_label(job.mode),
        "supplier_search_policy": getattr(job, "supplier_search_policy", SUPPLIER_POLICY_NORMAL),
        "supplier_search_run_type": getattr(job, "supplier_search_run_type", "initial"),
        "status": job.status,
        "status_label": status_lbl,
        "progress": job.progress,
        "message": job.message,
        "title": job.title,
        "human_title": human_job_title(job),
        "supplier_units": supplier_units,
        "procurement_report_units": report_units,
        "target_suppliers": job.target_suppliers,
        "verified_count": job.verified_count,
        "file_count": job.file_count,
        "has_result": bool(result_files),
        "can_download": bool(result_files) and job.status not in {STATUS_AWAITING_CUSTOMER_CONFIRMATION, STATUS_CUSTOMER_DECLINED},
        "can_cancel": job.status in {"pending", "running"},
        "can_find_more_suppliers": job_can_find_more_suppliers(job),
        "can_start_supplier_search": job_can_start_supplier_search(job),
        "exact_product_summary": _customer_exact_product_summary(job) if job_can_start_supplier_search(job) else None,
        "result_files": result_files,
        "result_offer": result_offer,
        "awaiting_customer_confirmation": job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION,
        "error": job.error,
        "yandex_requests_count": getattr(job, "yandex_requests_count", 0) or 0,
        "yandex_cost_rub": getattr(job, "yandex_cost_rub", 0.0) or 0.0,
        "yandex_cost_label": f"{(getattr(job, 'yandex_cost_rub', 0.0) or 0.0):.2f} ₽",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    exclusions_payload = read_supplier_exclusions_payload(job)
    if exclusions_payload or getattr(job, "supplier_search_run_type", "") == SUPPLIER_RUN_ADDITIONAL:
        prior_count = int(exclusions_payload.get("prior_verified_count") if exclusions_payload.get("prior_verified_count") is not None else len(exclusions_payload.get("suppliers", [])))
        data["prior_verified_count"] = prior_count
        data["cumulative_verified_count"] = prior_count + int(job.verified_count or 0)
    if include_files:
        data["files"] = [file_to_dict(item) for item in job.files]
        data["sources"] = [source_to_dict(item) for item in job.sources]
    return data


def customer_job_result_files(job: Job) -> list[dict]:
    if getattr(job, "status", "") in {"cancelled", STATUS_AWAITING_CUSTOMER_CONFIRMATION, STATUS_CUSTOMER_DECLINED}:
        return []
    result: list[dict] = []
    for item in package_job_output_items(job):
        path = Path(str(item.get("path") or ""))
        result.append(
            {
                "kind": str(item.get("kind") or path.stem),
                "label": _customer_result_file_label(str(item.get("kind") or ""), str(item.get("label") or "")),
                "filename": path.name,
            }
        )
    return result


def _customer_result_file_label(kind: str, label: str = "") -> str:
    if label:
        return label
    if kind == "analysis":
        return "Анализ"
    if kind == "suppliers":
        return "Поставщики"
    if kind == "quote_request":
        return "Запрос КП"
    if kind in {"exact_product", "exact_product_table", "exact_product_spec"}:
        return "Подбор товара и аналоги"
    return "Файл"


async def create_customer_job_api(
    *,
    mode: str,
    supplier_search_policy: str = SUPPLIER_POLICY_NORMAL,
    text: str = "",
    source_urls: str = "",
    target_suppliers: int = 0,
    files: list[UploadFile] | None = None,
    context: WebAuthContext,
    db: Session,
) -> dict:
    if mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Неизвестный режим обработки.")
    if not context.user.is_email_verified:
        raise HTTPException(status_code=403, detail="Подтвердите email, чтобы запускать задачи.")
    normalized_policy = _normalize_supplier_search_policy_for_job(mode, supplier_search_policy)
    settings = get_or_create_settings(db)
    sources = source_payloads_from_text(source_urls)
    if sources and mode == MODE_SUPPLIER_SEARCH:
        raise HTTPException(
            status_code=400,
            detail="Для поиска поставщиков отправьте файл или текст ТЗ. Номер извещения и ссылку используйте в анализе закупки.",
        )
    payload = await _customer_upload_payload(files or [], settings)
    text_value = str(text or "").strip()
    if text_value:
        payload.append(("technical_assignment.txt", text_value.encode("utf-8")))
    if not payload and not sources:
        if mode == MODE_SUPPLIER_SEARCH:
            raise HTTPException(status_code=400, detail="Приложите одно или несколько ТЗ.")
        raise HTTPException(status_code=400, detail="Добавьте документы закупки, номер извещения или ссылку.")
    if len(payload) > int(settings.max_files_per_batch or 20):
        raise HTTPException(status_code=400, detail="Слишком много файлов в одной задаче.")

    client = context.user.client
    safe_target = supplier_target_for_client(settings, client)
    supplier_specs = _customer_supplier_job_specs(mode, payload)
    supplier_search_count = len(supplier_specs) if supplier_specs else 1
    access_error = client_access_error(
        db,
        client,
        mode,
        incoming_file_count=len(payload),
        supplier_search_count=supplier_search_count,
    )
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    try:
        if supplier_specs and len(supplier_specs) > 1:
            jobs: list[Job] = []
            for title, job_files in supplier_specs:
                job = create_job(
                    db,
                    client_id=client.id,
                    created_by_telegram_id=f"web:{context.user.id}",
                    mode=MODE_SUPPLIER_SEARCH,
                    title=title,
                    target_suppliers=safe_target,
                    files=job_files,
                    sources=[],
                    supplier_search_policy=normalized_policy,
                )
                reserve_job_units(db, client, job)
                enqueue_job(job.id)
                jobs.append(job)
            return {"batch": True, "count": len(jobs), "jobs": [customer_job_to_dict(job) for job in jobs]}

        title = _customer_initial_job_title(mode, payload, sources)
        job = create_job(
            db,
            client_id=client.id,
            created_by_telegram_id=f"web:{context.user.id}",
            mode=mode,
            title=title,
            target_suppliers=safe_target,
            files=payload,
            sources=sources,
            supplier_search_policy=normalized_policy,
        )
        reserve_job_units(db, client, job, supplier_search_count=supplier_search_count)
        enqueue_job(job.id)
    except BillingError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"batch": False, "count": 1, "job": customer_job_to_dict(job)}


async def _customer_upload_payload(files: list[UploadFile], settings: SystemSettings) -> list[tuple[str, bytes]]:
    if len(files) > int(settings.max_files_per_batch or 20):
        raise HTTPException(status_code=400, detail="Слишком много файлов в одной задаче.")
    payload: list[tuple[str, bytes]] = []
    max_bytes = int(settings.max_upload_mb or 50) * 1024 * 1024
    for file in files:
        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail=f"{file.filename or 'Файл'} слишком большой.")
        if not content:
            continue
        payload.append((file.filename or "upload", content))
    return payload


def _customer_supplier_job_specs(mode: str, payload: list[tuple[str, bytes]]) -> list[tuple[str, list[tuple[str, bytes]]]]:
    if mode != MODE_SUPPLIER_SEARCH:
        return []
    return [(_clean_customer_job_subject(Path(filename).stem) or "ТЗ", [(filename, content)]) for filename, content in payload]


def _normalize_supplier_search_policy_for_job(mode: str, policy: str) -> str:
    if mode not in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}:
        return SUPPLIER_POLICY_NORMAL
    normalized = str(policy or "").strip().lower()
    return normalized if normalized in VALID_SUPPLIER_SEARCH_POLICIES else SUPPLIER_POLICY_NORMAL


def _customer_initial_job_title(mode: str, payload: list[tuple[str, bytes]], sources: list[dict]) -> str:
    if payload:
        title = _clean_customer_job_subject(Path(payload[0][0]).stem)
        if title:
            return title[:120]
    if sources:
        return source_label(sources[0]["value"])[:120]
    return mode_label(mode)


def _customer_job_or_404(db: Session, job_id: str, context: WebAuthContext) -> Job:
    job = db.get(Job, job_id)
    if not job or job.client_id != context.user.client_id:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    return job


def download_customer_job_api(job_id: str, *, context: WebAuthContext, db: Session):
    job = _customer_job_or_404(db, job_id, context)
    if job.status in {STATUS_CONFIRMATION_EXPIRED, STATUS_DELIVERY_EXPIRED}:
        raise HTTPException(status_code=410, detail="Срок действия предложения или выдачи результата истёк.")
    if job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтвердите неполный отчёт перед скачиванием.")
    output = package_job_outputs(job)
    if not output or not output.exists():
        items = package_job_output_items(job)
        if items:
            output = Path(str(items[0].get("path") or ""))
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Файл результата не найден.")
    if job.confirmation_kind and job.confirmation_outcome == "accepted" and job.offer_delivery_outcome != "delivered":
        claim_token = claim_job_result_offer_delivery(db, job, channel="web")
        complete_job_result_offer_delivery(db, job, claim_token, channel="web")
    else:
        charge_job_reservation(db, job)
    return FileResponse(output, filename=output.name)


def download_customer_job_file_api(job_id: str, file_kind: str, *, context: WebAuthContext, db: Session):
    job = _customer_job_or_404(db, job_id, context)
    if job.status in {STATUS_CONFIRMATION_EXPIRED, STATUS_DELIVERY_EXPIRED}:
        raise HTTPException(status_code=410, detail="Срок действия предложения или выдачи результата истёк.")
    if job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтвердите неполный отчёт перед скачиванием.")
    normalized_kind = str(file_kind or "").strip()
    output = None
    billing_kind = None
    for item in package_job_output_items(job):
        if str(item.get("kind") or "") == normalized_kind:
            output = Path(str(item.get("path") or ""))
            billing_kind = str(item.get("billing_kind") or "")
            break
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Файл результата не найден.")
    if job.confirmation_kind and job.confirmation_outcome == "accepted" and job.offer_delivery_outcome != "delivered":
        claim_token = claim_job_result_offer_delivery(db, job, channel="web")
        kinds = [billing_kind] if billing_kind else None
        complete_job_result_offer_delivery(db, job, claim_token, billing_kinds=kinds, channel="web")
    elif billing_kind:
        charge_job_kind_reservation(db, job, billing_kind)
    else:
        charge_job_reservation(db, job)
    return FileResponse(output, filename=output.name)


def cancel_customer_job_api(job_id: str, *, context: WebAuthContext, db: Session) -> dict:
    job = _customer_job_or_404(db, job_id, context)
    if job.status not in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="Эту задачу уже нельзя отменить.")
    release_job_reservation(db, job, note="Резерв возвращён: задача отменена клиентом")
    job.status = "cancelled"
    job.progress = 100
    job.error = ""
    job.message = "Задача отменена клиентом"
    job.completed_at = now_utc()
    job.updated_at = now_utc()
    db.commit()
    cancel_running_job(job.id)
    return {"success": True, "job": customer_job_to_dict(job)}


def customer_quote_request_api(job_id: str, *, context: WebAuthContext, db: Session) -> dict:
    job = _customer_job_or_404(db, job_id, context)
    if job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтвердите неполный отчёт перед открытием запроса КП.")
    item = _quote_request_output_item(job)
    content_path = Path(str(item.get("content_path") or ""))
    if not content_path.exists():
        raise HTTPException(status_code=404, detail="Текст запроса КП не найден.")
    content = content_path.read_text(encoding="utf-8")
    output = Path(str(item.get("path") or ""))
    filename = output.name if output.name else "Запрос КП.docx"
    return {"content": content, "filename": filename}


def download_customer_quote_request_docx_api(
    job_id: str,
    *,
    content: str,
    filename: str,
    context: WebAuthContext,
    db: Session,
):
    job = _customer_job_or_404(db, job_id, context)
    if job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтвердите неполный отчёт перед скачиванием.")
    _quote_request_output_item(job)
    markdown = str(content or "").strip()
    if not markdown:
        raise HTTPException(status_code=400, detail="Текст запроса КП пустой.")
    if len(markdown) > 300_000:
        raise HTTPException(status_code=413, detail="Текст запроса КП слишком большой.")
    safe_filename = _safe_docx_filename(filename, fallback="Запрос КП.docx")
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / safe_filename
        write_quote_request_docx(out_path, markdown, title="Запрос КП")
        payload = out_path.read_bytes()
    charge_job_reservation(db, job)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe_filename, safe='')}"},
    )


def _quote_request_output_item(job: Job) -> dict:
    for item in package_job_output_items(job):
        if str(item.get("kind") or "") == "quote_request":
            return item
    raise HTTPException(status_code=404, detail="Запрос КП для этой задачи не найден.")


def _safe_docx_filename(value: str, *, fallback: str) -> str:
    name = Path(str(value or fallback)).name.strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip(" .") or fallback
    if not name.lower().endswith(".docx"):
        name = f"{name}.docx"
    if len(name.encode("utf-8")) <= 180:
        return name
    stem = Path(name).stem.encode("utf-8")[:170].decode("utf-8", errors="ignore").rstrip(" ._-")
    return f"{stem or 'Запрос КП'}.docx"


def accept_customer_partial_job_api(job_id: str, *, context: WebAuthContext, db: Session):
    job = _customer_job_or_404(db, job_id, context)
    if job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтверждение уже не актуально.")
    if job.confirmation_kind:
        job = accept_job_result_offer(db, job, channel="web")
    else:
        job.status = "partial"
        job.message = "Клиент принял неполный отчёт"
        job.error = ""
        job.updated_at = now_utc()
        if job.completed_at is None:
            job.completed_at = now_utc()
        db.commit()
    return {"success": True, "job": customer_job_to_dict(job, db=db)}


def decline_customer_partial_job_api(job_id: str, *, context: WebAuthContext, db: Session) -> dict:
    job = _customer_job_or_404(db, job_id, context)
    if job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтверждение уже не актуально.")
    if job.confirmation_kind:
        job = decline_job_result_offer(db, job, channel="web")
    else:
        release_job_reservation(db, job, note="Резерв возвращён: клиент сайта отказался от неполного отчёта")
        job.status = STATUS_CUSTOMER_DECLINED
        job.message = "Клиент отказался от неполного отчёта"
        job.error = ""
        job.completed_at = now_utc()
        job.updated_at = now_utc()
        db.commit()
    return {"success": True, "job": customer_job_to_dict(job, db=db)}


FIND_MORE_SUPPLIER_STATUSES = {"completed", "partial", "needs_review"}


def create_additional_supplier_search_api(
    job_id: str,
    *,
    context: WebAuthContext,
    db: Session,
    additional_prompt: str = "",
) -> dict:
    if not context.user.is_email_verified:
        raise HTTPException(status_code=403, detail="Подтвердите email, чтобы запускать задачи.")
    original_job = _customer_job_or_404(db, job_id, context)
    job = create_additional_supplier_search_for_client(
        db,
        client=context.user.client,
        original_job=original_job,
        created_by_telegram_id=f"web:{context.user.id}",
        additional_prompt=additional_prompt,
    )

    return {
        "success": True,
        "message": "Запущен дополнительный поиск поставщиков. Он резервирует стоимость добора и исключает уже найденные компании.",
        "job": customer_job_to_dict(job),
    }


def _additional_supplier_target(settings: SystemSettings, client: Client, original_job: Job) -> int:
    base_target = int(original_job.target_suppliers or 0) or supplier_target_for_client(settings, client)
    verified = int(original_job.verified_count or 0)
    if base_target > verified and verified > 0:
        return max(1, base_target - verified)
    return max(1, base_target)


def _cumulative_prior_verified_count(job: Job) -> int:
    prev_payload = read_supplier_exclusions_payload(job)
    prev_prior = int(prev_payload.get("prior_verified_count") or 0)
    return prev_prior + int(job.verified_count or 0)


def create_additional_supplier_search_for_client(
    db: Session,
    *,
    client: Client,
    original_job: Job,
    created_by_telegram_id: str,
    additional_prompt: str = "",
) -> Job:
    if original_job.client_id != client.id:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    if not job_can_find_more_suppliers(original_job):
        raise HTTPException(status_code=409, detail="Дополнительный поиск доступен только после готового поиска поставщиков.")
    excluded_suppliers = _supplier_exclusions_from_job(original_job)
    if not excluded_suppliers:
        raise HTTPException(status_code=409, detail="Не нашёл поставщиков исходной задачи для исключения из нового поиска.")
    input_files = _repeat_supplier_search_input_files(original_job)
    if not input_files:
        raise HTTPException(status_code=409, detail="Не нашёл исходное ТЗ или контекст для дополнительного поиска.")

    settings = get_or_create_settings(db)
    access_error = client_access_error(
        db,
        client,
        MODE_SUPPLIER_SEARCH,
        incoming_file_count=len(input_files),
        supplier_search_count=1,
        supplier_search_run_type=SUPPLIER_RUN_ADDITIONAL,
    )
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    target_suppliers = _additional_supplier_target(settings, client, original_job)
    job: Job | None = None
    try:
        job = create_job(
            db,
            client_id=client.id,
            created_by_telegram_id=created_by_telegram_id,
            mode=MODE_SUPPLIER_SEARCH,
            title=_additional_supplier_search_title(original_job),
            target_suppliers=target_suppliers,
            files=input_files,
            sources=[],
            supplier_search_policy=_normalize_supplier_search_policy_for_job(
                MODE_SUPPLIER_SEARCH,
                getattr(original_job, "supplier_search_policy", SUPPLIER_POLICY_NORMAL),
            ),
            supplier_search_run_type=SUPPLIER_RUN_ADDITIONAL,
        )
        reserve_job_units(db, client, job, supplier_search_count=1)
        prior_verified_count = _cumulative_prior_verified_count(original_job)
        write_supplier_exclusions(
            job,
            previous_job_id=original_job.id,
            suppliers=excluded_suppliers,
            prior_verified_count=prior_verified_count,
        )

        unreviewed_candidates: list[dict] = []
        cached_profile: dict = {}
        executed_queries: list[str] = []
        wave_index = 2
        try:
            parent_evidence = read_job_evidence_payload(original_job)
            if isinstance(parent_evidence, dict):
                s_ev = parent_evidence.get("supplier_search") if isinstance(parent_evidence.get("supplier_search"), dict) else parent_evidence
                unreviewed_candidates = s_ev.get("unreviewed_candidates", [])
                cached_profile = s_ev.get("procurement_profile", {})
                executed_queries = s_ev.get("executed_queries", [])
                prev_wave = int(s_ev.get("wave_index") or 1)
                wave_index = prev_wave + 1
        except Exception:
            pass

        write_dobor_context(
            job,
            previous_job_id=original_job.id,
            unreviewed_candidates=unreviewed_candidates,
            cached_procurement_profile=cached_profile,
            executed_queries=executed_queries,
            additional_prompt=additional_prompt,
            wave_index=wave_index,
        )
        enqueue_job(job.id)
    except BillingError as exc:
        if job:
            _discard_created_job(db, job)
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        if job:
            _discard_created_job(db, job)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return job


def job_can_find_more_suppliers(job: Job | object) -> bool:
    return bool(
        str(getattr(job, "mode", "") or "") in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}
        and str(getattr(job, "status", "") or "") in FIND_MORE_SUPPLIER_STATUSES
        and int(getattr(job, "verified_count", 0) or 0) > 0
    )


def _discard_created_job(db: Session, job: Job) -> None:
    shutil.rmtree(config.storage_path / "jobs" / job.id, ignore_errors=True)
    db.delete(job)
    db.commit()


def _additional_supplier_search_title(job: Job) -> str:
    subject = _customer_job_subject_from_evidence(job) or _clean_customer_job_subject(job.title) or human_job_title(job)
    return _ellipsize_customer_title(f"Добор поставщиков: {subject}", limit=120)


def _repeat_supplier_search_input_files(job: Job) -> list[tuple[str, bytes]]:
    payload: list[tuple[str, bytes]] = []
    for file in getattr(job, "files", []) or []:
        path = Path(str(getattr(file, "stored_path", "") or ""))
        if path.exists() and path.is_file():
            payload.append((str(getattr(file, "original_filename", "") or path.name), path.read_bytes()))
    for source in getattr(job, "sources", []) or []:
        path = Path(str(getattr(source, "context_path", "") or ""))
        if path.exists() and path.is_file():
            label = _clean_customer_job_subject(getattr(source, "label", "") or getattr(source, "kind", "")) or "source"
            payload.append((f"{label[:60]}_context.txt", path.read_bytes()))
    if payload:
        return payload
    context = _supplier_context_from_job_evidence(job)
    return [("previous_supplier_context.txt", context.encode("utf-8"))] if context else []


def job_can_start_supplier_search(job: Job | object) -> bool:
    return bool(
        str(getattr(job, "mode", "") or "") == MODE_EXACT_PRODUCT
        and str(getattr(job, "status", "") or "") in {"completed", "done"}
        and not getattr(job, "error", "")
    )


def _clean_brand_model_label(mfr: str, brand: str, model: str) -> str:
    mfr = str(mfr or "").strip()
    brand = str(brand or "").strip()
    model = str(model or "").strip()

    generic_mfr = {
        "не указан", "нет данных", "отечественный производитель", "россия", "рф",
        "отечественный производитель (россия)", "не определен", "не требуется"
    }
    if mfr.lower() in generic_mfr:
        mfr = ""

    seen_significant_words: set[str] = set()
    result_words: list[str] = []
    ignore_duplicate_check = {"dn", "pn", "ру", "ду", "мм", "см", "м", "в", "вт", "квт", "а", "v", "w", "1", "2", "3", "no", "тип"}

    for part in [mfr, brand, model]:
        if not part:
            continue
        for word in part.split():
            clean_w = word.strip(" ,;.:\"'()[]")
            w_lower = clean_w.lower()
            if not clean_w:
                continue
            if w_lower in seen_significant_words and w_lower not in ignore_duplicate_check:
                if len(result_words) > 0 and result_words[-1].lower() == w_lower:
                    continue
                if any(rw.lower() == w_lower for rw in result_words):
                    continue
            result_words.append(word)
            if len(w_lower) >= 3 and w_lower not in ignore_duplicate_check:
                seen_significant_words.add(w_lower)

    res = " ".join(result_words).strip()
    return res or model or brand or mfr


def _customer_exact_product_summary(job: Job) -> dict | None:
    try:
        evidence = read_job_evidence_payload(job)
        if not isinstance(evidence, dict):
            return None
        rep = evidence.get("exact_product_report")
        if not isinstance(rep, dict):
            return None
        positions = rep.get("positions", [])
        if not positions or not isinstance(positions, list):
            return None
        first_pos = positions[0] if isinstance(positions[0], dict) else {}
        brand = str(first_pos.get("identified_brand") or "").strip()
        model = str(first_pos.get("identified_model") or "").strip()
        mfr = str(first_pos.get("manufacturer") or "").strip()
        name_tz = str(first_pos.get("name_in_tz") or "").strip()
        primary_str = _clean_brand_model_label(mfr, brand, model) or name_tz

        alts: list[str] = []
        for a in first_pos.get("alternative_brands", []) or []:
            if isinstance(a, dict):
                a_b = str(a.get("brand") or "").strip()
                a_m = str(a.get("model") or "").strip()
                a_mfr = str(a.get("manufacturer") or "").strip()
                alt_str = _clean_brand_model_label(a_mfr, a_b, a_m)
                if alt_str and alt_str not in alts:
                    alts.append(alt_str)
        return {
            "primary_product": primary_str,
            "brand": brand,
            "model": model,
            "manufacturer": mfr,
            "name_in_tz": name_tz,
            "alternatives": alts,
            "total_positions": len(positions),
        }
    except Exception:
        return None


def _build_exact_product_supplier_selection_text(
    exact_report: dict,
    include_alternatives: bool = True,
    additional_prompt: str = "",
    job_title: str = "",
) -> str:
    lines = [
        "=== ВЫЯВЛЕННЫЙ ТОЧНЫЙ ТОВАР И АНАЛОГИ (ПОДБОР TENDERLEX) ===",
        "Инструкция для ИИ-поиска поставщиков:",
        "По данному техническому заданию был выполнен детальный подбор товаров, материалов и эквивалентов.",
        "Необходимо найти прямых производителей, официальных дистрибьюторов, дилеров и оптовых поставщиков для следующей номенклатуры:",
        "",
    ]
    if job_title:
        lines.append(f"Предмет закупки: {job_title}\n")
    positions = exact_report.get("positions", [])
    if isinstance(positions, list) and positions:
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            p_no = pos.get("position_no", 1)
            name_tz = pos.get("name_in_tz", "")
            brand = pos.get("identified_brand", "")
            model = pos.get("identified_model", "")
            mfr = pos.get("manufacturer", "")
            lines.append(f"Позиция {p_no}: {name_tz}")
            conf = float(pos.get("confidence", 0.90) or 0.90)
            identified = _clean_brand_model_label(mfr, brand, model)
            if identified:
                if conf >= 0.60:
                    lines.append(f"- Выявленный точный товар: {identified}")
                else:
                    lines.append(f"- Проверенная модель {identified} имеет отклонения от ТЗ (соответствие {int(conf*100)}%). Искать поставщиков по техническим характеристикам позиции: {name_tz}")
            alts = pos.get("alternative_brands", [])
            if include_alternatives and isinstance(alts, list) and alts:
                alt_lines = []
                for a in alts:
                    if isinstance(a, dict):
                        a_conf = float(a.get("confidence", 0.90) or 0.90)
                        if a_conf >= 0.60:
                            a_b = a.get("brand", "")
                            a_m = a.get("model", "")
                            a_mfr = a.get("manufacturer", "")
                            item_str = _clean_brand_model_label(a_mfr, a_b, a_m)
                            if item_str:
                                alt_lines.append(item_str)
                if alt_lines:
                    lines.append(f"- Допустимые проверенные аналоги: {'; '.join(alt_lines)}")
            lines.append("")
    else:
        summary = str(exact_report.get("summary") or "").strip()
        if summary:
            lines.append(f"Результаты подбора: {summary}\n")
    if additional_prompt:
        lines.append(f"ТРЕБОВАНИЯ И ПОЖЕЛАНИЯ КЛИЕНТА К ПОИСКУ ПОСТАВЩИКОВ:\n{additional_prompt.strip()}\n")
    lines.append("=== ИСХОДНОЕ ТЕХНИЧЕСКОЕ ЗАДАНИЕ И ТРЕБОВАНИЯ СМ. ВО ВЛОЖЕНИЯХ ===")
    return "\n".join(lines)


def create_supplier_search_from_exact_product(
    db: Session,
    *,
    client: Client,
    original_job: Job,
    created_by_telegram_id: str,
    supplier_search_policy: str = SUPPLIER_POLICY_NORMAL,
    include_alternatives: bool = True,
    additional_prompt: str = "",
) -> Job:
    if original_job.client_id != client.id:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    if str(getattr(original_job, "mode", "") or "") != MODE_EXACT_PRODUCT:
        raise HTTPException(status_code=409, detail="Поиск поставщиков можно запустить только из задачи подбора товара.")
    if str(getattr(original_job, "status", "") or "") not in {"completed", "done"}:
        raise HTTPException(status_code=409, detail="Дождитесь завершения подбора товара перед поиском поставщиков.")

    input_files = _repeat_supplier_search_input_files(original_job)
    settings = get_or_create_settings(db)
    access_error = client_access_error(
        db,
        client,
        MODE_SUPPLIER_SEARCH,
        incoming_file_count=max(1, len(input_files)),
        supplier_search_count=1,
    )
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    exact_report = {}
    try:
        evidence = read_job_evidence_payload(original_job)
        if isinstance(evidence, dict):
            exact_report = evidence.get("exact_product_report") or {}
    except Exception:
        pass

    selection_text = _build_exact_product_supplier_selection_text(
        exact_report=exact_report,
        include_alternatives=include_alternatives,
        additional_prompt=additional_prompt,
        job_title=original_job.title or "",
    )

    combined_files = [("podbor_tovara_i_analogi_rezultat.txt", selection_text.encode("utf-8")), *input_files]
    subject = _customer_job_subject_from_evidence(original_job) or _clean_customer_job_subject(original_job.title) or human_job_title(original_job)
    title = _ellipsize_customer_title(f"Поставщики: {subject}", limit=120)
    target_suppliers = supplier_target_for_client(settings, client)
    normalized_policy = _normalize_supplier_search_policy_for_job(MODE_SUPPLIER_SEARCH, supplier_search_policy)

    job: Job | None = None
    try:
        job = create_job(
            db,
            client_id=client.id,
            created_by_telegram_id=created_by_telegram_id,
            mode=MODE_SUPPLIER_SEARCH,
            title=title,
            target_suppliers=target_suppliers,
            files=combined_files,
            sources=[],
            supplier_search_policy=normalized_policy,
            supplier_search_run_type="initial",
        )
        reserve_job_units(db, client, job, supplier_search_count=1)
        enqueue_job(job.id)
    except BillingError as exc:
        if job:
            _discard_created_job(db, job)
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        if job:
            _discard_created_job(db, job)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return job


def _supplier_context_from_job_evidence(job: Job) -> str:
    try:
        evidence = read_job_evidence_payload(job)
    except HTTPException:
        return ""
    supplier_evidence = evidence.get("supplier_search") if isinstance(evidence.get("supplier_search"), dict) else evidence
    profile = supplier_evidence.get("procurement_profile") if isinstance(supplier_evidence, dict) else {}
    if not isinstance(profile, dict):
        return ""
    lines = [
        f"Предмет закупки: {evidence.get('subject') or profile.get('summary') or evidence.get('source_title') or ''}".strip(),
    ]
    items = profile.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            parts = [
                str(item.get("name") or "").strip(),
                ", ".join(str(value) for value in item.get("aliases", []) if str(value).strip()) if isinstance(item.get("aliases"), list) else "",
                ", ".join(str(value) for value in item.get("category_terms", []) if str(value).strip()) if isinstance(item.get("category_terms"), list) else "",
                ", ".join(str(value) for value in item.get("exact_terms", []) if str(value).strip()) if isinstance(item.get("exact_terms"), list) else "",
                ", ".join(str(value) for value in item.get("required_terms", []) if str(value).strip()) if isinstance(item.get("required_terms"), list) else "",
            ]
            text = "; ".join(part for part in parts if part)
            if text:
                lines.append(f"Позиция: {text}")
    return "\n".join(line for line in lines if line and len(line) > 16)


def _supplier_exclusions_from_job(job: Job) -> list[dict]:
    existing_exclusions = read_supplier_exclusions(job)
    suppliers = [
        _supplier_result_exclusion(item)
        for item in getattr(job, "suppliers", []) or []
        if getattr(item, "evidence_status", "") == "verified" or getattr(item, "company_name", "")
    ]
    suppliers = [item for item in suppliers if item.get("company_name") or item.get("site")]
    if suppliers:
        return _dedupe_supplier_exclusions(existing_exclusions + suppliers)
    try:
        evidence = read_job_evidence_payload(job)
    except HTTPException:
        return _dedupe_supplier_exclusions(existing_exclusions)
    accepted = evidence.get("accepted")
    if not isinstance(accepted, list) and isinstance(evidence.get("supplier_search"), dict):
        accepted = evidence["supplier_search"].get("accepted")
    if not isinstance(accepted, list):
        return _dedupe_supplier_exclusions(existing_exclusions)
    evidence_suppliers = [
        {
            "company_name": str(item.get("company_name") or ""),
            "site": str(item.get("site") or ""),
            "evidence_url": str(item.get("evidence_url") or ""),
            "contact_url": str(item.get("contact_url") or ""),
            "email": str(item.get("email") or ""),
            "phone": str(item.get("phone") or ""),
        }
        for item in accepted
        if isinstance(item, dict) and (item.get("company_name") or item.get("site"))
    ]
    return _dedupe_supplier_exclusions(existing_exclusions + evidence_suppliers)


def _dedupe_supplier_exclusions(suppliers: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in suppliers:
        if not isinstance(item, dict):
            continue
        domain = _supplier_exclusion_domain(item)
        company = " ".join(str(item.get("company_name") or "").lower().split())
        key = domain or company
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _supplier_exclusion_domain(item: dict) -> str:
    for key in ("site", "evidence_url", "contact_url"):
        value = str(item.get(key) or "").strip()
        if not value:
            continue
        match = re.search(r"(?i)^(?:https?://)?(?:www\.)?([^/\s?#]+)", value)
        if match:
            return match.group(1).lower()
    return ""


def _supplier_result_exclusion(item: SupplierResult) -> dict:
    return {
        "company_name": item.company_name,
        "site": item.site,
        "evidence_url": item.evidence_url,
        "contact_url": item.contact_url,
        "email": item.email,
        "phone": item.phone,
    }


def is_internal_job(job: Job | object) -> bool:
    return is_internal_job_record(job)


def human_job_title(job: Job | object) -> str:
    if is_internal_job(job):
        return "Служебная проверка"
    mode = str(getattr(job, "mode", "") or "")
    subject = _customer_job_subject_from_evidence(job)
    if subject:
        return _customer_job_title_for_subject(mode, subject)
    raw = str(getattr(job, "title", "") or "").strip()
    if not raw:
        return mode_label(mode)
    cleaned = _clean_customer_job_subject(raw)
    if not cleaned or _looks_like_hash(cleaned):
        return mode_label(mode)
    return _customer_job_title_for_subject(mode, cleaned)


def _customer_job_subject_from_evidence(job: Job | object) -> str:
    evidence_path = Path(str(getattr(job, "evidence_path", "") or ""))
    payload: dict = {}
    if evidence_path.exists():
        try:
            payload = parse_json_dict(evidence_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    subject = _clean_customer_job_subject(payload.get("subject") if payload else "")
    if subject:
        return subject
    output_files = payload.get("output_files") if isinstance(payload, dict) else None
    if isinstance(output_files, list):
        for item in output_files:
            if not isinstance(item, dict):
                continue
            subject = _customer_subject_from_filename(Path(str(item.get("path") or "")).name)
            if subject:
                return subject
    result_path = str(getattr(job, "result_path", "") or "")
    return _customer_subject_from_filename(Path(result_path).name)


def _customer_subject_from_filename(filename: str) -> str:
    stem = Path(str(filename or "")).stem
    stem = re.sub(r"_(?:анализ|поставщики)$", "", stem, flags=re.IGNORECASE)
    return _clean_customer_job_subject(stem)


def _customer_job_title_for_subject(mode: str, subject: str) -> str:
    value = _ellipsize_customer_title(subject)
    if mode == MODE_SUPPLIER_SEARCH:
        return f"ТЗ: {value}"
    if mode == MODE_PROCUREMENT_REPORT:
        return f"Анализ закупки: {value}"
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return f"Анализ + поиск: {value}"
    if mode == MODE_EXACT_PRODUCT:
        return f"Точный товар и аналоги: {value}"
    return value


def _clean_customer_job_subject(value: object) -> str:
    cleaned = " ".join(str(value or "").replace("_", " ").split()).strip(" .,:;\"'")
    cleaned = re.sub(r"\.(?:docx?|xlsx?|pdf|zip|rar|7z|rtf|txt)$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"(?i)^техническое\s+задание\s*[-:—–]?\s*", "", cleaned).strip()
    cleaned = re.sub(r"(?i)^тз\s*[-:—–]?\s*", "", cleaned).strip()
    cleaned = re.sub(r"(?i)^тз(?=[A-ZА-ЯЁ])", "", cleaned).strip()
    cleaned = re.sub(r"(?i)\bтз\b", " ", cleaned)
    cleaned = " ".join(cleaned.split()).strip(" .,:;\"'")
    if not cleaned:
        return ""
    if re.fullmatch(r"[\d\W_]+", cleaned):
        return ""
    if len(re.sub(r"\W", "", cleaned)) < 3:
        return ""
    return cleaned


def _ellipsize_customer_title(value: str, limit: int = 90) -> str:
    cleaned = str(value or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rsplit(" ", 1)[0].rstrip(" .,:;-") + "..."


def _looks_like_hash(value: str) -> bool:
    return len(value) >= 12 and all(char in "0123456789abcdefABCDEF" for char in value)


def mode_label(mode: str) -> str:
    labels = {
        MODE_SUPPLIER_SEARCH: "Поиск поставщиков",
        MODE_PROCUREMENT_REPORT: "Анализ документации",
        MODE_ANALYSIS_AND_SUPPLIERS: "Анализ + поставщики",
        MODE_EXACT_PRODUCT: "Подбор товара и аналогов",
    }
    return labels.get(mode, "Задача")


def client_usage_summary(db: Session, client: Client) -> dict:
    balances = client_service_balance_summary(db, client)
    return {
        "supplier_search": usage_counter_from_balance(balances["supplier_search"]),
        "procurement_report": usage_counter_from_balance(balances["procurement_report"]),
        "supplier_search_extra": usage_counter_from_balance(balances["supplier_search_extra"]),
        "exact_product": usage_counter_from_balance(balances.get("exact_product", {})),
        "money": balances["money"],
        "effective_prices": balances["effective_prices"],
    }


def usage_counter_from_balance(counter: dict) -> dict:
    granted = int(counter.get("granted") or 0)
    manual_debited = int(counter.get("manual_debited") or 0)
    spent = int(counter.get("spent") or 0)
    available = counter.get("available")
    reserved = int(counter.get("reserved") or 0)
    unlimited = bool(counter.get("unlimited"))
    effective_limit = max(0, granted - manual_debited)
    percent = 0 if unlimited or effective_limit <= 0 else min(100, round((spent + reserved) * 100 / effective_limit))
    return {
        "label": counter.get("label") or billing_kind_label(str(counter.get("kind") or "")),
        "used": spent,
        "limit": effective_limit,
        "remaining": available,
        "unlimited": unlimited,
        "percent": percent,
        "available": available,
        "reserved": reserved,
        "spent": spent,
        "granted": granted,
        "manual_debited": manual_debited,
        "source": counter.get("source") or "ledger",
        "low": bool(counter.get("low")),
        "price_kopeks": int(counter.get("price_kopeks") or 0),
        "price_rub": round(int(counter.get("price_kopeks") or 0) / 100, 2),
    }


def usage_counter(*, label: str, used: int, limit: int) -> dict:
    unlimited = limit < 0
    remaining = None if unlimited else max(0, limit - used)
    percent = 0 if unlimited or limit <= 0 else min(100, round(used * 100 / limit))
    return {
        "label": label,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "unlimited": unlimited,
        "percent": percent,
    }


def client_recent_usage(db: Session, client: Client, *, limit: int = 5) -> list[dict]:
    jobs = (
        commercial_jobs_query(db, client)
        .order_by(Job.created_at.desc())
        .limit(max(1, limit * 3))
        .all()
    )
    items: list[dict] = []
    for job in jobs:
        supplier_units, report_units = requested_function_units(str(job.mode or ""))
        if supplier_units <= 0 and report_units <= 0:
            continue
        items.append(
            {
                "id": job.id,
                "mode": job.mode,
                "mode_label": mode_label(job.mode),
                "human_title": human_job_title(job),
                "created_by_telegram_id": job.created_by_telegram_id or (job.client.telegram_id if job.client else ""),
                "supplier_units": supplier_units,
                "procurement_report_units": report_units,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
        )
        if len(items) >= limit:
            break
    return items


def supplier_search_ui(settings: SystemSettings) -> dict:
    provider_order = _provider_order(settings)
    google_key, google_cse = _google_credentials(settings)
    yandex_folder, yandex_key = _yandex_credentials(settings)
    configured = {
        "google": bool(google_key and google_cse),
        "yandex": bool(yandex_folder and yandex_key),
    }
    active_provider = next((provider for provider in provider_order if configured.get(provider)), "")
    if not active_provider:
        active_provider = provider_order[0] if provider_order else "yandex"
    active_ready = bool(configured.get(active_provider))
    return {
        "active_provider": active_provider,
        "active_label": supplier_search_source_label(active_provider),
        "active_note": supplier_search_active_note(active_provider, active_ready),
        "has_active_source": active_ready,
        "provider_order": provider_order,
        "technical_sources": [
            source_ui_item(provider, supplier_search_source_label(provider), configured[provider], active_provider)
            for provider in provider_order
            if provider in configured
        ],
    }


def supplier_search_source_label(provider: str) -> str:
    labels = {
        "yandex": "Яндекс Поиск",
        "google": "Google Поиск",
    }
    return labels.get(provider, "Источник поиска")


def supplier_search_active_note(provider: str, ready: bool) -> str:
    if not ready:
        return "Основной поиск через Яндекс не настроен. Добавьте ключи Яндекса в расширенных параметрах."
    if provider == "yandex":
        return "Основной поиск через Яндекс подключён."
    if provider == "google":
        return "Поиск через Google подключён."
    return "Источник поиска подключён."


def source_ui_item(provider: str, label: str, configured: bool, active_provider: str) -> dict:
    return {
        "id": provider,
        "label": label,
        "configured": configured,
        "active": provider == active_provider,
        "status_label": "используется" if provider == active_provider and configured else "подключён" if configured else "не настроен",
    }


def build_system_status(settings: SystemSettings, db: Session, yandex_balance: float | None = None) -> dict:
    root_disk = disk_usage_payload(Path("/"))
    storage_disk = disk_usage_payload(config.storage_path if config.storage_path.exists() else config.storage_path.parent)
    memory = memory_payload()
    server = {
        **root_disk,
        "cpu_percent": cpu_percent(),
        "ram_total_gb": memory["ram_total_gb"],
        "ram_used_gb": memory["ram_used_gb"],
        "ram_percent": memory["ram_percent"],
        "storage_free_gb": storage_disk["disk_free_gb"],
        "storage_used_gb": storage_disk["disk_used_gb"],
        "storage_percent": storage_disk["disk_percent"],
    }
    now = now_utc()
    week_ago = now - timedelta(days=7)
    queue = {
        "pending": db.query(Job).filter(Job.status == "pending").count(),
        "running": db.query(Job).filter(Job.status == "running").count(),
        "failed": db.query(Job).filter(Job.status == "failed", Job.created_at >= week_ago).count(),
        "failed_total": db.query(Job).filter(Job.status == "failed").count(),
        "completed": db.query(Job).filter(Job.status.in_(["completed", "partial"])).count(),
    }
    services = api_service_statuses(settings, yandex_balance=yandex_balance)
    warnings = []
    if server["disk_free_gb"] < 10:
        warnings.append("На сервере осталось меньше 10 ГБ свободного места.")
    if server["ram_percent"] >= 85:
        warnings.append("Оперативная память загружена выше 85%.")
    if server["cpu_percent"] >= 85:
        warnings.append("CPU загружен выше 85%.")
    if queue["pending"] >= 50:
        warnings.append("В очереди больше 50 задач. Проверьте worker и скорость обработки.")
    return {
        "server": server,
        "queue": queue,
        "services": services,
        "warnings": warnings,
        "status": "warning" if warnings else "ok",
        "updated_at": now_iso(),
    }


def disk_usage_payload(path: Path) -> dict:
    usage = shutil.disk_usage(path)
    return {
        "disk_total_gb": bytes_to_gb(usage.total),
        "disk_used_gb": bytes_to_gb(usage.used),
        "disk_free_gb": bytes_to_gb(usage.free),
        "disk_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
    }


def memory_payload() -> dict:
    meminfo = read_meminfo()
    total = meminfo.get("MemTotal", 0) * 1024
    available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) * 1024
    used = max(0, total - available)
    return {
        "ram_total_gb": bytes_to_gb(total),
        "ram_used_gb": bytes_to_gb(used),
        "ram_percent": round((used / total) * 100, 1) if total else 0.0,
    }


def read_meminfo(path: Path = Path("/proc/meminfo")) -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            parts = value.strip().split()
            if parts and parts[0].isdigit():
                result[key] = int(parts[0])
    except Exception:
        return {}
    return result


def cpu_percent() -> float:
    first = read_cpu_totals()
    time.sleep(0.05)
    second = read_cpu_totals()
    if first and second:
        total_delta = second[0] - first[0]
        idle_delta = second[1] - first[1]
        if total_delta > 0:
            return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)
    try:
        load_1m = os.getloadavg()[0]
        cpu_count = max(1, os.cpu_count() or 1)
        return round(max(0.0, min(100.0, load_1m / cpu_count * 100)), 1)
    except Exception:
        return 0.0


def read_cpu_totals(path: Path = Path("/proc/stat")) -> tuple[int, int] | None:
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        parts = [int(part) for part in first_line.split()[1:]]
    except Exception:
        return None
    if len(parts) < 4:
        return None
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    return sum(parts), idle


def api_service_statuses(settings: SystemSettings, yandex_balance: float | None = None) -> list[dict]:
    yandex_folder, yandex_key = _yandex_credentials(settings)
    google_key, google_cse = _google_credentials(settings)
    configured_ai = [
        item
        for item in parse_json_list(settings.custom_ai_providers_json)
        if str(item.get("apiKey") or "").strip() and str(item.get("baseUrl") or "").strip()
    ]
    
    yandex_configured = bool(yandex_folder and yandex_key)
    yandex_warning = not yandex_configured or (yandex_balance is not None and yandex_balance < 100.0)
    yandex_url = (
        f"https://console.yandex.cloud/folders/{yandex_folder}/dashboard"
        if yandex_folder
        else "https://console.yandex.cloud/folders/b1gmnp1u8urslual8ht8/dashboard"
    )

    services = [
        {
            "id": "yandex",
            "label": "Поиск Яндекс",
            "detail": "yandex.cloud",
            "configured": yandex_configured,
            "status": "ok" if yandex_configured else "missing",
            "status_label": "подключено" if yandex_configured else "не настроено",
            "balance_rub": yandex_balance,
            "balance_label": f"{yandex_balance:.2f} ₽" if yandex_balance is not None else "н/д",
            "warning": yandex_warning,
            "note": "Основной источник поиска поставщиков.",
            "url": yandex_url,
        },
        {
            "id": "google",
            "label": "Google Поиск",
            "detail": "customsearch.googleapis.com",
            "configured": bool(google_key and google_cse),
            "status": "ok" if bool(google_key and google_cse) else "missing",
            "status_label": "подключено" if bool(google_key and google_cse) else "не настроено",
            "balance_label": "подключено",
            "warning": not bool(google_key and google_cse),
            "note": "Основной источник поиска поставщиков.",
            "url": "https://programmablesearchengine.google.com/",
        },
        {
            "id": "ai",
            "label": "Нейросети AI",
            "detail": "OpenRouter / Polza",
            "configured": bool(configured_ai) or settings.has_active_ai_provider,
            "status": "ok" if (bool(configured_ai) or settings.has_active_ai_provider) else "missing",
            "status_label": "подключено" if (bool(configured_ai) or settings.has_active_ai_provider) else "не настроено",
            "balance_label": "подключено",
            "warning": not (bool(configured_ai) or settings.has_active_ai_provider),
            "note": "Используются для анализа и ранжирования.",
            "url": "https://openrouter.ai/settings/credits",
        },
    ]
    return services


def api_service_item(service_id: str, label: str, detail: str, configured: bool, note: str) -> dict:
    return {
        "id": service_id,
        "label": label,
        "detail": detail,
        "configured": configured,
        "status": "ok" if configured else "missing",
        "status_label": "подключено" if configured else "не настроено",
        "balance_label": "баланс не проверяется",
        "note": note,
    }


def bytes_to_gb(value: int | float) -> float:
    return round(float(value) / (1024**3), 2)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def client_to_dict(client: Client, *, db: Session | None = None) -> dict:
    primary_telegram_id = "" if is_pending_telegram_id(client.telegram_id) else client.telegram_id
    return {
        "id": client.id,
        "telegram_id": primary_telegram_id,
        "is_pending": is_pending_telegram_id(client.telegram_id),
        "name": client.name,
        "username": client.username,
        "is_active": client.is_active,
        "is_trial": client.is_trial,
        "access_until": client.access_until,
        "allowed_supplier_search": client.allowed_supplier_search,
        "allowed_procurement_report": client.allowed_procurement_report,
        "monthly_job_limit": client.monthly_job_limit,
        "monthly_supplier_search_limit": client.monthly_supplier_search_limit,
        "monthly_procurement_report_limit": client.monthly_procurement_report_limit,
        "monthly_file_limit": client.monthly_file_limit,
        "supplier_target_min": client.supplier_target_min,
        "notes": client.notes,
        "telegram_accounts": [telegram_account_to_dict(account) for account in sorted(client.telegram_accounts, key=lambda item: item.created_at, reverse=True)],
        "web_users": [web_user_to_admin_dict(user) for user in sorted(client.web_users, key=lambda item: item.created_at, reverse=True)],
        "source": "web" if client.web_users else "telegram",
        "usage": client_usage_summary(db, client) if db else None,
        "recent_usage": client_recent_usage(db, client) if db else [],
        "recent_billing": recent_billing_transactions(db, client) if db else [],
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


def telegram_account_to_dict(account: ClientTelegramAccount) -> dict:
    pending = is_pending_telegram_id(account.telegram_id)
    return {
        "id": account.id,
        "client_id": account.client_id,
        "telegram_id": "" if pending else account.telegram_id,
        "username": account.username,
        "name": account.name,
        "is_active": account.is_active,
        "is_pending": pending,
        "notes": account.notes,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def web_user_to_admin_dict(user: WebUser) -> dict:
    return {
        "id": user.id,
        "client_id": user.client_id,
        "email": user.email,
        "name": user.name,
        "is_active": bool(user.is_active),
        "is_email_verified": bool(user.is_email_verified),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def web_password_reset_to_dict(item: WebPasswordResetRequest) -> dict:
    user = item.user
    client = user.client if user else None
    return {
        "id": item.id,
        "user_id": item.user_id,
        "client_id": user.client_id if user else "",
        "client_name": client.name if client else "",
        "email": item.email,
        "status": item.status,
        "admin_note": item.admin_note,
        "requested_ip": item.requested_ip,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        "resolved_by": item.resolved_by,
        "last_login_at": user.last_login_at.isoformat() if user and user.last_login_at else None,
    }


def job_to_dict(job: Job, include_files: bool = False, settings: SystemSettings | None = None, db: Session | None = None) -> dict:
    supplier_units, report_units = requested_function_units(job.mode)
    evidence_path = str(getattr(job, "evidence_path", "") or "")
    result_files = admin_job_result_files(job)
    ai_info = resolve_job_ai_info(job, settings=settings)
    confirmation_kind = str(getattr(job, "confirmation_kind", "") or "")
    confirmation_outcome = str(getattr(job, "confirmation_outcome", "") or "")
    offer_delivery_outcome = str(getattr(job, "offer_delivery_outcome", "") or "")
    result_offer = result_offer_to_dict(db, job) if confirmation_kind else None
    data = {
        "id": job.id,
        "client_id": job.client_id,
        "client_name": job.client.name if job.client else "",
        "client_email": (job.client.users[0].email if (job.client and getattr(job.client, "users", None) and len(job.client.users) > 0) else "") if job.client else "",
        "client_username": job.client.username if job.client else "",
        "telegram_id": job.client.telegram_id if job.client else "",
        "created_by_telegram_id": job.created_by_telegram_id,
        "mode": job.mode,
        "mode_label": mode_label(job.mode),
        "supplier_search_policy": getattr(job, "supplier_search_policy", None) or SUPPLIER_POLICY_NORMAL,
        "supplier_search_run_type": getattr(job, "supplier_search_run_type", None) or SUPPLIER_RUN_INITIAL,
        "confirmation_kind": confirmation_kind,
        "confirmation_outcome": confirmation_outcome,
        "offer_delivery_outcome": offer_delivery_outcome,
        "result_offer": result_offer,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "title": job.title,
        "human_title": human_job_title(job),
        "is_internal": is_internal_job(job),
        "supplier_units": supplier_units,
        "procurement_report_units": report_units,
        "target_suppliers": job.target_suppliers,
        "verified_count": job.verified_count,
        "file_count": job.file_count,
        "has_result": bool(result_files),
        "result_files": result_files,
        "has_evidence": bool(evidence_path),
        "error": job.error,
        "ai_provider": ai_info.get("ai_provider", ""),
        "ai_provider_name": ai_info.get("ai_provider_name", ""),
        "ai_model": ai_info.get("ai_model", ""),
        "ai_label": ai_info.get("ai_label", ""),
        "yandex_requests_count": getattr(job, "yandex_requests_count", 0) or 0,
        "yandex_cost_rub": getattr(job, "yandex_cost_rub", 0.0) or 0.0,
        "yandex_cost_label": f"{(getattr(job, 'yandex_cost_rub', 0.0) or 0.0):.2f} ₽",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "input_files": [file_to_dict(item) for item in job.files],
        "sources": [source_to_dict(item) for item in job.sources],
    }
    if include_files:
        data["files"] = [file_to_dict(item) for item in job.files]
        data["suppliers"] = [supplier_to_dict(item) for item in job.suppliers]
    return data


def admin_job_result_files(job: Job) -> list[dict]:
    result: list[dict] = []
    if not getattr(job, "evidence_path", None) and getattr(job, "status", "") != "completed":
        return result
    for item in package_job_output_items(job):
        path = Path(str(item.get("path") or ""))
        kind = str(item.get("kind") or path.stem).strip()
        result.append(
            {
                "kind": kind,
                "label": _customer_result_file_label(kind, str(item.get("label") or "")),
                "filename": path.name,
            }
        )
    return result


def file_to_dict(file: JobFile) -> dict:
    return {
        "id": file.id,
        "original_filename": file.original_filename,
        "parse_status": file.parse_status,
        "extracted_chars": file.extracted_chars,
        "error": file.error,
    }


def source_to_dict(source: JobSource) -> dict:
    return {
        "id": source.id,
        "kind": source.kind,
        "label": source.label,
        "value": source.value,
        "parse_status": source.parse_status,
        "extracted_chars": source.extracted_chars,
        "error": source.error,
    }


def supplier_to_dict(item: SupplierResult) -> dict:
    return {
        "company_name": item.company_name,
        "region": item.region,
        "status": item.status,
        "product": item.product,
        "phone": item.phone,
        "email": item.email,
        "site": item.site,
        "evidence_url": item.evidence_url,
        "contact_url": item.contact_url,
        "comments": item.comments,
        "evidence_status": item.evidence_status,
        "match_level": getattr(item, "match_level", ""),
        "source": getattr(item, "source", ""),
        "search_query": getattr(item, "search_query", ""),
        "quality_score": getattr(item, "quality_score", 0),
        "quality_tier": getattr(item, "quality_tier", ""),
        "procurement_item_id": getattr(item, "procurement_item_id", ""),
        "procurement_item": getattr(item, "procurement_item", ""),
        "ai_confidence": getattr(item, "ai_confidence", 0),
        "site_type": getattr(item, "site_type", ""),
        "product_fit": getattr(item, "product_fit", ""),
        "evidence_snippet": getattr(item, "evidence_snippet", ""),
        "contact_evidence_snippet": getattr(item, "contact_evidence_snippet", ""),
        "ai_rank_confidence": getattr(item, "ai_rank_confidence", 0),
        "ai_rank_reason": getattr(item, "ai_rank_reason", ""),
    }
