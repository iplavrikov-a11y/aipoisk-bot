import pytest

from app.bot import _mode_to_billing_kind
from app.billing import (
    KIND_EXACT_PRODUCT, KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH, KIND_SUPPLIER_SEARCH_EXTRA,
)


@pytest.mark.parametrize('mode,expected', [
    ('supplier_search', KIND_SUPPLIER_SEARCH),
    ('supplier_search_extra', KIND_SUPPLIER_SEARCH_EXTRA),
    ('exact_product', KIND_EXACT_PRODUCT),
    ('procurement_report', KIND_PROCUREMENT_REPORT),
    ('analysis_and_suppliers', KIND_PROCUREMENT_REPORT),
])
def test_low_balance_notice_resolves_service_kind_without_undefined_mode(mode, expected):
    assert _mode_to_billing_kind(mode) == expected
