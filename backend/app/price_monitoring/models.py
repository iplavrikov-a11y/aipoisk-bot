from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SupplierQuote:
    company_name: str
    inn: Optional[str] = None
    kpp: Optional[str] = None
    contacts: Optional[str] = None
    price_rub: float = 0.0              # Итоговая нормализованная цена в единицах заказчика
    raw_price_rub: float = 0.0          # Исходная цена на сайте до пересчета
    unit: str = "шт"                   # Единица измерения заказчика
    site_unit: str = ""                # Исходная единица измерения на сайте
    url: str = ""
    is_price_found: bool = True
    conversion_comment: str = ""        # Пояснение перерасчета (например, "2400 ₽ за баллон 50л -> 114.29 ₽/кг")
    comment: str = ""
    is_outlier: bool = False           # Флаг сильного расхождения цены
    evidence_level: str = "unknown"   # "page_content", "search_snippet", "unknown"
    retrieved_at: str = ""
    source_excerpt: str = ""
    supplier_city: str = ""
    supplier_distance_km: Optional[int] = None
    supplier_distance_radius_km: Optional[int] = None
    supplier_distance_radius_status: str = ""
    supplier_distance_within_radius: Optional[bool] = None
    supplier_location_source: str = ""
    supplier_location_confidence: str = "unknown"


@dataclass
class ItemPriceResult:
    row_number: int
    raw_name: str
    clean_name: str
    unit: str
    quotes: List[SupplierQuote] = field(default_factory=list)
    status: str = "pending"  # "found", "not_found", "error"
    not_found_reason: str = ""
    search_diagnostics: Dict[str, Any] = field(default_factory=dict)
    position_id: str = ""
    source_position_no: Optional[int] = None
    source_file: str = ""
    source_sheet: str = ""
    source_row: Optional[int] = None
    source_excerpt: str = ""
    quantity: str = ""
    requirements: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_prices(self) -> bool:
        return any(q.price_rub > 0 and not q.is_outlier for q in self.quotes)

    @property
    def best_price(self) -> Optional[float]:
        clean = [q.price_rub for q in self.quotes if q.price_rub > 0 and not q.is_outlier]
        if clean:
            return min(clean)
        valid = [q.price_rub for q in self.quotes if q.price_rub > 0]
        return min(valid) if valid else None


@dataclass
class BatchMonitoringResult:
    job_id: str
    total_positions: int
    found_positions: int
    not_found_positions: int
    price_per_position_rub: float
    total_charged_rub: float
    items: List[ItemPriceResult] = field(default_factory=list)
    output_excel_path: str = ""
    yandex_requests_count: int = 0
    yandex_cost_rub: float = 0.0
