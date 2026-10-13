from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SupplierQuote:
    company_name: str
    inn: Optional[str] = None
    kpp: Optional[str] = None
    contacts: Optional[str] = None
    price_rub: float = 0.0
    unit: str = "шт"
    url: str = ""
    is_price_found: bool = True
    comment: str = ""


@dataclass
class ItemPriceResult:
    row_number: int
    raw_name: str
    clean_name: str
    unit: str
    quotes: List[SupplierQuote] = field(default_factory=list)
    status: str = "pending"  # "found", "not_found", "error"

    @property
    def has_prices(self) -> bool:
        return any(q.price_rub > 0 for q in self.quotes)

    @property
    def best_price(self) -> Optional[float]:
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
