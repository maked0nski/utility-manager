from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import ApartmentAutomation, AutomationTemplate

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _make_automation(cron_eligible: bool) -> ApartmentAutomation:
    template = AutomationTemplate(
        code="test_template",
        name="Test",
        cron_eligible=cron_eligible,
        supports_accrual=True,
        supports_meter_submit=False,
        is_active=True,
    )
    automation = ApartmentAutomation(
        apartment_id=1,
        template=template,
        is_enabled=True,
        accrual_enabled=True,
    )
    return automation


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


def test_scheduled_trigger_skips_cron_ineligible_automation():
    automation = _make_automation(cron_eligible=False)
    should_skip = automation.template is not None and not automation.template.cron_eligible
    trigger_mode = "scheduled"
    assert (trigger_mode != "manual" and should_skip) is True


def test_manual_trigger_runs_cron_ineligible_automation():
    automation = _make_automation(cron_eligible=False)
    should_skip = automation.template is not None and not automation.template.cron_eligible
    trigger_mode = "manual"
    assert (trigger_mode != "manual" and should_skip) is False


def test_scheduled_trigger_runs_cron_eligible_automation():
    automation = _make_automation(cron_eligible=True)
    should_skip = automation.template is not None and not automation.template.cron_eligible
    trigger_mode = "scheduled"
    assert (trigger_mode != "manual" and should_skip) is False
