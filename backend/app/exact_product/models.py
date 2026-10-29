from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional

GISP_PRODUCT_REGISTRY_URL = "https://gisp.gov.ru/pp719v2/pub/prod/"
MAX_EXACT_POSITIONS_PER_JOB: int = 100
MAX_YANDEX_QUERIES_PER_JOB: int = 20


@dataclass
class SpecParameterMatch:
    param_name: str
    tz_requirement: str
    product_fact: str
    status: str = "match"  # "match" | "mismatch" | "clarify"
    comment: str = ""
    source_url: str = ""
    source_doc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GispRegistryMatch:
    registry_number: str
    manufacturer: str
    product: str
    inn: str = ""
    conclusion_number: str = ""
    valid_until: str = ""
    source_url: str = GISP_PRODUCT_REGISTRY_URL
    matched: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AlternativeProduct:
    brand: str
    model: str
    manufacturer: str
    confidence: float = 0.90
    notes: str = ""
    specs_breakdown: list[SpecParameterMatch] = field(default_factory=list)
    gisp_match: Optional[GispRegistryMatch] = None
    source_url: str = ""
    datasheet_url: str = ""
    inn: str = ""
    region: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["specs_breakdown"] = [
            s.to_dict() if isinstance(s, SpecParameterMatch) else s
            for s in self.specs_breakdown
        ]
        data["gisp_match"] = self.gisp_match.to_dict() if self.gisp_match else None
        return data


@dataclass
class ExactProductPosition:
    position_no: int
    name_in_tz: str
    identified_brand: str
    identified_model: str
    manufacturer: str
    confidence: float
    reasoning: str
    specs_breakdown: list[SpecParameterMatch] = field(default_factory=list)
    alternative_brands: list[AlternativeProduct] = field(default_factory=list)
    gisp_match: Optional[GispRegistryMatch] = None
    source_url: str = ""
    datasheet_url: str = ""
    inn: str = ""
    region: str = ""
    position_id: str = ""
    status: str = "found"
    error: str = ""

    @property
    def is_resolved(self) -> bool:
        if self.status == "found":
            return True
        if self.status in ("not_found", "error") and not self.identified_model and not self.alternative_brands:
            return False
        if bool((self.identified_model or "").strip() or (self.identified_brand or "").strip()):
            return True
        if bool(self.alternative_brands):
            return True
        if self.gisp_match and getattr(self.gisp_match, "registry_number", None):
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["is_resolved"] = self.is_resolved
        data["specs_breakdown"] = [
            s.to_dict() if isinstance(s, SpecParameterMatch) else s
            for s in self.specs_breakdown
        ]
        data["alternative_brands"] = [
            a.to_dict() if isinstance(a, AlternativeProduct) else a
            for a in self.alternative_brands
        ]
        data["gisp_match"] = self.gisp_match.to_dict() if self.gisp_match else None
        return data


def is_exact_position_resolved(pos: Any) -> bool:
    if pos is None:
        return False
    if hasattr(pos, "is_resolved"):
        return bool(pos.is_resolved)
    if isinstance(pos, dict):
        status = pos.get("status", "found")
        if status == "found":
            return True
        if status in ("not_found", "error") and not pos.get("identified_model") and not pos.get("alternative_brands"):
            return False
        if bool((pos.get("identified_model") or "").strip() or (pos.get("identified_brand") or "").strip()):
            return True
        if bool(pos.get("alternative_brands")):
            return True
        gisp = pos.get("gisp_match")
        if gisp and (isinstance(gisp, dict) and gisp.get("registry_number") or getattr(gisp, "registry_number", None)):
            return True
        return False
    status = getattr(pos, "status", "found")
    if status == "found":
        return True
    if status in ("not_found", "error") and not getattr(pos, "identified_model", "") and not getattr(pos, "alternative_brands", None):
        return False
    if bool((getattr(pos, "identified_model", "") or "").strip() or (getattr(pos, "identified_brand", "") or "").strip()):
        return True
    if bool(getattr(pos, "alternative_brands", None)):
        return True
    gisp = getattr(pos, "gisp_match", None)
    if gisp and getattr(gisp, "registry_number", None):
        return True
    return False



@dataclass
class ExactProductReport:
    procurement_title: str
    total_positions: int
    positions: list[ExactProductPosition] = field(default_factory=list)
    summary: str = ""
    disclaimer: str = (
        "Отчёт сформирован на основе сопоставления технического задания с открытыми веб-источниками, "
        "каталогами производителей, PDF-паспортами изделий и реестром Минпромторга РФ (ГИСП). "
        "Степень подтверждения каждого параметра указана отдельно. Неподтверждённые характеристики "
        "требуют уточнения; наличие отчёта само по себе не подтверждает соответствие товара условиям закупки."
    )
    yandex_requests_count: int = 0
    yandex_cost_rub: float = 0.0
    web_sources: list[str] = field(default_factory=list)
    verified_documents: list[dict[str, Any]] = field(default_factory=list)
    search_metrics_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "procurement_title": self.procurement_title,
            "total_positions": self.total_positions,
            "positions": [p.to_dict() for p in self.positions],
            "summary": self.summary,
            "disclaimer": self.disclaimer,
            "yandex_requests_count": self.yandex_requests_count,
            "yandex_cost_rub": self.yandex_cost_rub,
            "web_sources": self.web_sources,
            "verified_documents": self.verified_documents,
            "search_metrics_available": self.search_metrics_available,
        }


MAX_EXACT_POSITIONS_PER_JOB: int = 100
MAX_YANDEX_QUERIES_PER_JOB: int = 20

