from decimal import Decimal

from app.models import Apartment, ConnectionChargeLine
from app.workers.tariff_auto_check import _current_line_total


def test_fixed_price_line_ignores_registered_residents():
    apartment = Apartment(registered_residents=3)
    line = ConnectionChargeLine(
        price_per_unit=Decimal("185.00"),
        quantity_source="fixed_1",
        quantity_multiplier=Decimal("1.000"),
    )
    assert _current_line_total(apartment, line) == Decimal("185.00")


def test_per_resident_line_multiplies_by_registered_residents():
    apartment = Apartment(registered_residents=3)
    line = ConnectionChargeLine(
        price_per_unit=Decimal("60.00"),
        quantity_source="registered_residents",
        quantity_multiplier=Decimal("1.000"),
    )
    assert _current_line_total(apartment, line) == Decimal("180.00")


def test_zero_quantity_falls_back_to_one_unit():
    apartment = Apartment(registered_residents=0)
    line = ConnectionChargeLine(
        price_per_unit=Decimal("50.00"),
        quantity_source="registered_residents",
        quantity_multiplier=Decimal("1.000"),
    )
    assert _current_line_total(apartment, line) == Decimal("50.00")
