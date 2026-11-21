from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from .billing import KIND_MONEY, OP_GRANT
from .models import BillingTransaction, Client, Invoice, WebUser, YooKassaPayment, now_utc
from .yookassa_service import format_payment_method_type

MSK_TZ = timezone(timedelta(hours=3))
VALID_PERIODS = {"today", "7d", "30d", "all"}
VALID_TABS = {"all", "yookassa", "invoices", "manual"}
VALID_STATUSES = {"active", "all", "succeeded", "pending", "failed"}

INVOICE_LINK_WINDOW_SECONDS = 48 * 3600


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(dt: datetime | None) -> str | None:
    normalized = _to_utc(dt)
    return normalized.isoformat() if normalized else None


def _period_start_utc(period: str, reference_now: datetime) -> datetime | None:
    ref_utc = _to_utc(reference_now) or datetime.now(timezone.utc)
    if period == "today":
        msk_now = ref_utc.astimezone(MSK_TZ)
        msk_midnight = msk_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return msk_midnight.astimezone(timezone.utc)
    if period == "7d":
        return ref_utc - timedelta(days=7)
    if period == "30d":
        return ref_utc - timedelta(days=30)
    return None


def _in_period(dt: datetime | None, start_utc: datetime | None) -> bool:
    if start_utc is None:
        return True
    normalized = _to_utc(dt)
    if normalized is None:
        return False
    return normalized >= start_utc


def _yookassa_status_group(status: str) -> str:
    clean = str(status or "").strip().lower()
    if clean == "succeeded":
        return "succeeded"
    if clean in {"pending", "waiting_for_capture"}:
        return "pending"
    return "failed"


def _invoice_status_group(invoice: Invoice) -> tuple[str, bool, bool]:
    status = str(invoice.status or "").strip().lower()
    settlement = str(invoice.settlement_mode or "").strip().lower()
    is_manual_closed = status == "paid" and settlement == "manual_closed"
    is_paid_revenue = status == "paid" and not is_manual_closed
    if is_paid_revenue:
        return "succeeded", True, False
    if status in {"issued", "proof_submitted"}:
        return "pending", False, False
    return "failed", False, is_manual_closed


def _is_manual_refund(tx: BillingTransaction) -> bool:
    idem = str(tx.idempotency_key or "").strip().lower()
    note = str(tx.note or "").strip().lower()
    return idem.startswith("refund_") or note.startswith("возврат")


def _match_manual_txs_to_invoices(
    invoices: list[Invoice],
    manual_txs: list[BillingTransaction],
) -> dict[str, str]:
    """Return mapping tx.id -> invoice_number for admin grants already accounted by a paid invoice."""
    linked: dict[str, str] = {}
    txs_by_client: dict[str, list[BillingTransaction]] = {}
    for tx in manual_txs:
        if _is_manual_refund(tx):
            continue
        txs_by_client.setdefault(tx.client_id, []).append(tx)

    sync_invoices = [
        inv
        for inv in invoices
        if str(inv.status or "").lower() == "paid"
        and str(inv.settlement_mode or "").strip().lower() in {"manual_grant", "admin_grant_sync"}
    ]
    sync_invoices.sort(key=lambda inv: _to_utc(inv.paid_at or inv.created_at) or datetime.min.replace(tzinfo=timezone.utc))

    for inv in sync_invoices:
        inv_ref_dt = _to_utc(inv.paid_at) or _to_utc(inv.created_at)
        candidate_amounts = {
            int(inv.total_credit_rub or 0) * 100,
            int(inv.amount_rub or 0) * 100,
        }
        candidate_amounts.discard(0)
        if not candidate_amounts:
            continue

        best_tx: BillingTransaction | None = None
        best_delta: float | None = None
        for tx in txs_by_client.get(inv.client_id, []):
            if tx.id in linked:
                continue
            if int(tx.amount_kopeks or 0) not in candidate_amounts:
                continue
            tx_dt = _to_utc(tx.created_at)
            if inv_ref_dt and tx_dt:
                delta = abs((tx_dt - inv_ref_dt).total_seconds())
                if delta > INVOICE_LINK_WINDOW_SECONDS:
                    continue
            else:
                delta = 0.0
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_tx = tx

        if best_tx is not None:
            linked[best_tx.id] = inv.invoice_number

    return linked


def _format_client_contact(
    client_id: str,
    clients_by_id: dict[str, Client],
    web_users_by_client_id: dict[str, WebUser],
    *,
    fallback_name: str = "",
    fallback_email: str = "",
    fallback_phone: str = "",
    fallback_telegram: str = "",
) -> dict[str, Any]:
    client = clients_by_id.get(client_id)
    web_user = web_users_by_client_id.get(client_id)
    name = (
        (client.name if client and client.name else "")
        or (web_user.name if web_user and web_user.name else "")
        or fallback_name
        or "Удалённый клиент"
    )
    email = (web_user.email if web_user and web_user.email else "") or fallback_email or ""
    phone = (
        (client.phone if client and client.phone else "")
        or (web_user.phone if web_user and web_user.phone else "")
        or fallback_phone
        or ""
    )
    telegram = (
        (client.username if client and client.username else "")
        or (web_user.telegram_username if web_user and web_user.telegram_username else "")
        or fallback_telegram
        or ""
    ).lstrip("@")
    return {
        "client_id": client.id if client else None,
        "client_exists": client is not None,
        "client_number": client.client_number if client else None,
        "client_name": name,
        "client_email": email,
        "client_phone": phone,
        "client_telegram": telegram,
    }


def _matches_query(item: dict[str, Any], query_lower: str) -> bool:
    if not query_lower:
        return True
    parts = [
        item.get("title") or "",
        item.get("reference_id") or "",
        item.get("tariff_name") or "",
        item.get("client_name") or "",
        f"#{item['client_number']}" if item.get("client_number") else "",
        str(item.get("client_number") or ""),
        item.get("client_email") or "",
        item.get("client_phone") or "",
        item.get("client_telegram") or "",
        item.get("buyer_name") or "",
        item.get("buyer_inn") or "",
        item.get("buyer_email") or "",
        item.get("details_text") or "",
        item.get("payment_method_label") or "",
        item.get("linked_invoice_number") or "",
    ]
    haystack = " ".join(str(p) for p in parts if p).lower()
    return query_lower in haystack


def _matches_status_filter(item: dict[str, Any], status_filter: str) -> bool:
    if status_filter == "all":
        return True
    group = item["status_group"]
    if status_filter == "active":
        return group in {"succeeded", "pending"}
    return group == status_filter


def build_admin_payments_overview(
    db: Session,
    *,
    period: str = "all",
    tab: str = "all",
    status: str = "active",
    q: str = "",
    limit: int = 25,
    offset: int = 0,
    reference_now: datetime | None = None,
) -> dict[str, Any]:
    clean_period = period if period in VALID_PERIODS else "all"
    clean_tab = tab if tab in VALID_TABS else "all"
    clean_status = status if status in VALID_STATUSES else "active"
    clean_q = (q or "").strip()
    query_lower = clean_q.lower()

    ref_now = _to_utc(reference_now or now_utc()) or datetime.now(timezone.utc)
    start_utc = _period_start_utc(clean_period, ref_now)

    yk_rows = db.query(YooKassaPayment).all()
    inv_rows = db.query(Invoice).all()
    manual_rows = (
        db.query(BillingTransaction)
        .filter(
            BillingTransaction.kind == KIND_MONEY,
            BillingTransaction.operation == OP_GRANT,
            BillingTransaction.created_by == "admin",
        )
        .all()
    )

    client_ids = {
        cid
        for cid in (
            [p.client_id for p in yk_rows]
            + [inv.client_id for inv in inv_rows]
            + [tx.client_id for tx in manual_rows]
        )
        if cid
    }
    clients_by_id: dict[str, Client] = {}
    web_users_by_client_id: dict[str, WebUser] = {}
    if client_ids:
        for c in db.query(Client).filter(Client.id.in_(client_ids)).all():
            clients_by_id[c.id] = c
        for u in db.query(WebUser).filter(WebUser.client_id.in_(client_ids)).all():
            web_users_by_client_id[u.client_id] = u

    linked_manual_txs = _match_manual_txs_to_invoices(inv_rows, manual_rows)

    # Global count of proofs waiting for review (across all time so nothing is missed on 'today' filter)
    proof_pending_all_time = sum(1 for inv in inv_rows if str(inv.status or "").lower() == "proof_submitted")
    invoices_issued_all_time = sum(1 for inv in inv_rows if str(inv.status or "").lower() == "issued")

    summary = {
        "period": clean_period,
        "total_revenue_rub": 0,
        "total_paid_count": 0,
        "yookassa": {
            "succeeded_rub": 0,
            "succeeded_count": 0,
            "pending_count": 0,
            "canceled_count": 0,
        },
        "invoices": {
            "paid_rub": 0,
            "paid_count": 0,
            "issued_count": 0,
            "proof_submitted_count": 0,
            "manual_closed_count": 0,
            "cancelled_count": 0,
            "proof_submitted_all_time": proof_pending_all_time,
            "open_all_time": proof_pending_all_time + invoices_issued_all_time,
        },
        "manual": {
            "direct_rub": 0.0,
            "direct_count": 0,
            "refund_rub": 0.0,
            "refund_count": 0,
            "invoice_linked_rub": 0.0,
            "invoice_linked_count": 0,
            "total_rub": 0.0,
            "total_count": 0,
        },
    }

    normalized_items: list[dict[str, Any]] = []

    # 1. YooKassa payments
    for p in yk_rows:
        status_group = _yookassa_status_group(p.status)
        effective_dt = (
            (_to_utc(p.paid_at) or _to_utc(p.created_at))
            if status_group == "succeeded"
            else _to_utc(p.created_at)
        )
        if not _in_period(effective_dt, start_utc):
            continue

        amount_rub = int(p.amount_rub or 0)
        bonus_rub = int(p.bonus_rub or 0)
        total_credit_rub = int(p.total_credit_rub or (amount_rub + bonus_rub))

        if status_group == "succeeded":
            summary["yookassa"]["succeeded_rub"] += amount_rub
            summary["yookassa"]["succeeded_count"] += 1
        elif status_group == "pending":
            summary["yookassa"]["pending_count"] += 1
        else:
            summary["yookassa"]["canceled_count"] += 1

        contact = _format_client_contact(
            p.client_id,
            clients_by_id,
            web_users_by_client_id,
            fallback_phone=p.phone or "",
            fallback_telegram=p.telegram_username or "",
        )
        pm_raw = str(p.payment_method_type or "").strip()
        pm_label = format_payment_method_type(pm_raw) if pm_raw else "Способ не выбран"

        normalized_items.append(
            {
                "id": f"yk:{p.id}",
                "source": "yookassa",
                "include_in_all": True,
                "reference_id": p.payment_id,
                "title": f"ЮKassa #{p.payment_id[:8]}",
                "tariff_name": p.package_name or "Пополнение баланса",
                "status": p.status,
                "status_group": status_group,
                "amount_rub": amount_rub,
                "bonus_rub": bonus_rub,
                "total_credit_rub": total_credit_rub,
                "created_at": _iso_utc(p.created_at),
                "paid_at": _iso_utc(p.paid_at),
                "effective_at": _iso_utc(effective_dt),
                "_sort_dt": effective_dt or datetime.min.replace(tzinfo=timezone.utc),
                "payment_method_type": pm_raw,
                "payment_method_label": pm_label,
                "details_text": p.error_message or "",
                "buyer_name": "",
                "buyer_inn": "",
                "buyer_kpp": "",
                "buyer_email": "",
                "settlement_mode": "",
                "manual_category": "",
                "linked_invoice_number": "",
                "invoice": None,
                **contact,
            }
        )

    # 2. Invoices (B2B / bank transfer)
    for inv in inv_rows:
        status_group, is_paid_revenue, is_manual_closed = _invoice_status_group(inv)
        raw_status = str(inv.status or "").strip().lower()
        if raw_status == "paid":
            effective_dt = _to_utc(inv.paid_at) or _to_utc(inv.created_at)
        elif raw_status == "proof_submitted":
            effective_dt = _to_utc(inv.proof_submitted_at) or _to_utc(inv.created_at)
        else:
            effective_dt = _to_utc(inv.created_at)

        if not _in_period(effective_dt, start_utc):
            continue

        amount_rub = int(inv.amount_rub or 0)
        bonus_rub = int(inv.bonus_rub or 0)
        total_credit_rub = int(inv.total_credit_rub or (amount_rub + bonus_rub))

        if is_paid_revenue:
            summary["invoices"]["paid_rub"] += amount_rub
            summary["invoices"]["paid_count"] += 1
        elif raw_status == "proof_submitted":
            summary["invoices"]["proof_submitted_count"] += 1
        elif raw_status == "issued":
            summary["invoices"]["issued_count"] += 1
        elif is_manual_closed:
            summary["invoices"]["manual_closed_count"] += 1
        else:
            summary["invoices"]["cancelled_count"] += 1

        contact = _format_client_contact(
            inv.client_id,
            clients_by_id,
            web_users_by_client_id,
            fallback_name=inv.buyer_name or "",
            fallback_email=inv.buyer_email or "",
            fallback_phone=getattr(inv, "buyer_phone", "") or "",
            fallback_telegram=getattr(inv, "buyer_telegram", "") or "",
        )
        inv_dict = inv.to_dict()
        inv_dict["created_at"] = _iso_utc(inv.created_at)
        inv_dict["paid_at"] = _iso_utc(inv.paid_at)
        inv_dict["proof_submitted_at"] = _iso_utc(inv.proof_submitted_at)

        normalized_items.append(
            {
                "id": f"inv:{inv.id}",
                "source": "invoice",
                "include_in_all": True,
                "reference_id": inv.invoice_number,
                "title": inv.invoice_number,
                "tariff_name": inv.tariff_name or "Пополнение баланса",
                "status": inv.status,
                "status_group": status_group,
                "amount_rub": amount_rub,
                "bonus_rub": bonus_rub,
                "total_credit_rub": total_credit_rub,
                "created_at": _iso_utc(inv.created_at),
                "paid_at": _iso_utc(inv.paid_at),
                "effective_at": _iso_utc(effective_dt),
                "_sort_dt": effective_dt or datetime.min.replace(tzinfo=timezone.utc),
                "payment_method_type": "bank_transfer",
                "payment_method_label": "Безналичный счёт",
                "details_text": inv.proof_original_name or "",
                "buyer_name": inv.buyer_name or "",
                "buyer_inn": inv.buyer_inn or "",
                "buyer_kpp": inv.buyer_kpp or "",
                "buyer_email": inv.buyer_email or "",
                "settlement_mode": str(inv.settlement_mode or ""),
                "manual_category": "",
                "linked_invoice_number": "",
                "invoice": inv_dict,
                **contact,
            }
        )

    # 3. Manual admin grants (BillingTransaction)
    for tx in manual_rows:
        effective_dt = _to_utc(tx.created_at)
        if not _in_period(effective_dt, start_utc):
            continue

        rub_value = round(int(tx.amount_kopeks or 0) / 100.0, 2)
        linked_inv_num = linked_manual_txs.get(tx.id, "")
        if linked_inv_num:
            manual_category = "invoice_linked"
            status_group = "failed"  # excluded from active/all to avoid double counting; still shown in manual tab
            summary["manual"]["invoice_linked_rub"] = round(summary["manual"]["invoice_linked_rub"] + rub_value, 2)
            summary["manual"]["invoice_linked_count"] += 1
        elif _is_manual_refund(tx):
            manual_category = "refund"
            status_group = "failed"
            summary["manual"]["refund_rub"] = round(summary["manual"]["refund_rub"] + rub_value, 2)
            summary["manual"]["refund_count"] += 1
        else:
            manual_category = "direct_topup"
            status_group = "succeeded"
            summary["manual"]["direct_rub"] = round(summary["manual"]["direct_rub"] + rub_value, 2)
            summary["manual"]["direct_count"] += 1

        summary["manual"]["total_rub"] = round(summary["manual"]["total_rub"] + rub_value, 2)
        summary["manual"]["total_count"] += 1

        contact = _format_client_contact(tx.client_id, clients_by_id, web_users_by_client_id)
        normalized_items.append(
            {
                "id": f"tx:{tx.id}",
                "source": "manual",
                "include_in_all": manual_category == "direct_topup",
                "reference_id": tx.id[:8],
                "title": "Ручное начисление",
                "tariff_name": (
                    "Возврат на баланс"
                    if manual_category == "refund"
                    else (f"По счёту {linked_inv_num}" if linked_inv_num else "Начислено администратором")
                ),
                "status": manual_category,
                "status_group": status_group,
                "amount_rub": rub_value,
                "bonus_rub": 0,
                "total_credit_rub": rub_value,
                "created_at": _iso_utc(tx.created_at),
                "paid_at": _iso_utc(tx.created_at),
                "effective_at": _iso_utc(effective_dt),
                "_sort_dt": effective_dt or datetime.min.replace(tzinfo=timezone.utc),
                "payment_method_type": "admin_grant",
                "payment_method_label": "Ручное начисление",
                "details_text": tx.note or "",
                "buyer_name": "",
                "buyer_inn": "",
                "buyer_kpp": "",
                "buyer_email": "",
                "settlement_mode": "",
                "manual_category": manual_category,
                "linked_invoice_number": linked_inv_num,
                "invoice": None,
                **contact,
            }
        )

    summary["total_revenue_rub"] = summary["yookassa"]["succeeded_rub"] + summary["invoices"]["paid_rub"]
    summary["total_paid_count"] = summary["yookassa"]["succeeded_count"] + summary["invoices"]["paid_count"]

    # Search filter first (for consistent facet counts across tabs & statuses)
    q_filtered = [item for item in normalized_items if _matches_query(item, query_lower)]

    def _for_tab(items: list[dict[str, Any]], target_tab: str) -> list[dict[str, Any]]:
        if target_tab == "yookassa":
            return [i for i in items if i["source"] == "yookassa"]
        if target_tab == "invoices":
            return [i for i in items if i["source"] == "invoice"]
        if target_tab == "manual":
            return [i for i in items if i["source"] == "manual"]
        return [i for i in items if i["include_in_all"]]

    current_tab_items = _for_tab(q_filtered, clean_tab)

    # Status facet counts for current tab
    status_counts = {
        "active": sum(1 for i in current_tab_items if _matches_status_filter(i, "active")),
        "all": len(current_tab_items),
        "succeeded": sum(1 for i in current_tab_items if i["status_group"] == "succeeded"),
        "pending": sum(1 for i in current_tab_items if i["status_group"] == "pending"),
        "failed": sum(1 for i in current_tab_items if i["status_group"] == "failed"),
    }

    # Tab facet counts under current status filter (except manual tab when active -> show total or matching?)
    # Keeping tab_counts under the active status filter matches what user sees when switching tabs.
    tab_counts = {
        "all": sum(1 for i in _for_tab(q_filtered, "all") if _matches_status_filter(i, clean_status)),
        "all_active": sum(1 for i in _for_tab(q_filtered, "all") if _matches_status_filter(i, "active")),
        "yookassa": sum(1 for i in _for_tab(q_filtered, "yookassa") if _matches_status_filter(i, clean_status)),
        "invoices": sum(1 for i in _for_tab(q_filtered, "invoices") if _matches_status_filter(i, clean_status)),
        "manual": sum(1 for i in _for_tab(q_filtered, "manual") if _matches_status_filter(i, clean_status)),
        "yookassa_total": len(_for_tab(q_filtered, "yookassa")),
        "invoices_total": len(_for_tab(q_filtered, "invoices")),
        "manual_total": len(_for_tab(q_filtered, "manual")),
    }

    filtered = [i for i in current_tab_items if _matches_status_filter(i, clean_status)]
    filtered.sort(key=lambda i: (i["_sort_dt"], i["id"]), reverse=True)

    total = len(filtered)
    page_items = []
    for item in filtered[offset : offset + limit]:
        clean_item = {k: v for k, v in item.items() if not k.startswith("_") and k != "include_in_all"}
        page_items.append(clean_item)

    return {
        "summary": summary,
        "tab_counts": tab_counts,
        "status_counts": status_counts,
        "items": page_items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
