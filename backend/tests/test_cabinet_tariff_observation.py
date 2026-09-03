from datetime import UTC, datetime
from decimal import Decimal

from app.models import ConnectionChargeLine
from app.workers.tariff_auto_check import _apply_cabinet_tariff_observation


def test_records_cabinet_value_without_touching_price_per_unit():
    line = ConnectionChargeLine(price_per_unit=Decimal("111.00"))
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(line, candidate_value=Decimal("120.5"), checked_at=checked_at)

    assert line.price_per_unit == Decimal("111.00")
    assert line.cabinet_price_per_unit == Decimal("120.5000")
    assert line.cabinet_checked_at == checked_at


def test_records_cabinet_value_even_when_lower_than_current_price():
    line = ConnectionChargeLine(price_per_unit=Decimal("200.00"))
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(line, candidate_value=Decimal("50"), checked_at=checked_at)

    assert line.price_per_unit == Decimal("200.00")
    assert line.cabinet_price_per_unit == Decimal("50.0000")
    assert line.cabinet_checked_at == checked_at
