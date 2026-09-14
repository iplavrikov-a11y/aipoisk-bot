from __future__ import annotations

# AI & search helpers for compatibility and patching in tests
from .llm_bridge import call_llm
from ..supplier_search import _search_with_yandex, _yandex_credentials
from .docx_report import write_exact_product_docx
from .evidence_miner import mine_tender_evidence
from .fetcher import (
    candidate_domain_resolves_fast,
    extract_pdf_links_from_html,
    fetch_batch_web_documents,
    fetch_web_or_pdf_document,
)
from .matcher import (
    _rank_search_candidates,
    detect_exact_products_characteristic_first,
    find_candidate_models_characteristic_first,
)
from .minprom import (
    _GISP_COMPAT_CACHE,
    _is_generic_gisp_term,
    _is_gisp_product_compatible,
    check_model_in_gisp_text,
    detect_minprom_registry_requirement,
    extract_conclusion_number,
    find_minprom_gisp_match,
    find_minprom_gisp_match_ai,
    find_minprom_registry_matches_ai,
    is_gisp_product_compatible_ai,
    match_brand_in_gisp,
)
from .models import (
    MAX_EXACT_POSITIONS_PER_JOB,
    MAX_YANDEX_QUERIES_PER_JOB,
    AlternativeProduct,
    ExactProductPosition,
    ExactProductReport,
    GispRegistryMatch,
    SpecParameterMatch,
)
from .pipeline import (
    analyze_exact_product,
    auto_rotate_clean_analogs,
    drop_nonconforming_analogs,
    sanitize_shops_from_positions,
)
from .search_planner import (
    _extract_relevant_spec_excerpts,
    _is_grounded_in_text,
    auto_fill_ai_recommendations,
    build_universal_negative_keywords,
    extract_clean_spec_text,
    extract_key_search_parameters,
    extract_real_item_name,
    plan_exact_product_search,
    resolve_clarify_parameters,
    resolve_standards_parameters,
)
from .validation import (
    _is_placeholder_brand_or_model,
    comment_says_deviation,
    compute_spec_compliance,
    extract_standards_from_text,
    neutralize_alt_mentions_in_comments,
    recompute_and_reconcile_positions,
    validate_exact_products,
    validate_stored_products,
)
from .xlsx_report import write_exact_product_xlsx

__all__ = [
    # Models & Constants
    "AlternativeProduct",
    "ExactProductPosition",
    "ExactProductReport",
    "GispRegistryMatch",
    "SpecParameterMatch",
    "MAX_EXACT_POSITIONS_PER_JOB",
    "MAX_YANDEX_QUERIES_PER_JOB",
    # Main pipeline
    "analyze_exact_product",
    "auto_rotate_clean_analogs",
    "drop_nonconforming_analogs",
    "sanitize_shops_from_positions",
    # Reports
    "write_exact_product_docx",
    "write_exact_product_xlsx",
    # Minprom
    "check_model_in_gisp_text",
    "detect_minprom_registry_requirement",
    "extract_conclusion_number",
    "find_minprom_gisp_match",
    "find_minprom_gisp_match_ai",
    "find_minprom_registry_matches_ai",
    "is_gisp_product_compatible_ai",
    "match_brand_in_gisp",
    "_is_generic_gisp_term",
    "_is_gisp_product_compatible",
    "_GISP_COMPAT_CACHE",
    # Validation
    "_is_placeholder_brand_or_model",
    "comment_says_deviation",
    "compute_spec_compliance",
    "extract_standards_from_text",
    "neutralize_alt_mentions_in_comments",
    "recompute_and_reconcile_positions",
    "validate_exact_products",
    "validate_stored_products",
    # Fetcher
    "candidate_domain_resolves_fast",
    "extract_pdf_links_from_html",
    "fetch_batch_web_documents",
    "fetch_web_or_pdf_document",
    # Search Planner & Clarify
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
    # Matcher & Evidence
    "_rank_search_candidates",
    "detect_exact_products_characteristic_first",
    "find_candidate_models_characteristic_first",
    "mine_tender_evidence",
    # AI & Search functions
    "call_llm",
    "_search_with_yandex",
    "_yandex_credentials",
]
