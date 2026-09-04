from decimal import Decimal

from app.models import ConnectionChargeLine
from app.workers.tariff_auto_check import _borrow_estimate_from_previous_line


def test_returns_none_when_no_previous_line():
    assert _borrow_estimate_from_previous_line(None) is None


def test_returns_none_when_previous_line_has_no_cabinet_value():
    previous_line = ConnectionChargeLine(price_per_unit=Decimal("100.00"))
    assert _borrow_estimate_from_previous_line(previous_line) is None


def test_borrows_previous_line_cabinet_value():
    previous_line = ConnectionChargeLine(price_per_unit=Decimal("100.00"))
    previous_line.cabinet_price_per_unit = Decimal("334.4950")
    assert _borrow_estimate_from_previous_line(previous_line) == Decimal("334.4950")


def test_borrows_even_when_previous_line_was_itself_an_estimate():
    previous_line = ConnectionChargeLine(price_per_unit=Decimal("100.00"))
    previous_line.cabinet_price_per_unit = Decimal("300.0000")
    previous_line.cabinet_price_is_estimated = True
    assert _borrow_estimate_from_previous_line(previous_line) == Decimal("300.0000")
