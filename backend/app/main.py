from __future__ import annotations

import json
import os
import re
import shutil
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import time

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from .ai import call_llm
from .billing import (
    BillingError,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CUSTOMER_DECLINED,
    VALID_BILLING_KINDS,
    billing_kind_label,
    charge_job_reservation,
    client_balance_summary,
    client_uses_trial_access,
    expire_stale_confirmations,
    grant_package_units,
    release_job_reservation,
    list_tariffs,
    recent_billing_transactions,
    reserve_job_units,
    tariff_to_dict,
    transaction_to_dict,
)
from .config import config
from .db import db_session, init_db
from .jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    VALID_JOB_MODES,
    cleanup_expired_jobs,
    create_job,
    enqueue_job,
    package_job_output_items,
    package_job_outputs,
    recover_interrupted_jobs,
)
from .models import BillingTransaction, Client, ClientTelegramAccount, Job, JobFile, JobSource, SupplierResult, SystemSettings, TariffPackage, WebEmailVerificationToken, WebPasswordResetRequest, WebRegistrationAttempt, WebSession, WebUser, now_utc, parse_json_dict, parse_json_list
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
from .schemas import (
    AiTestRequest,
    ClientCreate,
    ClientMergeRequest,
    ClientPatch,
    ClientTelegramAccountCreate,
    ClientTelegramAccountPatch,
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
    WebAuthContext,
    authenticate_web_user,
    clear_customer_session_cookie,
    create_email_verification_token,
    create_web_session,
    create_web_user,
    generate_temporary_password,
    hash_password,
    send_email_verification,
    optional_web_context,
    require_customer_csrf,
    require_web_context,
    revoke_web_session,
    set_customer_session_cookie,
    validate_email,
    verify_email_token,
)
from .supplier_search import _google_credentials, _provider_order, _tavily_key_candidates, _yandex_credentials

ANALYTICS_EXCLUDED_WEB_EMAILS = {"79210629909@ya.ru"}
ANALYTICS_EXCLUDED_TELEGRAM_USERNAMES = {"lexelence", "lexs"}
ANALYTICS_EXCLUDED_TELEGRAM_IDS = {"320433711"}

app = FastAPI(title="TenderLex API", version="0.1.0")
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
    finally:
        db.close()
    for job_id in recovered_job_ids:
        enqueue_job(job_id)


@app.get("/api/health")
def health(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return {
        "ok": True,
        "domain": settings.public_base_url,
        "logistics_enabled": settings.logistics_enabled,
    }


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
    _check_customer_registration_rate(db, request, data.email)
    key = _check_customer_auth_rate(request, data.email)
    try:
        user = create_web_user(db, email=data.email, password=data.password, name=data.name, email_verified=False)
    except ValueError as exc:
        _record_customer_registration_attempt(db, request, data.email, "failed")
        _record_customer_auth_failure(key)
        detail = str(exc)
        status_code = 409 if "уже зарегистрирован" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
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
    context: WebAuthContext | None = Depends(optional_web_context),
    db: Session = Depends(db_session),
) -> dict:
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
    limit: int = 50,
    context: WebAuthContext = Depends(require_web_context),
    db: Session = Depends(db_session),
) -> list[dict]:
    safe_limit = max(1, min(200, int(limit or 50)))
    jobs = (
        commercial_jobs_query(db, context.user.client)
        .order_by(Job.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    return [customer_job_to_dict(job) for job in jobs]


@app.post("/api/customer/jobs")
async def customer_create_job_route(
    request: Request,
    mode: str = Form(default=MODE_SUPPLIER_SEARCH),
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
    return {
        "clients": db.query(Client).count(),
        "active_clients": db.query(Client).filter(Client.is_active.is_(True)).count(),
        "jobs": db.query(Job).count(),
        "running_jobs": db.query(Job).filter(Job.status.in_(["pending", "running"])).count(),
        "completed_jobs": db.query(Job).filter(Job.status.in_(["completed", "partial"])).count(),
        "failed_jobs": db.query(Job).filter(Job.status == "failed").count(),
        "suppliers": db.query(SupplierResult).count(),
    }


@app.get("/api/ops/system-status", dependencies=[Depends(require_admin)])
def system_status_ops(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return build_system_status(settings, db)


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


@app.get("/api/analytics/bot", dependencies=[Depends(require_admin)])
def bot_analytics_api(period_days: int = 30, db: Session = Depends(db_session)) -> dict:
    safe_days = min(365, max(1, int(period_days or 30)))
    return build_bot_analytics(db, period_days=safe_days)


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


@app.post("/api/tariffs", dependencies=[Depends(require_admin)])
def create_tariff_api(data: TariffPackageCreate, db: Session = Depends(db_session)) -> dict:
    if data.kind not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown tariff kind")
    package = TariffPackage(**data.model_dump())
    db.add(package)
    db.commit()
    db.refresh(package)
    return tariff_to_dict(package)


@app.patch("/api/tariffs/{package_id}", dependencies=[Depends(require_admin)])
def patch_tariff_api(package_id: str, data: TariffPackagePatch, db: Session = Depends(db_session)) -> dict:
    package = db.get(TariffPackage, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Tariff package not found")
    payload = data.model_dump(exclude_unset=True)
    if "kind" in payload and payload["kind"] not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown tariff kind")
    for key, value in payload.items():
        if value is not None:
            setattr(package, key, value)
    db.commit()
    db.refresh(package)
    return tariff_to_dict(package)


@app.delete("/api/tariffs/{package_id}", dependencies=[Depends(require_admin)])
def delete_tariff_api(package_id: str, db: Session = Depends(db_session)) -> dict:
    package = db.get(TariffPackage, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Tariff package not found")
    db.delete(package)
    db.commit()
    return {"success": True}


@app.get("/api/clients", dependencies=[Depends(require_admin)])
def list_clients(db: Session = Depends(db_session)) -> list[dict]:
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
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
        db.query(BillingTransaction).filter(BillingTransaction.job_id.in_(job_ids)).delete(synchronize_session=False)
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
    merge_note = f"Объединён клиент: {source.name or source.username or source.telegram_id or source.id}"
    target.notes = "\n".join(item for item in [target.notes, merge_note] if item).strip()

    db.query(Job).filter(Job.client_id == source.id).update({Job.client_id: target.id}, synchronize_session=False)
    db.query(BillingTransaction).filter(BillingTransaction.client_id == source.id).update({BillingTransaction.client_id: target.id}, synchronize_session=False)
    db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == source.id).update({ClientTelegramAccount.client_id: target.id}, synchronize_session=False)
    db.query(WebUser).filter(WebUser.client_id == source.id).update({WebUser.client_id: target.id}, synchronize_session=False)
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
    if data.package_id and not package:
        raise HTTPException(status_code=404, detail="Tariff package not found")
    kind = package.kind if package else data.kind
    units = package.units if package else data.units
    if kind not in VALID_BILLING_KINDS:
        raise HTTPException(status_code=400, detail="Unknown billing kind")
    note = data.note or (f"Начислен пакет «{package.name}»" if package else "Ручное пополнение пакета")
    transaction = grant_package_units(
        db,
        client,
        kind=kind,
        units=units,
        package_id=package.id if package else data.package_id,
        note=note,
        created_by="admin",
    )
    db.refresh(client)
    return {
        "success": True,
        "transaction": transaction_to_dict(transaction),
        "client": client_to_dict(client, db=db),
    }


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
    limit: int = 200,
    db: Session = Depends(db_session),
) -> list[dict]:
    safe_limit = max(1, min(500, int(limit or 200)))
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(safe_limit * 3).all()
    visible_jobs = jobs if include_internal else [job for job in jobs if not is_internal_job(job)]
    return [job_to_dict(job) for job in visible_jobs[:safe_limit]]


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_admin)])
def get_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_dict(job, include_files=True)


@app.get("/api/jobs/{job_id}/download", dependencies=[Depends(require_admin)])
def download_job(job_id: str, db: Session = Depends(db_session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    output = package_job_outputs(job)
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(output, filename=output.name)


@app.get("/api/jobs/{job_id}/evidence", dependencies=[Depends(require_admin)])
def get_job_evidence(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return read_job_evidence_payload(job)


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_admin)])
def retry_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "pending"
    job.progress = 0
    job.error = ""
    job.message = "Повторный запуск"
    db.commit()
    enqueue_job(job.id)
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
        if status in {"completed", "partial", "needs_review"} and target and verified < target:
            underfilled += 1
        created_at = getattr(job, "created_at", None)
        completed_at = getattr(job, "completed_at", None)
        if created_at and completed_at:
            durations.append(max(0.0, (completed_at - created_at).total_seconds()))
        evidence = _safe_read_job_evidence(job, storage_root=storage_root)
        if evidence.get("ai_required") and status == "failed":
            ai_required_failures += 1
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

    return {
        "window_size": supplier_jobs,
        "status_counts": dict(sorted(status_counts.items())),
        "average_verified_count": round(total_verified / supplier_jobs, 2) if supplier_jobs else 0,
        "average_duration_seconds": round(sum(durations) / len(durations), 2) if durations else 0,
        "underfilled_terminal_jobs": underfilled,
        "ai_required_failures": ai_required_failures,
        "provider_status_counts": {
            provider: dict(sorted(counts.items()))
            for provider, counts in sorted(provider_status_counts.items())
        },
        "recent_failures": recent_failures,
        "alerts": build_supplier_quality_alerts(
            supplier_jobs=supplier_jobs,
            status_counts=status_counts,
            provider_status_counts=provider_status_counts,
            ai_required_failures=ai_required_failures,
            underfilled_terminal_jobs=underfilled,
            average_duration_seconds=round(sum(durations) / len(durations), 2) if durations else 0,
        ),
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
    if sources and mode not in {MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS}:
        raise HTTPException(
            status_code=400,
            detail="Supplier search requires a technical assignment file; procurement numbers and links are accepted for documentation analysis.",
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
            enqueue_job(job.id)
            jobs.append(job_to_dict(job))
        return {"batch": True, "count": len(jobs), "jobs": jobs}

    title = Path(files[0].filename).stem if files else source_label(sources[0]["value"])
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
        if item.client_id not in excluded_client_ids
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
    }
    return labels.get(str(status or ""), str(status or "") or "неизвестно")


def client_display_name(client: Client) -> str:
    return client.name or (f"@{client.username}" if client.username else "") or client.telegram_id or "без имени"


def _daily_job_series(jobs: list[Job], *, now, period_days: int) -> list[dict]:
    start = (now - timedelta(days=period_days - 1)).date()
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
        key = job.created_at.date().isoformat()
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
            {"kind": kind, "label": billing_kind_label(kind), "granted": 0, "reserved": 0, "charged": 0, "released": 0},
        )
        units = int(item.units or 0)
        if item.operation == "grant":
            row["granted"] += units
        elif item.operation == "reserve":
            row["reserved"] += units
        elif item.operation == "charge":
            row["charged"] += units
        elif item.operation == "release":
            row["released"] += units
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
            "telegram": settings.contact_telegram,
            "telegram_url": telegram_public_url(settings.contact_telegram),
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
            "supplier_search": [item for item in tariffs if item["kind"] == "supplier_search"],
            "procurement_report": [item for item in tariffs if item["kind"] == "procurement_report"],
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
            "supplier_search": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True) if item.kind == "supplier_search"],
            "procurement_report": [tariff_to_public_dict(item) for item in list_tariffs(db, active_only=True) if item.kind == "procurement_report"],
        },
        "contacts": {
            "email": settings.contact_email,
            "telegram": settings.contact_telegram,
            "telegram_url": telegram_public_url(settings.contact_telegram),
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


def customer_job_to_dict(job: Job, include_files: bool = False) -> dict:
    supplier_units, report_units = requested_function_units(job.mode)
    result_files = customer_job_result_files(job)
    data = {
        "id": job.id,
        "client_id": job.client_id,
        "mode": job.mode,
        "mode_label": mode_label(job.mode),
        "status": job.status,
        "status_label": human_status_label(job.status),
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
        "result_files": result_files,
        "awaiting_customer_confirmation": job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_files:
        data["files"] = [file_to_dict(item) for item in job.files]
        data["sources"] = [source_to_dict(item) for item in job.sources]
    return data


def customer_job_result_files(job: Job) -> list[dict]:
    if getattr(job, "status", "") in {STATUS_AWAITING_CUSTOMER_CONFIRMATION, STATUS_CUSTOMER_DECLINED}:
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
    return "Файл"


async def create_customer_job_api(
    *,
    mode: str,
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
    if job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтвердите неполный отчёт перед скачиванием.")
    output = package_job_outputs(job)
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Файл результата не найден.")
    charge_job_reservation(db, job)
    return FileResponse(output, filename=output.name)


def download_customer_job_file_api(job_id: str, file_kind: str, *, context: WebAuthContext, db: Session):
    job = _customer_job_or_404(db, job_id, context)
    if job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтвердите неполный отчёт перед скачиванием.")
    normalized_kind = str(file_kind or "").strip()
    output = None
    for item in package_job_output_items(job):
        if str(item.get("kind") or "") == normalized_kind:
            output = Path(str(item.get("path") or ""))
            break
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Файл результата не найден.")
    charge_job_reservation(db, job)
    return FileResponse(output, filename=output.name)


def accept_customer_partial_job_api(job_id: str, *, context: WebAuthContext, db: Session):
    job = _customer_job_or_404(db, job_id, context)
    if job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтверждение уже не актуально.")
    job.status = "partial"
    job.message = "Клиент принял неполный отчёт"
    job.error = ""
    job.updated_at = now_utc()
    if job.completed_at is None:
        job.completed_at = now_utc()
    db.commit()
    return {"success": True, "job": customer_job_to_dict(job)}


def decline_customer_partial_job_api(job_id: str, *, context: WebAuthContext, db: Session) -> dict:
    job = _customer_job_or_404(db, job_id, context)
    if job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        raise HTTPException(status_code=409, detail="Подтверждение уже не актуально.")
    release_job_reservation(db, job, note="Резерв возвращён: клиент сайта отказался от неполного отчёта")
    job.status = STATUS_CUSTOMER_DECLINED
    job.message = "Клиент отказался от неполного отчёта"
    job.error = ""
    job.completed_at = now_utc()
    job.updated_at = now_utc()
    db.commit()
    return {"success": True, "job": customer_job_to_dict(job)}


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
    }
    return labels.get(mode, "Задача")


def client_usage_summary(db: Session, client: Client) -> dict:
    balances = client_balance_summary(db, client)
    return {
        "supplier_search": usage_counter_from_balance(balances["supplier_search"]),
        "procurement_report": usage_counter_from_balance(balances["procurement_report"]),
    }


def usage_counter_from_balance(counter: dict) -> dict:
    granted = int(counter.get("granted") or 0)
    spent = int(counter.get("spent") or 0)
    available = counter.get("available")
    reserved = int(counter.get("reserved") or 0)
    unlimited = bool(counter.get("unlimited"))
    percent = 0 if unlimited or granted <= 0 else min(100, round((spent + reserved) * 100 / granted))
    return {
        "label": counter.get("label") or billing_kind_label(str(counter.get("kind") or "")),
        "used": spent,
        "limit": granted,
        "remaining": available,
        "unlimited": unlimited,
        "percent": percent,
        "available": available,
        "reserved": reserved,
        "spent": spent,
        "granted": granted,
        "source": counter.get("source") or "ledger",
        "low": bool(counter.get("low")),
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
            }
        )
        if len(items) >= limit:
            break
    return items


def supplier_search_ui(settings: SystemSettings) -> dict:
    provider_order = _provider_order(settings)
    tavily_ready = bool(_tavily_key_candidates(settings))
    google_key, google_cse = _google_credentials(settings)
    yandex_folder, yandex_key = _yandex_credentials(settings)
    configured = {
        "tavily": tavily_ready,
        "google": bool(google_key and google_cse),
        "yandex": bool(yandex_folder and yandex_key),
        "ddgs": "ddgs" in provider_order,
    }
    active_provider = next((provider for provider in provider_order if configured.get(provider)), "")
    if not active_provider:
        active_provider = provider_order[0] if provider_order else "tavily"
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
        "tavily": "Дополнительный поиск Tavily",
        "ddgs": "Резерв DuckDuckGo",
    }
    return labels.get(provider, "Источник поиска")


def supplier_search_active_note(provider: str, ready: bool) -> str:
    if not ready:
        return "Первый источник в порядке поиска не настроен. Добавьте ключи Яндекса или Google в расширенных параметрах."
    if provider == "yandex":
        return "Основной поиск через Яндекс подключён."
    if provider == "google":
        return "Основной поиск через Google подключён."
    if provider == "tavily":
        return "Работает дополнительный источник Tavily."
    if provider == "ddgs":
        return "Работает резервный поиск без ключа."
    return "Источник поиска подключён."


def source_ui_item(provider: str, label: str, configured: bool, active_provider: str) -> dict:
    return {
        "id": provider,
        "label": label,
        "configured": configured,
        "active": provider == active_provider,
        "status_label": "используется" if provider == active_provider and configured else "подключён" if configured else "не настроен",
    }


def build_system_status(settings: SystemSettings, db: Session) -> dict:
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
    queue = {
        "pending": db.query(Job).filter(Job.status == "pending").count(),
        "running": db.query(Job).filter(Job.status == "running").count(),
        "failed": db.query(Job).filter(Job.status == "failed").count(),
        "completed": db.query(Job).filter(Job.status.in_(["completed", "partial"])).count(),
    }
    services = api_service_statuses(settings)
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


def api_service_statuses(settings: SystemSettings) -> list[dict]:
    yandex_folder, yandex_key = _yandex_credentials(settings)
    google_key, google_cse = _google_credentials(settings)
    configured_ai = [
        item
        for item in parse_json_list(settings.custom_ai_providers_json)
        if str(item.get("apiKey") or "").strip() and str(item.get("baseUrl") or "").strip()
    ]
    services = [
        api_service_item("yandex", "Яндекс Поиск", "yandex.cloud", bool(yandex_folder and yandex_key), "Основной источник поиска поставщиков."),
        api_service_item("google", "Google Поиск", "customsearch.googleapis.com", bool(google_key and google_cse), "Основной источник поиска поставщиков."),
        api_service_item("ai", "Нейросети", f"подключений: {len(configured_ai)}", bool(configured_ai), "Используются для анализа документации и проверки поставщиков."),
        api_service_item("tavily", "Tavily", "дополнительный поиск", bool(_tavily_key_candidates(settings)), "Вспомогательный источник после Яндекса и Google."),
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


def job_to_dict(job: Job, include_files: bool = False) -> dict:
    supplier_units, report_units = requested_function_units(job.mode)
    data = {
        "id": job.id,
        "client_id": job.client_id,
        "client_name": job.client.name if job.client else "",
        "telegram_id": job.client.telegram_id if job.client else "",
        "created_by_telegram_id": job.created_by_telegram_id,
        "mode": job.mode,
        "mode_label": mode_label(job.mode),
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
        "has_result": bool(job.result_path),
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_files:
        data["files"] = [file_to_dict(item) for item in job.files]
        data["sources"] = [source_to_dict(item) for item in job.sources]
        data["suppliers"] = [supplier_to_dict(item) for item in job.suppliers]
    return data


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
