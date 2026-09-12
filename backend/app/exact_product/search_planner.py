"""
Модуль планирования поиска и резолвинга параметров.
Реэкспорт функций из deep.py и product_brand_detector.py для обратной совместимости.
"""

from __future__ import annotations

from .deep import (
    _extract_relevant_spec_excerpts,
    _is_grounded_in_text,
    auto_fill_ai_recommendations,
    build_universal_negative_keywords,
    extract_key_search_parameters,
    extract_real_item_name,
    plan_exact_product_search,
    resolve_clarify_parameters,
    resolve_standards_parameters,
)
from .product_brand_detector import extract_clean_spec_text

__all__ = [
    "_extract_relevant_spec_excerpts",
    "_is_grounded_in_text",
    "auto_fill_ai_recommendations",
    "build_universal_negative_keywords",
    "extract_clean_spec_text",
    "extract_key_search_parameters",
    "extract_real_item_name",
    "plan_exact_product_search",
    "resolve_clarify_parameters",
    "resolve_standards_parameters",
]
