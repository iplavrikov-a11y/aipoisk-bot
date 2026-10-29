import pytest
from app.jobs import sanitize_customer_error
from app.supplier_search import (
    EmptyProcurementProfileError,
    _validate_procurement_profile_response,
)


def test_sanitize_ai_zero_items_error():
    raw_error = (
        "AI procurement profile extraction failed: AI returned profile with 0 items "
        "(raw keys: ['summary', 'items', 'excluded_terms']); tried models: "
        "Gemini:gemini-3.8-flash-high, Gemini:gemini-3.1-flash-lite, Gemini:gemini-3-flash"
    )
    sanitized = sanitize_customer_error(raw_error)
    assert "Gemini" not in sanitized
    assert "models" not in sanitized
    assert "raw keys" not in sanitized
    assert "В загруженных документах не найдены товары или спецификация" in sanitized
    assert "Пожалуйста, прикрепите файл со спецификацией" in sanitized


def test_sanitize_timeout_error():
    raw_error = "TimeoutError: LLM overall deadline exceeded; tried models: Gemini:gemini-3.8-flash-high"
    sanitized = sanitize_customer_error(raw_error)
    assert "Gemini" not in sanitized
    assert "Временная задержка сервиса анализа" in sanitized
    assert "Баланс не списан" in sanitized


def test_sanitize_raw_traceback():
    raw_error = "Traceback (most recent call last):\n  File 'test.py', line 12, in <module>\nKeyError: 'foo'"
    sanitized = sanitize_customer_error(raw_error)
    assert "Traceback" not in sanitized
    assert "KeyError" not in sanitized
    assert "Баланс не списан" in sanitized


def test_sanitize_minprom_empty():
    raw_error = "В реестре Минпромторга записи не найдены"
    sanitized = sanitize_customer_error(raw_error)
    assert "В реестре Минпромторга" in sanitized
    assert "обычный поиск поставщиков" in sanitized


def test_validate_procurement_profile_raises_clean_error():
    empty_json = '{"summary": "", "items": [], "excluded_terms": []}'
    with pytest.raises(EmptyProcurementProfileError) as exc_info:
        _validate_procurement_profile_response(empty_json)
    assert "В загруженных документах не найдены товары или спецификация" in str(exc_info.value)
