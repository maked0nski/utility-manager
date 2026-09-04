from datetime import UTC
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Apartment, ApartmentAutomation, AutomationTemplate
from app.workers.tariff_auto_check import run_tariff_auto_checks

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_cron_eligible_defaults_to_true():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        template = AutomationTemplate(
            code="t", name="T", supports_accrual=True, supports_meter_submit=False, is_active=True
        )
        db.add(template)
        db.flush()
        assert template.cron_eligible is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _setup_gating_db():
    """Build a real (in-memory SQLite) DB with one cron-eligible and one
    cron-ineligible ApartmentAutomation, so the gating tests exercise the
    actual production guard inside run_tariff_auto_checks rather than a
    locally reimplemented expression."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    apartment = Apartment(code="A1", address="Test Address 1")
    db.add(apartment)
    db.flush()

    eligible_template = AutomationTemplate(
        code="eligible_tpl",
        name="Eligible",
        cron_eligible=True,
        supports_accrual=True,
        supports_meter_submit=False,
        is_active=True,
    )
    ineligible_template = AutomationTemplate(
        code="ineligible_tpl",
        name="Ineligible",
        cron_eligible=False,
        supports_accrual=True,
        supports_meter_submit=False,
        is_active=True,
    )
    db.add_all([eligible_template, ineligible_template])
    db.flush()

    eligible_automation = ApartmentAutomation(
        apartment_id=apartment.id,
        template_id=eligible_template.id,
        is_enabled=True,
        accrual_enabled=True,
    )
    ineligible_automation = ApartmentAutomation(
        apartment_id=apartment.id,
        template_id=ineligible_template.id,
        is_enabled=True,
        accrual_enabled=True,
    )
    db.add_all([eligible_automation, ineligible_automation])
    db.commit()
    db.refresh(eligible_automation)
    db.refresh(ineligible_automation)
    return db, eligible_automation, ineligible_automation


def _run_cycle(db, *, trigger_mode: str):
    # This dev environment's interpreter has no `tzdata` package installed,
    # so zoneinfo.ZoneInfo("Europe/Kyiv") (the apartment's default timezone)
    # cannot resolve here even though it resolves fine in production (Linux
    # ships its own IANA tz database). Pin ZoneInfo to UTC for the duration
    # of the call so the real dispatch/guard code in run_tariff_auto_checks
    # still runs end-to-end; only the local-time-zone conversion is stubbed.
    with patch("app.workers.tariff_auto_check.ZoneInfo", return_value=UTC):
        return run_tariff_auto_checks(db, trigger_mode=trigger_mode)


def test_scheduled_trigger_skips_cron_ineligible_automation():
    db, eligible_automation, ineligible_automation = _setup_gating_db()
    try:
        assert eligible_automation.auto_check_last_checked_at is None
        assert ineligible_automation.auto_check_last_checked_at is None

        result = _run_cycle(db, trigger_mode="scheduled")

        # Only the cron-eligible automation should have been processed.
        assert result["processed_accrual_automations"] == 1

        db.refresh(eligible_automation)
        db.refresh(ineligible_automation)
        assert eligible_automation.auto_check_last_checked_at is not None
        assert ineligible_automation.auto_check_last_checked_at is None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_manual_trigger_runs_cron_ineligible_automation():
    db, eligible_automation, ineligible_automation = _setup_gating_db()
    try:
        result = _run_cycle(db, trigger_mode="manual")

        # Manual trigger bypasses the cron_eligible guard entirely.
        assert result["processed_accrual_automations"] == 2

        db.refresh(eligible_automation)
        db.refresh(ineligible_automation)
        assert eligible_automation.auto_check_last_checked_at is not None
        assert ineligible_automation.auto_check_last_checked_at is not None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_scheduled_trigger_runs_cron_eligible_automation():
    db, eligible_automation, _ = _setup_gating_db()
    try:
        result = _run_cycle(db, trigger_mode="scheduled")

        assert result["processed_accrual_automations"] == 1

        db.refresh(eligible_automation)
        assert eligible_automation.auto_check_last_checked_at is not None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
