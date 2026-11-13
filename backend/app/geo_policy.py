"""Validation contract for delivery-radius searches.

This module is deliberately pure and local: creating a task must not make a
network geocoding request or silently turn a region into a delivery point.
"""

from __future__ import annotations

import re

from .supplier_locations import CITY_COORDINATES, normalize_city_name


# ``supplier_search_extra`` is the paid continuation of supplier search and
# carries the same delivery-radius contract.
GEO_SUPPORTED_MODES = frozenset({"supplier_search", "supplier_search_extra", "analysis_and_suppliers", "price_monitoring"})
GEO_MIN_RADIUS_KM = 10
GEO_MAX_RADIUS_KM = 5_000


def _display_city(value: str) -> str:
    return re.sub(r"^(?:г\.?|город)\s+", "", value.strip(), flags=re.IGNORECASE).strip()


def validate_geo_request(
    delivery_city: str | None,
    geo_radius_km: int | str | None,
    *,
    mode: str,
) -> tuple[str, int | None]:
    """Return a validated city/radius pair or raise ``ValueError``.

    A radius is an estimate from known city coordinates.  Therefore a vague
    region, an unknown point, or only one half of the pair is not a valid paid
    geo request.
    """
    city = _display_city(str(delivery_city or ""))
    raw_radius = "" if geo_radius_km is None else str(geo_radius_km).strip()
    if not city and not raw_radius:
        return "", None
    if not city or not raw_radius:
        raise ValueError("Город доставки и радиус указываются одновременно.")
    if mode not in GEO_SUPPORTED_MODES:
        raise ValueError("Этот режим не поддерживает приоритет в радиусе доставки.")
    # Reject fractional values instead of silently truncating them via int().
    if isinstance(geo_radius_km, float) and not geo_radius_km.is_integer():
        raise ValueError("Радиус доставки должен быть целым числом в километрах.")
    if not re.fullmatch(r"\d+", raw_radius):
        raise ValueError("Радиус доставки должен быть целым числом в километрах.")
    try:
        radius = int(raw_radius)
    except (TypeError, ValueError) as exc:
        raise ValueError("Радиус доставки должен быть целым числом в километрах.") from exc
    if not GEO_MIN_RADIUS_KM <= radius <= GEO_MAX_RADIUS_KM:
        raise ValueError(f"Радиус доставки должен быть от {GEO_MIN_RADIUS_KM} до {GEO_MAX_RADIUS_KM} км.")
    normalized = normalize_city_name(city)
    if normalized not in CITY_COORDINATES:
        raise ValueError("Точка доставки не распознана. Укажите город из адреса поставки.")
    return city, radius
