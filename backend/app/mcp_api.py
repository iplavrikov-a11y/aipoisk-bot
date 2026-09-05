from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from .ai import get_model_selection
from .config import config
from .db import db_session
from .exact_product import (
    ExactProductReport,
    analyze_exact_product,
    write_exact_product_docx,
)
from .models import ApiKey, Client, SystemSettings, now_utc
from .procurement_report import generate_procurement_report
from .quote_request import build_quote_request_markdown_with_ai
from .repository import get_or_create_settings
from .security import require_admin
from .supplier_search import (
    discover_suppliers,
    extract_supplier_search_context,
    supplier_search_job_context,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])
admin_router = APIRouter(prefix="/api/admin/api-keys", tags=["admin_api_keys"])

# In-memory sliding rate limiter per key_id: {key_id: [timestamps]}
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}
_MAX_SPEC_LENGTH = 500000
_MAX_DOC_LENGTH = 800000


# ---------------------------------------------------------------------------
# Key Utilities & Security
# ---------------------------------------------------------------------------

def hash_api_key(raw_key: str) -> str:
    """Computes SHA-256 hex digest for secure API key storage and constant-time lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_api_key(is_admin: bool = False) -> tuple[str, str, str]:
    """
    Generates a cryptographically strong API key.
    Returns: (raw_key, key_hash, key_prefix)
    """
    prefix = "tl_admin_" if is_admin else "tl_live_"
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_part}"
    key_hash = hash_api_key(raw_key)
    key_prefix = f"{raw_key[:12]}...{raw_key[-4:]}"
    return raw_key, key_hash, key_prefix


def _check_rate_limit(key_id: str, max_per_minute: int = 30) -> None:
    """In-memory sliding window rate limiter."""
    now = time.time()
    window_start = now - 60.0
    timestamps = _RATE_LIMIT_STORE.get(key_id, [])
    # Filter timestamps within current 60s window
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= max_per_minute:
        _RATE_LIMIT_STORE[key_id] = timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {max_per_minute} requests per minute.",
        )
    timestamps.append(now)
    _RATE_LIMIT_STORE[key_id] = timestamps


def get_api_key_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(db_session),
) -> ApiKey:
    """
    Dependency that authenticates requests using Bearer token or X-API-Key header.
    Validates key existence, active status, expiration, and rate limits.
    """
    raw_token = ""
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:].strip()
    elif x_api_key:
        raw_token = x_api_key.strip()
    elif authorization:
        raw_token = authorization.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Pass 'Authorization: Bearer tl_live_...' or 'X-API-Key: tl_live_...'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    computed_hash = hash_api_key(raw_token)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == computed_hash).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is disabled or revoked",
        )

    if api_key.expires_at:
        now = datetime.now(timezone.utc)
        exp = api_key.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
            )

    # Check rate limit
    _check_rate_limit(api_key.id, api_key.rate_limit_per_minute or 30)

    # Update last used timestamp
    try:
        api_key.last_used_at = now_utc()
        db.commit()
    except Exception:
        db.rollback()

    return api_key


def consume_quota(db: Session, api_key: ApiKey, service: str, count: int = 1) -> int:
    """
    Verifies service permission and consumes quota.
    For admin master keys, quotas are bypassed.
    Returns remaining quota count (-1 for unlimited).
    """
    if api_key.is_admin:
        return -1

    if service == "supplier_search":
        if not api_key.allowed_supplier_search:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supplier search service ('supplier_search') is not permitted for this API key",
            )
        if (api_key.spent_supplier_search + count) > api_key.quota_supplier_search:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Supplier search quota exceeded (spent: {api_key.spent_supplier_search}, limit: {api_key.quota_supplier_search})",
            )
        api_key.spent_supplier_search += count
        db.commit()
        return max(0, api_key.quota_supplier_search - api_key.spent_supplier_search)

    elif service == "exact_product":
        if not api_key.allowed_exact_product:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Exact product & Form 2 service ('exact_product') is not permitted for this API key",
            )
        if (api_key.spent_exact_product + count) > api_key.quota_exact_product:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Exact product quota exceeded (spent: {api_key.spent_exact_product}, limit: {api_key.quota_exact_product})",
            )
        api_key.spent_exact_product += count
        db.commit()
        return max(0, api_key.quota_exact_product - api_key.spent_exact_product)

    elif service == "procurement_report":
        if not api_key.allowed_procurement_report:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Procurement documentation analysis service ('procurement_report') is not permitted for this API key",
            )
        if (api_key.spent_procurement_report + count) > api_key.quota_procurement_report:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Procurement analysis quota exceeded (spent: {api_key.spent_procurement_report}, limit: {api_key.quota_procurement_report})",
            )
        api_key.spent_procurement_report += count
        db.commit()
        return max(0, api_key.quota_procurement_report - api_key.spent_procurement_report)

    return -1


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Public MCP Request / Response Schemas
# ---------------------------------------------------------------------------

def _extract_str(data: dict[str, Any], keys: list[str], default: str = "") -> str:
    for k in keys:
        val = data.get(k)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def _extract_int(data: dict[str, Any], keys: list[str], default: int) -> int:
    for k in keys:
        val = data.get(k)
        if val is not None:
            try:
                iv = int(val)
                if iv > 0:
                    return iv
            except (ValueError, TypeError):
                pass
    return default


def _format_characteristics(chars: Any) -> str:
    """Formats characteristics passed as list of dicts, dict, or list of strings into clean text."""
    if not chars:
        return ""
    lines = []
    if isinstance(chars, list):
        for item in chars:
            if isinstance(item, dict):
                name = item.get("name") or item.get("param") or item.get("parameter") or item.get("title") or item.get("key") or ""
                value = item.get("value") or item.get("val") or item.get("description") or ""
                if name and value:
                    lines.append(f"• {name}: {value}")
                elif name or value:
                    lines.append(f"• {name or value}")
            elif isinstance(item, str) and item.strip():
                lines.append(f"• {item.strip()}")
    elif isinstance(chars, dict):
        for k, v in chars.items():
            if str(k).strip() and str(v).strip():
                lines.append(f"• {str(k).strip()}: {str(v).strip()}")
    elif isinstance(chars, str) and chars.strip():
        lines.append(chars.strip())
    return "\n".join(lines)


class McpBalanceResponse(BaseModel):
    ok: bool = True
    key_name: str
    key_prefix: str
    is_admin: bool
    is_active: bool
    supplier_search: Dict[str, Any]
    exact_product: Dict[str, Any]
    procurement_report: Dict[str, Any]
    rate_limit_per_minute: int
    expires_at: Optional[str] = None


class McpSupplierSearchRequest(BaseModel):
    specification: str = Field(..., min_length=2, max_length=_MAX_SPEC_LENGTH, description="Текст ТЗ, спецификации или наименование закупаемой продукции")
    target_count: int = Field(default=5, ge=1, le=50, description="Желаемое количество поставщиков для поиска")
    city: str = Field(default="", max_length=120, description="Город или регион поставки (опционально)")
    include_quote_request: bool = Field(default=True, description="Сформировать готовый шаблон запроса КП")
    search_policy: str = Field(
        default="normal",
        description="Режим поиска: 'normal' (обычный рынок РФ), 'minprom_registry_priority' (приоритет реестра Минпромторга / ГИСП), 'minprom_registry_only' (только производители из реестра Минпромторга РФ)"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # 1. Target count / limit / max_results
        target = _extract_int(d, ["target_count", "max_results", "limit", "count", "suppliers_count", "target"], default=5)
        d["target_count"] = min(50, max(1, target))

        # 2. City / Delivery region
        city = _extract_str(d, ["city", "delivery_region", "region", "location", "delivery_city", "address"], default="")
        d["city"] = city

        # 3. Search policy
        policy = _extract_str(d, ["search_policy", "policy", "mode"], default="normal").lower().strip()
        if policy in {"minprom_registry_only", "only_registry", "gisp_only"}:
            d["search_policy"] = "minprom_registry_only"
        elif policy in {"minprom_registry_priority", "registry_priority", "priority_registry", "gisp_priority"}:
            d["search_policy"] = "minprom_registry_priority"
        else:
            d["search_policy"] = "normal"

        # 4. Include quote request
        if "include_quote_request" not in d:
            for k in ["quote_request", "commercial_offer", "kp", "with_quote"]:
                if k in d:
                    d["include_quote_request"] = bool(d[k])
                    break

        # 5. Specification assembly from any AI agent format
        spec_text = _extract_str(d, ["specification", "spec", "text", "tz", "description", "content", "query"], default="")
        prod_name = _extract_str(d, ["product_name", "procurement_title", "title", "name", "item_name", "subject", "item"], default="")
        okpd2 = _extract_str(d, ["okpd2", "okpd", "code"], default="")
        qty = d.get("quantity") or d.get("amount") or d.get("count_items")
        chars_text = _format_characteristics(d.get("characteristics") or d.get("params") or d.get("parameters") or d.get("specs") or d.get("attributes"))

        parts = []
        if prod_name and prod_name.lower() not in spec_text.lower():
            parts.append(f"Предмет закупки / товар: {prod_name}")
        if okpd2 and okpd2 not in spec_text:
            parts.append(f"Код ОКПД2: {okpd2}")
        if qty and str(qty) not in spec_text:
            parts.append(f"Количество: {qty}")
        if spec_text:
            parts.append(spec_text)
        if chars_text and chars_text not in spec_text:
            parts.append(f"Характеристики:\n{chars_text}")

        final_spec = "\n\n".join([p for p in parts if p.strip()]).strip()
        if not final_spec:
            final_spec = prod_name or spec_text or "Товар по спецификации"

        d["specification"] = final_spec
        return d


class McpSupplierItem(BaseModel):
    company_name: str
    inn: str = ""
    region: str = ""
    status: str = "поставщик"  # завод | дилер | дистрибьютор | поставщик
    product: str = ""
    site: str = ""
    email: str = ""
    phone: str = ""
    match_level: str = "exact"  # exact | adjacent | profile
    quality_score: int = 0
    comments: str = ""
    evidence_url: str = ""


class McpSupplierSearchResponse(BaseModel):
    ok: bool = True
    total_found: int
    target_requested: int
    suppliers: List[McpSupplierItem]
    quote_request_markdown: Optional[str] = None
    quota_remaining: int
    source_title: str = ""


class McpExactProductRequest(BaseModel):
    specification: str = Field(..., min_length=2, max_length=_MAX_SPEC_LENGTH, description="Текст технического задания, параметров или требований к оборудованию")
    procurement_title: str = Field(default="", max_length=300, description="Наименование предмета закупки (опционально)")

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # 1. Procurement title
        title = _extract_str(d, ["procurement_title", "product_name", "title", "name", "item_name", "subject", "item"], default="")
        d["procurement_title"] = title

        # 2. Specification assembly from any AI agent format
        spec_text = _extract_str(d, ["specification", "spec", "text", "tz", "description", "content", "query"], default="")
        okpd2 = _extract_str(d, ["okpd2", "okpd", "code"], default="")
        qty = d.get("quantity") or d.get("amount") or d.get("count_items")
        chars_text = _format_characteristics(d.get("characteristics") or d.get("params") or d.get("parameters") or d.get("specs") or d.get("attributes"))

        parts = []
        if title and title.lower() not in spec_text.lower():
            parts.append(f"Предмет закупки / товар: {title}")
        if okpd2 and okpd2 not in spec_text:
            parts.append(f"Код ОКПД2: {okpd2}")
        if qty and str(qty) not in spec_text:
            parts.append(f"Количество: {qty}")
        if spec_text:
            parts.append(spec_text)
        if chars_text and chars_text not in spec_text:
            parts.append(f"Характеристики:\n{chars_text}")

        final_spec = "\n\n".join([p for p in parts if p.strip()]).strip()
        if not final_spec:
            final_spec = title or spec_text or "Товар по спецификации"

        d["specification"] = final_spec
        return d


class McpSpecMatchItem(BaseModel):
    param_name: str
    tz_requirement: str
    product_fact: str
    status: str  # match | mismatch | clarify
    comment: str = ""


class McpAlternativeItem(BaseModel):
    brand: str
    model: str
    manufacturer: str
    confidence: float
    notes: str = ""
    inn: str = ""
    region: str = ""
    specs_breakdown: List[McpSpecMatchItem] = []


class McpExactPositionItem(BaseModel):
    position_no: int
    name_in_tz: str
    identified_brand: str
    identified_model: str
    manufacturer: str
    confidence: float
    reasoning: str
    specs_breakdown: List[McpSpecMatchItem]
    alternatives: List[McpAlternativeItem]


class McpExactProductResponse(BaseModel):
    ok: bool = True
    summary: str
    total_positions: int
    positions: List[McpExactPositionItem]
    docx_download_url: Optional[str] = None
    quota_remaining: int


class McpProcurementAnalyzeRequest(BaseModel):
    document_text: str = Field(..., min_length=2, max_length=_MAX_DOC_LENGTH, description="Текст проекта контракта, извещения или закупочной документации")

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        doc_text = _extract_str(d, [
            "document_text", "text", "document", "doc", "contract_text",
            "tz", "specification", "content", "file_content", "description", "data"
        ], default="")
        d["document_text"] = doc_text or "Документация закупки"
        return d


class McpProcurementAnalyzeResponse(BaseModel):
    ok: bool = True
    report_markdown: str
    ai_model: str = ""
    quota_remaining: int


# ---------------------------------------------------------------------------
# Public MCP Endpoints
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=McpBalanceResponse)
def get_mcp_balance(api_key: ApiKey = Depends(get_api_key_auth)):
    """Check remaining quotas, active services, and limits for the authenticated API key."""
    return McpBalanceResponse(
        ok=True,
        key_name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_admin=api_key.is_admin,
        is_active=api_key.is_active,
        supplier_search={
            "allowed": api_key.allowed_supplier_search or api_key.is_admin,
            "quota": api_key.quota_supplier_search if not api_key.is_admin else "unlimited",
            "spent": api_key.spent_supplier_search,
            "remaining": max(0, api_key.quota_supplier_search - api_key.spent_supplier_search) if not api_key.is_admin else "unlimited",
        },
        exact_product={
            "allowed": api_key.allowed_exact_product or api_key.is_admin,
            "quota": api_key.quota_exact_product if not api_key.is_admin else "unlimited",
            "spent": api_key.spent_exact_product,
            "remaining": max(0, api_key.quota_exact_product - api_key.spent_exact_product) if not api_key.is_admin else "unlimited",
        },
        procurement_report={
            "allowed": api_key.allowed_procurement_report or api_key.is_admin,
            "quota": api_key.quota_procurement_report if not api_key.is_admin else "unlimited",
            "spent": api_key.spent_procurement_report,
            "remaining": max(0, api_key.quota_procurement_report - api_key.spent_procurement_report) if not api_key.is_admin else "unlimited",
        },
        rate_limit_per_minute=api_key.rate_limit_per_minute or 30,
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
    )


@router.post("/suppliers/search", response_model=McpSupplierSearchResponse)
async def mcp_supplier_search(
    req: McpSupplierSearchRequest,
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """
    Search direct suppliers, manufacturers, and distributors matching technical specification in real time.
    Returns contact details, verified websites, phone numbers, and optional commercial offer markdown.
    """
    settings = get_or_create_settings(db)
    remaining_quota = consume_quota(db, api_key, "supplier_search", count=1)

    spec_text = req.specification.strip()
    if req.city:
        spec_text = f"Регион поставки: {req.city.strip()}\n\n{spec_text}"

    clean_context = (await extract_supplier_search_context(settings, spec_text)) or spec_text[:20000]
    policy = req.search_policy.strip() if req.search_policy else "normal"
    if policy not in {"normal", "minprom_registry_priority", "minprom_registry_only"}:
        policy = "normal"

    try:
        with supplier_search_job_context(f"mcp_{api_key.id[:8]}"):
            accepted_rows, evidence = await discover_suppliers(
                settings=settings,
                context=clean_context,
                target=req.target_count,
                supplier_search_policy=policy,
            )
    except Exception as exc:
        logger.error("mcp_supplier_search_failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supplier search processing error: {str(exc)}",
        )

    supplier_items: List[McpSupplierItem] = []
    for row in accepted_rows:
        supplier_items.append(
            McpSupplierItem(
                company_name=str(row.get("company_name") or "").strip(),
                inn=str(row.get("inn") or "").strip(),
                region=str(row.get("region") or "").strip(),
                status=str(row.get("status") or "поставщик").strip(),
                product=str(row.get("product") or "").strip(),
                site=str(row.get("site") or "").strip(),
                email=str(row.get("email") or "").strip(),
                phone=str(row.get("phone") or "").strip(),
                match_level=str(row.get("match_level") or "exact").strip(),
                quality_score=int(row.get("quality_score") or 0),
                comments=str(row.get("comments") or "").strip(),
                evidence_url=str(row.get("evidence_url") or "").strip(),
            )
        )

    quote_markdown = None
    if req.include_quote_request and supplier_items:
        try:
            subject = str(evidence.get("subject") or "Поставка продукции по ТЗ").strip()
            quote_markdown = await build_quote_request_markdown_with_ai(
                settings,
                clean_context,
                subject=subject,
                procurement_profile=evidence.get("procurement_profile") if isinstance(evidence, dict) else {},
            )
        except Exception as exc:
            logger.warning("mcp_quote_request_gen_failed: %s", exc)

    return McpSupplierSearchResponse(
        ok=True,
        total_found=len(supplier_items),
        target_requested=req.target_count,
        suppliers=supplier_items,
        quote_request_markdown=quote_markdown,
        quota_remaining=remaining_quota,
        source_title=str(evidence.get("subject") or "").strip(),
    )


@router.post("/products/exact-analogs", response_model=McpExactProductResponse)
async def mcp_exact_product(
    req: McpExactProductRequest,
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """
    Deep technical specification analysis to uncover hidden original model, Form 2 parameters,
    and 2-4 verified equivalent analogues with compliance verification and DOCX report.
    """
    settings = get_or_create_settings(db)
    remaining_quota = consume_quota(db, api_key, "exact_product", count=1)

    spec_text = req.specification.strip()
    proc_title = req.procurement_title.strip()

    try:
        report: ExactProductReport = await analyze_exact_product(
            settings=settings,
            context=spec_text,
            procurement_title=proc_title,
        )
    except Exception as exc:
        logger.error("mcp_exact_product_failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Exact product analysis error: {str(exc)}",
        )

    # Save docx in public downloads storage
    docx_rel_url = None
    try:
        storage_dir = Path(config.storage_dir or "/root/projects/aipoisk-bot/storage") / "mcp_reports"
        storage_dir.mkdir(parents=True, exist_ok=True)
        doc_filename = f"exact_product_{secrets.token_hex(8)}.docx"
        doc_path = storage_dir / doc_filename
        write_exact_product_docx(doc_path, report, title=req.procurement_title or "Подбор товара и аналогов")
        public_url = getattr(settings, "public_base_url", "https://tenderlex.ru").rstrip("/")
        docx_rel_url = f"{public_url}/api/v1/mcp/downloads/{doc_filename}"
    except Exception as exc:
        logger.warning("mcp_docx_save_failed: %s", exc)

    positions_output: List[McpExactPositionItem] = []
    for pos in report.positions:
        specs_list = [
            McpSpecMatchItem(
                param_name=s.param_name,
                tz_requirement=s.tz_requirement,
                product_fact=s.product_fact,
                status=s.status,
                comment=s.comment,
            )
            for s in pos.specs_breakdown
        ]
        alts_list = [
            McpAlternativeItem(
                brand=alt.brand,
                model=alt.model,
                manufacturer=alt.manufacturer,
                confidence=alt.confidence,
                notes=alt.notes,
                inn=alt.inn,
                region=alt.region,
                specs_breakdown=[
                    McpSpecMatchItem(
                        param_name=alt_s.param_name,
                        tz_requirement=alt_s.tz_requirement,
                        product_fact=alt_s.product_fact,
                        status=alt_s.status,
                        comment=alt_s.comment,
                    )
                    for alt_s in alt.specs_breakdown
                ],
            )
            for alt in pos.alternative_brands
        ]
        positions_output.append(
            McpExactPositionItem(
                position_no=pos.position_no,
                name_in_tz=pos.name_in_tz,
                identified_brand=pos.identified_brand,
                identified_model=pos.identified_model,
                manufacturer=pos.manufacturer,
                confidence=pos.confidence,
                reasoning=pos.reasoning,
                specs_breakdown=specs_list,
                alternatives=alts_list,
            )
        )

    return McpExactProductResponse(
        ok=True,
        summary=report.summary,
        total_positions=report.total_positions,
        positions=positions_output,
        docx_download_url=docx_rel_url,
        quota_remaining=remaining_quota,
    )


@router.post("/procurements/analyze", response_model=McpProcurementAnalyzeResponse)
async def mcp_procurement_analyze(
    req: McpProcurementAnalyzeRequest,
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """
    Expert audit of procurement contracts, notice terms, national regime, guarantees, and legal pitfalls under 44-FZ and 223-FZ.
    """
    settings = get_or_create_settings(db)
    remaining_quota = consume_quota(db, api_key, "procurement_report", count=1)

    doc_text = req.document_text.strip()
    try:
        gen_result = await generate_procurement_report(settings, doc_text)
    except Exception as exc:
        logger.error("mcp_procurement_analyze_failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Procurement report analysis error: {str(exc)}",
        )

    return McpProcurementAnalyzeResponse(
        ok=True,
        report_markdown=gen_result.report,
        ai_model=gen_result.ai_model,
        quota_remaining=remaining_quota,
    )


@router.get("/downloads/{filename}")
def mcp_download_report(filename: str):
    """Safely serves generated MCP reports without path traversal risks."""
    safe_name = Path(filename).name
    if not safe_name.endswith((".docx", ".xlsx", ".pdf", ".zip")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file format")

    storage_dir = Path(config.storage_dir or "/root/projects/aipoisk-bot/storage") / "mcp_reports"
    file_path = (storage_dir / safe_name).resolve()

    if not str(file_path).startswith(str(storage_dir.resolve())) or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or expired")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ---------------------------------------------------------------------------
# Admin API Keys Management Schemas & Endpoints
# ---------------------------------------------------------------------------

class AdminApiKeyItem(BaseModel):
    id: str
    key_prefix: str
    name: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    is_admin: bool
    is_active: bool
    allowed_supplier_search: bool
    allowed_exact_product: bool
    allowed_procurement_report: bool
    quota_supplier_search: int
    quota_exact_product: int
    quota_procurement_report: int
    spent_supplier_search: int
    spent_exact_product: int
    spent_procurement_report: int
    rate_limit_per_minute: int
    notes: str
    created_at: str
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class AdminCreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    client_id: Optional[str] = None
    is_admin: bool = False
    allowed_supplier_search: bool = True
    allowed_exact_product: bool = True
    allowed_procurement_report: bool = True
    quota_supplier_search: int = Field(default=10, ge=0)
    quota_exact_product: int = Field(default=10, ge=0)
    quota_procurement_report: int = Field(default=10, ge=0)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=300)
    notes: str = ""
    expires_days: Optional[int] = Field(default=None, ge=1, le=3650)


class AdminCreateApiKeyResponse(BaseModel):
    ok: bool = True
    raw_api_key: str  # Returned only once upon creation
    item: AdminApiKeyItem


class AdminUpdateApiKeyRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    allowed_supplier_search: Optional[bool] = None
    allowed_exact_product: Optional[bool] = None
    allowed_procurement_report: Optional[bool] = None
    quota_supplier_search: Optional[int] = None
    quota_exact_product: Optional[int] = None
    quota_procurement_report: Optional[int] = None
    rate_limit_per_minute: Optional[int] = None
    notes: Optional[str] = None


class AdminTestApiKeyRequest(BaseModel):
    tool: str = Field(..., description="supplier_search | exact_product | procurement_report")
    query: str = Field(..., min_length=3, max_length=50000)
    search_policy: str = Field(default="normal", description="normal | minprom_registry_priority | minprom_registry_only")


def _serialize_api_key_item(k: ApiKey, client_name: Optional[str] = None) -> AdminApiKeyItem:
    return AdminApiKeyItem(
        id=k.id,
        key_prefix=k.key_prefix,
        name=k.name,
        client_id=k.client_id,
        client_name=client_name or (k.client.name if k.client else None),
        is_admin=k.is_admin,
        is_active=k.is_active,
        allowed_supplier_search=k.allowed_supplier_search,
        allowed_exact_product=k.allowed_exact_product,
        allowed_procurement_report=k.allowed_procurement_report,
        quota_supplier_search=k.quota_supplier_search,
        quota_exact_product=k.quota_exact_product,
        quota_procurement_report=k.quota_procurement_report,
        spent_supplier_search=k.spent_supplier_search,
        spent_exact_product=k.spent_exact_product,
        spent_procurement_report=k.spent_procurement_report,
        rate_limit_per_minute=k.rate_limit_per_minute or 30,
        notes=k.notes or "",
        created_at=k.created_at.isoformat() if k.created_at else "",
        expires_at=k.expires_at.isoformat() if k.expires_at else None,
        last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
    )


@admin_router.get("", response_model=List[AdminApiKeyItem])
def list_api_keys(
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """List all client and master API keys with usage statistics."""
    keys = db.query(ApiKey).order_by(ApiKey.is_admin.desc(), ApiKey.created_at.desc()).all()
    return [_serialize_api_key_item(k) for k in keys]


@admin_router.get("/master")
def get_or_create_master_key(
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """
    Returns the Master Admin API key details and active raw token.
    """
    master = db.query(ApiKey).filter(ApiKey.is_admin == True, ApiKey.is_active == True).first()
    if not master:
        raw_key, key_hash, key_prefix = generate_api_key(is_admin=True)
        master = ApiKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            secret_token=raw_key,
            name="Главный Master-ключ Администратора",
            is_admin=True,
            is_active=True,
            allowed_supplier_search=True,
            allowed_exact_product=True,
            allowed_procurement_report=True,
            quota_supplier_search=999999,
            quota_exact_product=999999,
            quota_procurement_report=999999,
            rate_limit_per_minute=120,
            notes="Мастер-ключ с полным безлимитным доступом ко всем модулям TenderLex",
        )
        db.add(master)
        db.commit()
        db.refresh(master)
        return {
            "ok": True,
            "raw_api_key": raw_key,
            "item": _serialize_api_key_item(master),
        }

    if not master.secret_token:
        raw_key, key_hash, key_prefix = generate_api_key(is_admin=True)
        master.key_hash = key_hash
        master.key_prefix = key_prefix
        master.secret_token = raw_key
        db.commit()
        db.refresh(master)

    return {
        "ok": True,
        "raw_api_key": master.secret_token,
        "item": _serialize_api_key_item(master),
    }


@admin_router.post("", response_model=AdminCreateApiKeyResponse)
def create_api_key(
    req: AdminCreateApiKeyRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Creates a new API key and returns the raw secret key once."""
    raw_key, key_hash, key_prefix = generate_api_key(is_admin=req.is_admin)

    expires_at = None
    if req.expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_days)

    client_name = None
    if req.client_id:
        client = db.query(Client).filter(Client.id == req.client_id).first()
        if client:
            client_name = client.name

    new_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        secret_token=raw_key if req.is_admin else None,
        name=req.name.strip(),
        client_id=req.client_id or None,
        is_admin=req.is_admin,
        is_active=True,
        allowed_supplier_search=req.allowed_supplier_search,
        allowed_exact_product=req.allowed_exact_product,
        allowed_procurement_report=req.allowed_procurement_report,
        quota_supplier_search=req.quota_supplier_search,
        quota_exact_product=req.quota_exact_product,
        quota_procurement_report=req.quota_procurement_report,
        rate_limit_per_minute=req.rate_limit_per_minute,
        notes=req.notes.strip(),
        expires_at=expires_at,
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)

    return AdminCreateApiKeyResponse(
        ok=True,
        raw_api_key=raw_key,
        item=_serialize_api_key_item(new_key, client_name),
    )


@admin_router.post("/{key_id}/regenerate")
def regenerate_api_key(
    key_id: str,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Regenerates the token for an existing API key and returns the new raw token."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    raw_key, key_hash, key_prefix = generate_api_key(is_admin=key.is_admin)
    key.key_hash = key_hash
    key.key_prefix = key_prefix
    if key.is_admin:
        key.secret_token = raw_key
    db.commit()
    db.refresh(key)

    return {
        "ok": True,
        "raw_api_key": raw_key,
        "item": _serialize_api_key_item(key),
    }


@admin_router.patch("/{key_id}", response_model=AdminApiKeyItem)
def update_api_key(
    key_id: str,
    req: AdminUpdateApiKeyRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Updates API key settings, quotas, allowed services, or status."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if req.name is not None:
        key.name = req.name.strip()
    if req.is_active is not None:
        key.is_active = req.is_active
    if req.allowed_supplier_search is not None:
        key.allowed_supplier_search = req.allowed_supplier_search
    if req.allowed_exact_product is not None:
        key.allowed_exact_product = req.allowed_exact_product
    if req.allowed_procurement_report is not None:
        key.allowed_procurement_report = req.allowed_procurement_report
    if req.quota_supplier_search is not None:
        key.quota_supplier_search = req.quota_supplier_search
    if req.quota_exact_product is not None:
        key.quota_exact_product = req.quota_exact_product
    if req.quota_procurement_report is not None:
        key.quota_procurement_report = req.quota_procurement_report
    if req.rate_limit_per_minute is not None:
        key.rate_limit_per_minute = req.rate_limit_per_minute
    if req.notes is not None:
        key.notes = req.notes.strip()

    db.commit()
    db.refresh(key)
    return _serialize_api_key_item(key)


@admin_router.delete("/{key_id}")
def delete_api_key(
    key_id: str,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Deletes an API key."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    db.delete(key)
    db.commit()
    return {"ok": True, "deleted_id": key_id}


@admin_router.post("/test")
async def test_api_tool(
    req: AdminTestApiKeyRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Executes a live test of an MCP tool directly from the admin panel."""
    settings = get_or_create_settings(db)
    start_time = time.time()

    if req.tool == "supplier_search":
        clean_ctx = (await extract_supplier_search_context(settings, req.query)) or req.query[:10000]
        policy = req.search_policy.strip() if req.search_policy else "normal"
        if policy not in {"normal", "minprom_registry_priority", "minprom_registry_only"}:
            policy = "normal"
        with supplier_search_job_context("admin_live_test"):
            accepted_rows, evidence = await discover_suppliers(
                settings=settings,
                context=clean_ctx,
                target=3,
                supplier_search_policy=policy,
            )
        duration = round(time.time() - start_time, 2)
        return {
            "ok": True,
            "tool": "supplier_search",
            "search_policy": policy,
            "duration_seconds": duration,
            "total_found": len(accepted_rows),
            "suppliers": accepted_rows[:5],
        }

    elif req.tool == "exact_product":
        report = await analyze_exact_product(
            settings=settings,
            context=req.query,
            procurement_title="Тестовый запрос из админ-панели",
        )
        duration = round(time.time() - start_time, 2)
        return {
            "ok": True,
            "tool": "exact_product",
            "duration_seconds": duration,
            "summary": report.summary,
            "total_positions": report.total_positions,
            "positions": [
                {
                    "identified_brand": p.identified_brand,
                    "identified_model": p.identified_model,
                    "confidence": p.confidence,
                    "specs_count": len(p.specs_breakdown),
                    "alternatives_count": len(p.alternative_brands),
                }
                for p in report.positions
            ],
        }

    elif req.tool == "procurement_report":
        gen_result = await generate_procurement_report(settings, req.query)
        duration = round(time.time() - start_time, 2)
        return {
            "ok": True,
            "tool": "procurement_report",
            "duration_seconds": duration,
            "ai_model": gen_result.ai_model,
            "report_snippet": gen_result.report[:1000],
        }

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown tool '{req.tool}'")
