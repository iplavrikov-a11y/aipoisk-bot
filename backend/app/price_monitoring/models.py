from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


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
