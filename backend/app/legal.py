from __future__ import annotations

from sqlalchemy.orm import Session

from .models import LegalAcceptance

LEGAL_VERSION = "2026-07-17"
LEGAL_DOCUMENT_TERMS = "terms"
LEGAL_DOCUMENT_PERSONAL_DATA = "personal_data"
LEGAL_DOCUMENTS = (LEGAL_DOCUMENT_TERMS, LEGAL_DOCUMENT_PERSONAL_DATA)
LEGAL_BASE_URL = "https://tenderlex.ru"
LEGAL_INDEX_URL = f"{LEGAL_BASE_URL}/legal"
TERMS_URL = f"{LEGAL_BASE_URL}/terms"
PRIVACY_URL = f"{LEGAL_BASE_URL}/privacy"
PERSONAL_DATA_URL = f"{LEGAL_BASE_URL}/personal-data"


def record_legal_acceptance(
    db: Session,
    *,
    subject_type: str,
    subject_id: str,
    document_type: str,
    source: str,
    document_version: str = LEGAL_VERSION,
    ip_address: str = "",
    user_agent: str = "",
) -> LegalAcceptance:
    if document_type not in LEGAL_DOCUMENTS:
        raise ValueError("Unsupported legal document type")
    subject_type = str(subject_type or "").strip()[:40]
    subject_id = str(subject_id or "").strip()[:64]
    if not subject_type or not subject_id:
        raise ValueError("Legal acceptance subject is required")
    existing = (
        db.query(LegalAcceptance)
        .filter(LegalAcceptance.subject_type == subject_type)
        .filter(LegalAcceptance.subject_id == subject_id)
        .filter(LegalAcceptance.document_type == document_type)
        .filter(LegalAcceptance.document_version == document_version)
        .first()
    )
    if existing:
        return existing
    acceptance = LegalAcceptance(
        subject_type=subject_type,
        subject_id=subject_id,
        document_type=document_type,
        document_version=document_version,
        source=str(source or "")[:40],
        ip_address=str(ip_address or "")[:80],
        user_agent=str(user_agent or "")[:1000],
    )
    db.add(acceptance)
    db.flush()
    return acceptance


def accepted_legal_documents(
    db: Session,
    *,
    subject_type: str,
    subject_id: str,
    document_version: str = LEGAL_VERSION,
) -> set[str]:
    rows = (
        db.query(LegalAcceptance.document_type)
        .filter(LegalAcceptance.subject_type == subject_type)
        .filter(LegalAcceptance.subject_id == str(subject_id))
        .filter(LegalAcceptance.document_version == document_version)
        .all()
    )
    return {str(row[0]) for row in rows}


def has_current_legal_acceptances(db: Session, *, subject_type: str, subject_id: str) -> bool:
    return set(LEGAL_DOCUMENTS).issubset(
        accepted_legal_documents(db, subject_type=subject_type, subject_id=subject_id)
    )
