from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import encrypt_text
from app.db.base import Base
from app.models import (
    Apartment,
    ApartmentServiceConnection,
    ChargeLineKind,
    ConnectionChargeLine,
    QuantitySource,
    ServiceCalculationKind,
    ServiceCatalog,
    UnitType,
)
from app.workers.tariff_auto_check import AutomationBindingContext, _is_gas_ua_setting, _run_gas_ua


def _setting(*, adapter_code=None, provider_company=None, cabinet_url=None, service_code=None):
    provider = SimpleNamespace(adapter_code=adapter_code) if adapter_code is not None else None
    return SimpleNamespace(
        provider=provider,
        provider_company=provider_company,
        cabinet_url=cabinet_url,
        service_code=service_code,
    )


def test_matches_by_adapter_code():
    assert _is_gas_ua_setting(_setting(adapter_code="gas_ua_supply")) is True


def test_matches_by_cabinet_url_fallback():
    assert _is_gas_ua_setting(_setting(cabinet_url="https://my.gas.ua/login")) is True


def test_does_not_match_unrelated_provider():
    assert _is_gas_ua_setting(_setting(adapter_code="atp0928_if", cabinet_url="https://atp0928.if.ua")) is False


def test_does_not_match_empty_setting():
    assert _is_gas_ua_setting(_setting()) is False


# --- _run_gas_ua status-transition tests -----------------------------------
#
# These exercise the real dispatch function against a lightweight in-memory
# SQLite DB, mocking only the network call (_fetch_gas_ua_home_html), so the
# actual login->parse->apply-observation pipeline in _run_gas_ua runs for
# real, including its DB lookup of the active ConnectionChargeLine via
# _service_charge_line_for_period.

_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)

# Local time inside the run window; the previous calendar month (2026-08) is
# the period _run_gas_ua should resolve to and write the observation onto.
_NOW_UTC = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
_LOCAL_NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

# Real captured markup shape (see test_gas_ua_parsing.py), with a price that
# has no rounding ambiguity at 4 decimal places.
_VALID_HTML = (
    '<personal-accounts-dropdown class_names="nav-item" '
    'user_info="{&quot;kodr&quot;:&quot;801685457&quot;,&quot;peracc&quot;:&quot;160026427&quot;,'
    '&quot;pay_lastsum&quot;:&quot;2451.85&quot;,&quot;beforelimit_price&quot;:&quot;12.3456&quot;,'
    '&quot;afterlimit_price&quot;:&quot;12.3456&quot;,&quot;single_price&quot;:&quot;12.3456&quot;,'
    '&quot;priv_percent&quot;:&quot;&quot;}" />'
)

# Real-looking HTML that does not contain the personal-accounts-dropdown
# component the parser regex looks for, so parsing returns None.
_HTML_WITHOUT_PRICE = "<html><body><div class='dashboard'>no price widget here</div></body></html>"


def _setup_gas_ua_db(*, initial_price_per_unit: Decimal = Decimal("7.5000")):
    Base.metadata.create_all(bind=_ENGINE)
    db = _SessionLocal()

    apartment = Apartment(code="GAS1", address="Gas Test Address")
    db.add(apartment)
    db.flush()

    catalog = ServiceCatalog(
        code="gas_supply",
        name="Газопостачання",
        calculation_kind=ServiceCalculationKind.metered,
        unit_name=UnitType.m3,
    )
    db.add(catalog)
    db.flush()

    connection = ApartmentServiceConnection(
        apartment_id=apartment.id,
        service_catalog_id=catalog.id,
        started_at=date(2026, 1, 1),
        status="active",
    )
    db.add(connection)
    db.flush()

    charge_line = ConnectionChargeLine(
        connection_id=connection.id,
        line_kind=ChargeLineKind.meter_register,
        label="Газ",
        unit_name=UnitType.m3,
        price_per_unit=initial_price_per_unit,
        quantity_source=QuantitySource.derived_consumption,
        effective_from=date(2026, 1, 1),
        is_active=True,
    )
    db.add(charge_line)
    db.commit()
    db.refresh(charge_line)

    setting = AutomationBindingContext(
        apartment_id=apartment.id,
        connection_id=connection.id,
        service_catalog_id=catalog.id,
        service_code="gas_supply",
        service_name=catalog.name,
        provider_id=None,
        provider_company=None,
        provider=None,
        cabinet_url="https://my.gas.ua/login",
        cabinet_login="test_login",
        cabinet_password_encrypted=encrypt_text("test_password"),
        personal_account=None,
        auto_check_enabled=True,
        auto_check_time="09:00",
        auto_check_timezone="Europe/Kyiv",
        auto_check_window_day_from=1,
        auto_check_window_day_to=10,
    )
    return db, charge_line, setting


@patch("app.workers.tariff_auto_check._fetch_gas_ua_home_html")
def test_successful_login_and_parse_writes_cabinet_price_without_touching_price_per_unit(mock_fetch):
    mock_fetch.return_value = (_VALID_HTML, None)
    db, charge_line, setting = _setup_gas_ua_db(initial_price_per_unit=Decimal("7.5000"))
    try:
        _run_gas_ua(db, setting=setting, now_utc=_NOW_UTC, local_now=_LOCAL_NOW)

        # _run_gas_ua itself doesn't commit (its caller does); flush so the
        # refresh below reads back what was actually written, not stale data.
        db.flush()
        db.refresh(charge_line)
        assert charge_line.cabinet_price_per_unit == Decimal("12.3456")
        assert charge_line.price_per_unit == Decimal("7.5000")
        assert setting.auto_check_status == "updated"
    finally:
        db.close()
        Base.metadata.drop_all(bind=_ENGINE)


@patch("app.workers.tariff_auto_check._fetch_gas_ua_home_html")
def test_login_or_fetch_failure_sets_error_status(mock_fetch):
    mock_fetch.return_value = (None, "my.gas.ua authorization failed (HTTP 401)")
    db, charge_line, setting = _setup_gas_ua_db()
    try:
        _run_gas_ua(db, setting=setting, now_utc=_NOW_UTC, local_now=_LOCAL_NOW)

        assert setting.auto_check_status == "error"
        db.refresh(charge_line)
        assert charge_line.cabinet_price_per_unit is None
    finally:
        db.close()
        Base.metadata.drop_all(bind=_ENGINE)


@patch("app.workers.tariff_auto_check._fetch_gas_ua_home_html")
def test_price_not_found_in_valid_html_sets_error_status(mock_fetch):
    mock_fetch.return_value = (_HTML_WITHOUT_PRICE, None)
    db, charge_line, setting = _setup_gas_ua_db()
    try:
        _run_gas_ua(db, setting=setting, now_utc=_NOW_UTC, local_now=_LOCAL_NOW)

        assert setting.auto_check_status == "error"
        db.refresh(charge_line)
        assert charge_line.cabinet_price_per_unit is None
    finally:
        db.close()
        Base.metadata.drop_all(bind=_ENGINE)
