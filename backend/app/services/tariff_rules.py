from __future__ import annotations

from decimal import Decimal

FIXED_QUANTITY_SOURCE_AUTO = "auto"
FIXED_QUANTITY_SOURCE_UNIT = "unit"
FIXED_QUANTITY_SOURCE_REGISTERED_RESIDENTS = "apartment_registered_residents"
FIXED_QUANTITY_SOURCE_APARTMENT_AREA_M2 = "apartment_area_m2"
FIXED_QUANTITY_SOURCES = {
    FIXED_QUANTITY_SOURCE_AUTO,
    FIXED_QUANTITY_SOURCE_UNIT,
    FIXED_QUANTITY_SOURCE_REGISTERED_RESIDENTS,
    FIXED_QUANTITY_SOURCE_APARTMENT_AREA_M2,
}

RESIDENT_BASED_SERVICE_KEYWORDS = (
    "вивіз сміття",
    "побутовими відходами",
)


def is_resident_based_service(service_name: str | None) -> bool:
    normalized = (service_name or "").strip().casefold()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in RESIDENT_BASED_SERVICE_KEYWORDS)


def _normalized_source(source: str | None) -> str:
    normalized = (source or "").strip().lower()
    if normalized in FIXED_QUANTITY_SOURCES:
        return normalized
    return FIXED_QUANTITY_SOURCE_AUTO


def _normalized_multiplier(multiplier: Decimal | int | float | str | None) -> Decimal:
    try:
        value = Decimal(str(multiplier if multiplier is not None else "1"))
    except Exception:
        value = Decimal("1")
    if value <= 0:
        return Decimal("1")
    return value


def fixed_charge_multiplier(
    service_name: str | None,
    registered_residents: int | None,
    apartment_area_m2: Decimal | int | float | str | None = None,
    quantity_source: str | None = None,
    quantity_multiplier: Decimal | int | float | str | None = None,
) -> Decimal:
    source = _normalized_source(quantity_source)
    multiplier = _normalized_multiplier(quantity_multiplier)
    residents = int(registered_residents or 1)
    if residents < 1:
        residents = 1
    area_m2 = Decimal("0")
    try:
        area_m2 = Decimal(str(apartment_area_m2 if apartment_area_m2 is not None else "0"))
    except Exception:
        area_m2 = Decimal("0")
    if area_m2 < 0:
        area_m2 = Decimal("0")
    if source == FIXED_QUANTITY_SOURCE_REGISTERED_RESIDENTS:
        return Decimal(residents) * multiplier
    if source == FIXED_QUANTITY_SOURCE_APARTMENT_AREA_M2:
        return area_m2 * multiplier
    if source == FIXED_QUANTITY_SOURCE_UNIT:
        return Decimal("1") * multiplier
    if is_resident_based_service(service_name):
        return Decimal(residents) * multiplier
    return Decimal("1") * multiplier
