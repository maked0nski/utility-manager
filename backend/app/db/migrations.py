from __future__ import annotations

from datetime import timedelta

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models import (
    Apartment,
    ApartmentAutomation,
    ApartmentServiceConnection,
    ApartmentTariffSetting,
    AutomationTemplate,
    ChargeMode,
    ChargeLineKind,
    ConnectionChargeLine,
    ElectricityMeterPlan,
    ElectricityPlanMode,
    Meter,
    MeterType,
    ProviderKind,
    Provider,
    QuantitySource,
    ServiceCalculationKind,
    ServiceCatalog,
    Tariff,
    UtilityType,
)


def _has_column(db: Session, table_name: str, column_name: str) -> bool:
    cols = inspect(db.bind).get_columns(table_name)
    return any(col.get("name") == column_name for col in cols)


def _has_table(db: Session, table_name: str) -> bool:
    return table_name in inspect(db.bind).get_table_names()


def _ensure_apartment_timezone_column(db: Session) -> None:
    if _has_column(db, "apartments", "timezone"):
        return
    db.execute(text("ALTER TABLE apartments ADD COLUMN timezone VARCHAR(64) DEFAULT 'Europe/Kyiv'"))
    db.commit()


def _ensure_apartment_profile_columns(db: Session) -> None:
    apartment_columns = {
        "country": "ALTER TABLE apartments ADD COLUMN country VARCHAR(128) NULL",
        "region": "ALTER TABLE apartments ADD COLUMN region VARCHAR(128) NULL",
        "locality": "ALTER TABLE apartments ADD COLUMN locality VARCHAR(128) NULL",
        "street": "ALTER TABLE apartments ADD COLUMN street VARCHAR(128) NULL",
        "house_number": "ALTER TABLE apartments ADD COLUMN house_number VARCHAR(32) NULL",
        "apartment_number": "ALTER TABLE apartments ADD COLUMN apartment_number VARCHAR(32) NULL",
        "postal_code": "ALTER TABLE apartments ADD COLUMN postal_code VARCHAR(16) NULL",
        "living_area_m2": "ALTER TABLE apartments ADD COLUMN living_area_m2 NUMERIC(10, 2) NULL",
        "entrance": "ALTER TABLE apartments ADD COLUMN entrance VARCHAR(32) NULL",
        "floor": "ALTER TABLE apartments ADD COLUMN floor VARCHAR(32) NULL",
        "room_count": "ALTER TABLE apartments ADD COLUMN room_count INTEGER NULL",
    }
    for column_name, ddl in apartment_columns.items():
        if _has_column(db, "apartments", column_name):
            continue
        db.execute(text(ddl))
        db.commit()


def _ensure_apartment_automation_submit_period_columns(db: Session) -> None:
    if not _has_column(db, "apartment_automations", "submit_target_year"):
        db.execute(text("ALTER TABLE apartment_automations ADD COLUMN submit_target_year INTEGER NULL"))
        db.commit()
    if not _has_column(db, "apartment_automations", "submit_target_month"):
        db.execute(text("ALTER TABLE apartment_automations ADD COLUMN submit_target_month INTEGER NULL"))
        db.commit()


def _ensure_automation_run_log_register_column(db: Session) -> None:
    if _has_column(db, "automation_run_logs", "register_name"):
        return
    db.execute(text("ALTER TABLE automation_run_logs ADD COLUMN register_name VARCHAR(32) NULL"))
    db.commit()


def _ensure_automation_run_log_target_period_columns(db: Session) -> None:
    if not _has_column(db, "automation_run_logs", "target_year"):
        db.execute(text("ALTER TABLE automation_run_logs ADD COLUMN target_year INTEGER NULL"))
        db.commit()
    if not _has_column(db, "automation_run_logs", "target_month"):
        db.execute(text("ALTER TABLE automation_run_logs ADD COLUMN target_month INTEGER NULL"))
        db.commit()


def _ensure_electricity_meter_plans_table(db: Session) -> None:
    inspector = inspect(db.bind)
    if "electricity_meter_plans" in inspector.get_table_names():
        return
    db.execute(
        text(
            """
            CREATE TABLE electricity_meter_plans (
                id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                apartment_id INTEGER NOT NULL,
                meter_id INTEGER NOT NULL,
                plan_mode VARCHAR(32) NOT NULL,
                effective_from DATE NOT NULL,
                single_service_name VARCHAR(128) NULL,
                day_service_name VARCHAR(128) NULL,
                night_service_name VARCHAR(128) NULL,
                peak_service_name VARCHAR(128) NULL,
                semi_peak_service_name VARCHAR(128) NULL,
                off_peak_service_name VARCHAR(128) NULL,
                single_price_per_unit NUMERIC(12, 4) NULL,
                day_price_per_unit NUMERIC(12, 4) NULL,
                night_price_per_unit NUMERIC(12, 4) NULL,
                peak_price_per_unit NUMERIC(12, 4) NULL,
                semi_peak_price_per_unit NUMERIC(12, 4) NULL,
                off_peak_price_per_unit NUMERIC(12, 4) NULL,
                single_initial_reading NUMERIC(12, 3) NULL,
                day_initial_reading NUMERIC(12, 3) NULL,
                night_initial_reading NUMERIC(12, 3) NULL,
                peak_initial_reading NUMERIC(12, 3) NULL,
                semi_peak_initial_reading NUMERIC(12, 3) NULL,
                off_peak_initial_reading NUMERIC(12, 3) NULL,
                note VARCHAR(255) NULL,
                created_at DATETIME NULL,
                CONSTRAINT uq_electricity_meter_plan_date UNIQUE (meter_id, effective_from),
                INDEX ix_electricity_meter_plans_lookup (apartment_id, meter_id, effective_from)
            )
            """
        )
    )
    db.commit()


def _drop_legacy_electricity_meter_plans_table(db: Session) -> None:
    if not _has_table(db, "electricity_meter_plans"):
        return
    db.execute(text("DROP TABLE electricity_meter_plans"))
    db.commit()


def _drop_legacy_tariff_tables(db: Session) -> None:
    for table_name in ("apartment_tariff_settings", "apartment_services", "tariffs"):
        if not _has_table(db, table_name):
            continue
        db.execute(text(f"DROP TABLE {table_name}"))
        db.commit()


def _ensure_automation_cycle_runs_table(db: Session) -> None:
    inspector = inspect(db.bind)
    if "automation_cycle_runs" in inspector.get_table_names():
        return
    db.execute(
        text(
            """
            CREATE TABLE automation_cycle_runs (
                id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                trigger_mode VARCHAR(32) NOT NULL,
                processed_accrual_automations INTEGER NOT NULL DEFAULT 0,
                processed_submit_automations INTEGER NOT NULL DEFAULT 0,
                processed_legacy_settings INTEGER NOT NULL DEFAULT 0,
                submitted_readings INTEGER NOT NULL DEFAULT 0,
                message VARCHAR(255) NULL,
                started_at DATETIME NULL,
                finished_at DATETIME NULL,
                INDEX ix_automation_cycle_runs_trigger_mode (trigger_mode),
                INDEX ix_automation_cycle_runs_started_at (started_at)
            )
            """
        )
    )
    db.commit()


def _ensure_automation_cycle_phase_runs_table(db: Session) -> None:
    inspector = inspect(db.bind)
    if "automation_cycle_phase_runs" not in inspector.get_table_names():
        db.execute(
            text(
                """
                CREATE TABLE automation_cycle_phase_runs (
                    id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                    cycle_run_id INTEGER NOT NULL,
                    phase VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'completed',
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    submitted_readings INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NULL,
                    message VARCHAR(255) NULL,
                    started_at DATETIME NULL,
                    finished_at DATETIME NULL,
                    INDEX ix_automation_cycle_phase_runs_cycle (cycle_run_id),
                    INDEX ix_automation_cycle_phase_runs_phase (phase)
                )
                """
            )
        )
        db.commit()
        return
    if not _has_column(db, "automation_cycle_phase_runs", "duration_ms"):
        db.execute(text("ALTER TABLE automation_cycle_phase_runs ADD COLUMN duration_ms INTEGER NULL"))
        db.commit()


def _ensure_meter_types_table(db: Session) -> None:
    inspector = inspect(db.bind)
    if "meter_types" not in inspector.get_table_names():
        db.execute(
            text(
                """
                CREATE TABLE meter_types (
                    id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                    code VARCHAR(64) NOT NULL,
                    name VARCHAR(128) NOT NULL,
                    utility_type VARCHAR(32) NOT NULL,
                    default_service_name VARCHAR(128) NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 100,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    UNIQUE KEY uq_meter_types_code (code),
                    UNIQUE KEY uq_meter_types_name (name),
                    INDEX ix_meter_types_utility_type (utility_type)
                )
                """
            )
        )
        db.commit()
    if not _has_column(db, "meters", "meter_type_id"):
        db.execute(text("ALTER TABLE meters ADD COLUMN meter_type_id INTEGER NULL"))
        db.commit()
        db.execute(text("CREATE INDEX ix_meters_meter_type_id ON meters (meter_type_id)"))
        db.commit()


def _drop_legacy_meter_service_name_column(db: Session) -> None:
    if not _has_column(db, "meters", "service_name"):
        return
    db.execute(text("ALTER TABLE meters DROP COLUMN service_name"))
    db.commit()


def _ensure_provider_catalog_extensions(db: Session) -> None:
    if not _has_column(db, "providers", "provider_kind"):
        db.execute(text("ALTER TABLE providers ADD COLUMN provider_kind VARCHAR(32) NOT NULL DEFAULT 'utility'"))
        db.commit()
    utility_column = next((col for col in inspect(db.bind).get_columns("providers") if col.get("name") == "utility_type"), None)
    if utility_column and not utility_column.get("nullable", False):
        try:
            db.execute(text("ALTER TABLE providers MODIFY COLUMN utility_type VARCHAR(32) NULL"))
            db.commit()
        except Exception:
            db.rollback()


def _ensure_service_catalog_table(db: Session) -> None:
    if _has_table(db, "service_catalog"):
        return
    db.execute(
        text(
            """
            CREATE TABLE service_catalog (
                id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                code VARCHAR(64) NOT NULL,
                name VARCHAR(128) NOT NULL,
                calculation_kind VARCHAR(32) NOT NULL,
                unit_name VARCHAR(32) NOT NULL,
                requires_meter BOOLEAN NOT NULL DEFAULT FALSE,
                allowed_meter_utility_type VARCHAR(32) NULL,
                default_provider_utility_type VARCHAR(32) NULL,
                derived_from_service_id INTEGER NULL,
                display_order INTEGER NOT NULL DEFAULT 100,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at DATETIME NULL,
                CONSTRAINT uq_service_catalog_code UNIQUE (code),
                CONSTRAINT uq_service_catalog_name UNIQUE (name),
                INDEX ix_service_catalog_name (name),
                INDEX ix_service_catalog_kind (calculation_kind),
                INDEX ix_service_catalog_order (display_order)
            )
            """
        )
    )
    db.commit()


def _ensure_apartment_service_connections_table(db: Session) -> None:
    if _has_table(db, "apartment_service_connections"):
        return
    db.execute(
        text(
            """
            CREATE TABLE apartment_service_connections (
                id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                apartment_id INTEGER NOT NULL,
                service_catalog_id INTEGER NOT NULL,
                provider_id INTEGER NULL,
                personal_account VARCHAR(128) NULL,
                started_at DATE NOT NULL,
                ended_at DATE NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                note TEXT NULL,
                automation_id INTEGER NULL,
                created_at DATETIME NULL,
                INDEX ix_service_connections_apartment (apartment_id),
                INDEX ix_service_connections_catalog (service_catalog_id),
                INDEX ix_service_connections_provider (provider_id),
                INDEX ix_service_connections_status (status)
            )
            """
        )
    )
    db.commit()


def _ensure_connection_charge_lines_table(db: Session) -> None:
    if not _has_table(db, "connection_charge_lines"):
        db.execute(
            text(
                """
                CREATE TABLE connection_charge_lines (
                    id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,
                    connection_id INTEGER NOT NULL,
                    line_kind VARCHAR(32) NOT NULL,
                    label VARCHAR(128) NOT NULL,
                    meter_id INTEGER NULL,
                    meter_register VARCHAR(32) NOT NULL DEFAULT 'total',
                    derived_from_line_id INTEGER NULL,
                    initial_reading NUMERIC(12, 3) NULL,
                    unit_name VARCHAR(32) NOT NULL,
                    price_per_unit NUMERIC(12, 4) NOT NULL,
                    quantity_source VARCHAR(32) NOT NULL DEFAULT 'fixed_1',
                    quantity_multiplier NUMERIC(10, 3) NOT NULL DEFAULT 1.000,
                    effective_from DATE NOT NULL,
                    effective_to DATE NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at DATETIME NULL,
                    INDEX ix_charge_lines_connection (connection_id),
                    INDEX ix_charge_lines_meter (meter_id),
                    INDEX ix_charge_lines_kind (line_kind),
                    INDEX ix_charge_lines_effective_from (effective_from)
                )
                """
            )
        )
        db.commit()
        return
    if not _has_column(db, "connection_charge_lines", "initial_reading"):
        db.execute(text("ALTER TABLE connection_charge_lines ADD COLUMN initial_reading NUMERIC(12, 3) NULL"))
        db.commit()


def _ensure_provider_import_rows_service_catalog_code(db: Session) -> None:
    if not _has_table(db, "provider_import_rows"):
        return
    if not _has_column(db, "provider_import_rows", "service_catalog_code"):
        db.execute(text("ALTER TABLE provider_import_rows ADD COLUMN service_catalog_code VARCHAR(64) NULL"))
        db.commit()
    try:
        db.execute(
            text(
                "CREATE INDEX ix_provider_import_rows_service_catalog_code "
                "ON provider_import_rows (service_catalog_code)"
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _sync_utility_payment_periods_from_paid_at(db: Session) -> None:
    if not _has_table(db, "utility_payments"):
        return
    if not _has_column(db, "utility_payments", "year") or not _has_column(db, "utility_payments", "month"):
        return
    db.execute(text("UPDATE utility_payments SET year = YEAR(paid_at), month = MONTH(paid_at)"))
    db.commit()


def _seed_meter_types(db: Session) -> None:
    defaults = [
        ("electricity_default", "Електролічильник", UtilityType.electricity.value, "Електролічильник", 10),
        ("water_default", "Лічильник води", UtilityType.water.value, "Лічильник води", 20),
        ("gas_default", "Газовий лічильник", UtilityType.gas.value, "Газовий лічильник", 30),
        ("heating_default", "Лічильник опалення", UtilityType.heating.value, "Лічильник опалення", 40),
        ("sewage_default", "Лічильник водовідведення", UtilityType.sewage.value, "Лічильник водовідведення", 50),
        ("internet_default", "Інтернет-лічильник", UtilityType.internet.value, "Інтернет-лічильник", 60),
        ("other_default", "Лічильник", UtilityType.other.value, "Лічильник", 70),
    ]
    existing_codes = {row.code for row in db.query(MeterType).all()}
    for code, name, utility_type, default_service_name, sort_order in defaults:
        if code in existing_codes:
            continue
        db.add(
            MeterType(
                code=code,
                name=name,
                utility_type=UtilityType(utility_type),
                default_service_name=default_service_name,
                sort_order=sort_order,
                is_active=True,
            )
        )
    db.commit()


def _seed_service_catalog(db: Session) -> None:
    if db.query(ServiceCatalog).count() > 0:
        return
    defaults = [
        ("maintenance_fee", "Квартплата", ServiceCalculationKind.fixed, "month", False, None, UtilityType.other, None, 10),
        ("gas_supply", "Газопостачання", ServiceCalculationKind.metered, "m3", True, UtilityType.gas, UtilityType.gas, None, 20),
        ("gas_distribution", "За розподіл (доставку) газу", ServiceCalculationKind.fixed, "month", False, None, UtilityType.gas, None, 30),
        ("waste", "Вивіз сміття", ServiceCalculationKind.fixed, "month", False, None, UtilityType.other, None, 40),
        ("electricity", "Електроенергія", ServiceCalculationKind.metered, "kWh", True, UtilityType.electricity, UtilityType.electricity, None, 50),
        ("water_subscription", "Абонентська плата (водоканал)", ServiceCalculationKind.fixed, "month", False, None, UtilityType.water, None, 60),
        ("water_supply", "Водопостачання", ServiceCalculationKind.metered, "m3", True, UtilityType.water, UtilityType.water, None, 70),
        ("sewage", "Водовідведення", ServiceCalculationKind.derived, "m3", False, None, UtilityType.sewage, "water_supply", 80),
        ("gate_automation", "За автоматику на воротах", ServiceCalculationKind.fixed, "month", False, None, UtilityType.other, None, 90),
        ("intercom", "За домофон", ServiceCalculationKind.fixed, "month", False, None, UtilityType.other, None, 100),
        ("internet", "Інтернет", ServiceCalculationKind.fixed, "month", False, None, UtilityType.internet, None, 110),
    ]
    created: dict[str, ServiceCatalog] = {}
    for code, name, calculation_kind, unit_name, requires_meter, allowed_meter_utility_type, default_provider_utility_type, derived_from_code, display_order in defaults:
        row = ServiceCatalog(
            code=code,
            name=name,
            calculation_kind=calculation_kind,
            unit_name=unit_name,
            requires_meter=requires_meter,
            allowed_meter_utility_type=allowed_meter_utility_type,
            default_provider_utility_type=default_provider_utility_type,
            display_order=display_order,
            is_active=True,
        )
        db.add(row)
        db.flush()
        created[code] = row
        if derived_from_code:
            row.derived_from_service_id = created[derived_from_code].id
    db.commit()


def _backfill_meter_types(db: Session) -> None:
    fallback_codes = {
        UtilityType.electricity: "electricity_default",
        UtilityType.water: "water_default",
        UtilityType.gas: "gas_default",
        UtilityType.heating: "heating_default",
        UtilityType.sewage: "sewage_default",
        UtilityType.internet: "internet_default",
        UtilityType.other: "other_default",
    }
    type_by_code = {item.code: item for item in db.query(MeterType).all()}
    meters = db.query(Meter).all()
    for meter in meters:
        resolved_type = meter.meter_type
        if resolved_type is None:
            resolved_type = type_by_code.get(fallback_codes.get(meter.utility_type, "other_default"))
        if resolved_type is None:
            continue
        meter.meter_type_id = resolved_type.id
        meter.utility_type = resolved_type.utility_type
    db.commit()


def _safe_code(base: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (base or "").strip().lower())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned or "automation")[:80]


def _ensure_template(
    db: Session,
    *,
    provider: Provider | None,
    provider_company: str | None,
    cabinet_url: str | None,
) -> AutomationTemplate:
    if provider is not None:
        existing = db.query(AutomationTemplate).filter(AutomationTemplate.provider_id == provider.id).first()
        if existing is not None:
            return existing
        code = f"provider_{provider.id}_default"
        row = AutomationTemplate(
            code=code,
            name=f"{provider.name_full} (базова автоматизація)",
            provider_id=provider.id,
            utility_type=provider.utility_type,
            cabinet_url=cabinet_url,
            description="Автоматизація постачальника (створено автоматично під час міграції).",
            supports_accrual=True,
            supports_meter_submit=False,
            is_active=True,
        )
        db.add(row)
        db.flush()
        return row

    company = (provider_company or "").strip()
    code = f"manual_{_safe_code(company or 'provider')}_default"
    existing = db.query(AutomationTemplate).filter(AutomationTemplate.code == code).first()
    if existing is not None:
        return existing
    row = AutomationTemplate(
        code=code,
        name=f"{company or 'Невідомий постачальник'} (базова автоматизація)",
        provider_id=None,
        utility_type=None,
        cabinet_url=cabinet_url,
        description="Автоматизація без довідникового постачальника (створено автоматично під час міграції).",
        supports_accrual=True,
        supports_meter_submit=False,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _is_vodokanal_label(value: str) -> bool:
    low = value.casefold()
    return ("водоканал" in low) or ("vodokanal" in low)


def _backfill_automations(db: Session) -> None:
    settings = db.query(ApartmentTariffSetting).order_by(ApartmentTariffSetting.id.desc()).all()
    seen: set[tuple[int, int | None, str]] = set()
    for setting in settings:
        provider = setting.provider
        provider_company = (setting.provider_company or "").strip()
        if provider is None and not provider_company:
            continue
        uniq_key = (setting.apartment_id, setting.provider_id, provider_company.casefold())
        if uniq_key in seen:
            continue
        seen.add(uniq_key)
        template = _ensure_template(
            db,
            provider=provider,
            provider_company=provider_company,
            cabinet_url=setting.cabinet_url,
        )
        existing = (
            db.query(ApartmentAutomation)
            .filter(ApartmentAutomation.apartment_id == setting.apartment_id)
            .filter(
                (ApartmentAutomation.template_id == template.id)
                | (ApartmentAutomation.provider_id == setting.provider_id)
            )
            .first()
        )
        if existing is not None:
            continue
        submit_enabled = False
        submit_from = 28
        submit_to = 3
        haystack = " ".join(
            [
                setting.service_name or "",
                setting.provider_company or "",
                setting.cabinet_url or "",
            ]
        )
        if _is_vodokanal_label(haystack):
            submit_enabled = True
        row = ApartmentAutomation(
            apartment_id=setting.apartment_id,
            template_id=template.id,
            provider_id=setting.provider_id,
            personal_account=setting.personal_account,
            cabinet_url=setting.cabinet_url,
            cabinet_login=setting.cabinet_login,
            cabinet_password_encrypted=setting.cabinet_password_encrypted,
            is_enabled=True,
            accrual_enabled=setting.auto_check_enabled,
            accrual_time=setting.auto_check_time or "09:00",
            accrual_window_day_from=setting.auto_check_window_day_from or 1,
            accrual_window_day_to=setting.auto_check_window_day_to or 10,
            accrual_completed_for_period=setting.auto_check_completed_for_period,
            submit_enabled=submit_enabled,
            submit_time="09:00",
            submit_window_day_from=submit_from,
            submit_window_day_to=submit_to,
            submit_completed_for_period=False,
            auto_check_target_year=setting.auto_check_target_year,
            auto_check_target_month=setting.auto_check_target_month,
            auto_check_status=setting.auto_check_status,
            auto_check_message=setting.auto_check_message,
            auto_check_last_checked_at=setting.auto_check_last_checked_at,
            auto_check_last_updated_at=setting.auto_check_last_updated_at,
            auto_check_next_at=setting.auto_check_next_at,
        )
        db.add(row)
    db.commit()


def _backfill_electricity_meter_plans(db: Session) -> None:
    tariffs = (
        db.query(Tariff)
        .filter(Tariff.meter_id != None)  # noqa: E711
        .filter(Tariff.utility_type == UtilityType.electricity)
        .order_by(Tariff.meter_id, Tariff.effective_from, Tariff.id)
        .all()
    )
    grouped: dict[tuple[int, object], list[Tariff]] = {}
    for tariff in tariffs:
        grouped.setdefault((tariff.meter_id, tariff.effective_from), []).append(tariff)
    for (meter_id, effective_from), rows in grouped.items():
        meter = db.get(Meter, meter_id)
        if meter is None or meter.utility_type != UtilityType.electricity:
            continue
        exists = (
            db.query(ElectricityMeterPlan)
            .filter(ElectricityMeterPlan.meter_id == meter_id)
            .filter(ElectricityMeterPlan.effective_from == effective_from)
            .first()
        )
        if exists is not None:
            continue
        by_register = {row.meter_register or "total": row for row in rows}
        mode = ElectricityPlanMode.single if "total" in by_register else ElectricityPlanMode.day_night
        db.add(
            ElectricityMeterPlan(
                apartment_id=meter.apartment_id,
                meter_id=meter.id,
                plan_mode=mode,
                effective_from=effective_from,
                single_service_name=by_register.get("total").service_name if by_register.get("total") else None,
                day_service_name=by_register.get("day").service_name if by_register.get("day") else None,
                night_service_name=by_register.get("night").service_name if by_register.get("night") else None,
                single_price_per_unit=by_register.get("total").price_per_unit if by_register.get("total") else None,
                day_price_per_unit=by_register.get("day").price_per_unit if by_register.get("day") else None,
                night_price_per_unit=by_register.get("night").price_per_unit if by_register.get("night") else None,
                single_initial_reading=meter.initial_reading if "total" in by_register else None,
                note="Створено автоматично з існуючих електротарифів.",
            )
        )
    db.commit()


def _legacy_tariff_service_catalog(
    service_by_name: dict[str, ServiceCatalog], tariff: Tariff
) -> ServiceCatalog | None:
    name = (tariff.service_name or "").strip().casefold()
    if tariff.utility_type == UtilityType.electricity or "електро" in name:
        return service_by_name.get("електроенергія")
    return service_by_name.get(name)


def _legacy_quantity_source(raw: str | None) -> QuantitySource:
    if raw == QuantitySource.registered_residents.value:
        return QuantitySource.registered_residents
    if raw == QuantitySource.area_m2.value:
        return QuantitySource.area_m2
    if raw == QuantitySource.derived_consumption.value:
        return QuantitySource.derived_consumption
    return QuantitySource.fixed_1


def _legacy_line_label(service_catalog: ServiceCatalog, tariff: Tariff) -> str:
    register_name = tariff.meter_register or "total"
    if service_catalog.code == "electricity":
        return {
            "total": "Основний тариф",
            "day": "Денний тариф",
            "night": "Нічний тариф",
            "peak": "Піковий тариф",
            "semi_peak": "Напівпіковий тариф",
            "off_peak": "Нічний тариф",
        }.get(register_name, "Тариф")
    if tariff.charge_mode == ChargeMode.metered and tariff.source_service_name:
        return "Розрахунок від іншої послуги"
    return "Основний тариф"


def _backfill_service_connections(db: Session) -> None:
    tariffs = (
        db.query(Tariff)
        .order_by(Tariff.apartment_id, Tariff.effective_from, Tariff.service_name, Tariff.id)
        .all()
    )
    if not tariffs:
        return

    service_by_name = {row.name.casefold(): row for row in db.query(ServiceCatalog).all()}
    settings_by_service = {
        (row.apartment_id, (row.service_name or "").casefold()): row
        for row in db.query(ApartmentTariffSetting).order_by(ApartmentTariffSetting.id.desc()).all()
    }
    automations_by_provider = {
        (row.apartment_id, row.provider_id): row
        for row in db.query(ApartmentAutomation)
        .filter(ApartmentAutomation.provider_id != None)  # noqa: E711
        .order_by(ApartmentAutomation.id.desc())
        .all()
    }
    connection_by_key: dict[tuple[int, int], ApartmentServiceConnection] = {
        (row.apartment_id, row.service_catalog_id): row for row in db.query(ApartmentServiceConnection).all()
    }
    staged_line_keys: set[tuple[int, str, str, object]] = set()
    last_version_by_signature: dict[tuple[int, str, str], ConnectionChargeLine] = {}
    pending_derived: list[tuple[ConnectionChargeLine, int, str]] = []

    for tariff in tariffs:
        service_catalog = _legacy_tariff_service_catalog(service_by_name, tariff)
        if service_catalog is None:
            continue
        connection_key = (tariff.apartment_id, service_catalog.id)
        connection = connection_by_key.get(connection_key)
        setting = settings_by_service.get((tariff.apartment_id, (tariff.service_name or "").casefold()))

        if connection is None:
            provider_id = setting.provider_id if setting else None
            automation = automations_by_provider.get((tariff.apartment_id, provider_id)) if provider_id else None
            connection = ApartmentServiceConnection(
                apartment_id=tariff.apartment_id,
                service_catalog_id=service_catalog.id,
                provider_id=provider_id,
                personal_account=setting.personal_account if setting else None,
                started_at=tariff.effective_from,
                ended_at=None,
                status="active",
                note="Створено автоматично зі старих тарифів.",
                automation_id=automation.id if automation else None,
            )
            db.add(connection)
            db.flush()
            connection_by_key[connection_key] = connection
        else:
            if tariff.effective_from < connection.started_at:
                connection.started_at = tariff.effective_from
            if connection.provider_id is None and setting and setting.provider_id is not None:
                connection.provider_id = setting.provider_id
                automation = automations_by_provider.get((tariff.apartment_id, setting.provider_id))
                connection.automation_id = automation.id if automation else connection.automation_id
            if (not connection.personal_account) and setting and setting.personal_account:
                connection.personal_account = setting.personal_account

        line_kind = (
            ChargeLineKind.derived
            if tariff.charge_mode == ChargeMode.metered and tariff.source_service_name
            else ChargeLineKind.meter_register if tariff.charge_mode == ChargeMode.metered else ChargeLineKind.fixed
        )
        label = _legacy_line_label(service_catalog, tariff)
        register_name = tariff.meter_register or "total"
        line_key = (connection.id, line_kind.value, register_name, tariff.effective_from)
        if line_key in staged_line_keys:
            continue
        staged_line_keys.add(line_key)

        row = ConnectionChargeLine(
            connection_id=connection.id,
            line_kind=line_kind,
            label=label,
            meter_id=tariff.meter_id,
            meter_register=register_name,
            derived_from_line_id=None,
            unit_name=tariff.unit_name,
            price_per_unit=tariff.price_per_unit,
            quantity_source=_legacy_quantity_source(tariff.fixed_quantity_source),
            quantity_multiplier=tariff.fixed_quantity_multiplier,
            effective_from=tariff.effective_from,
            effective_to=None,
            is_active=True,
        )
        db.add(row)
        db.flush()

        signature = (connection.id, line_kind.value, register_name)
        previous = last_version_by_signature.get(signature)
        if previous is not None and previous.effective_from < row.effective_from and previous.effective_to is None:
            previous.effective_to = row.effective_from - timedelta(days=1)
        if previous is None or previous.effective_from <= row.effective_from:
            last_version_by_signature[signature] = row

        if line_kind == ChargeLineKind.derived and tariff.source_service_name:
            pending_derived.append((row, tariff.apartment_id, tariff.source_service_name))

    db.flush()

    for row, apartment_id, source_service_name in pending_derived:
        source_catalog = service_by_name.get((source_service_name or "").strip().casefold())
        if source_catalog is None:
            continue
        source_connection = connection_by_key.get((apartment_id, source_catalog.id))
        if source_connection is None:
            continue
        source_line = (
            db.query(ConnectionChargeLine)
            .filter(ConnectionChargeLine.connection_id == source_connection.id)
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
            .first()
        )
        if source_line is None:
            continue
        row.derived_from_line_id = source_line.id
        row.quantity_source = QuantitySource.derived_consumption

    db.commit()


def run_startup_migrations(db: Session) -> None:
    _ensure_apartment_profile_columns(db)
    _ensure_apartment_timezone_column(db)
    _ensure_apartment_automation_submit_period_columns(db)
    _ensure_automation_run_log_register_column(db)
    _ensure_automation_run_log_target_period_columns(db)
    _ensure_meter_types_table(db)
    _ensure_provider_catalog_extensions(db)
    _ensure_service_catalog_table(db)
    _ensure_apartment_service_connections_table(db)
    _ensure_connection_charge_lines_table(db)
    _ensure_provider_import_rows_service_catalog_code(db)
    _ensure_automation_cycle_runs_table(db)
    _ensure_automation_cycle_phase_runs_table(db)
    _sync_utility_payment_periods_from_paid_at(db)
    _drop_legacy_electricity_meter_plans_table(db)
    apartments_without_timezone = db.query(Apartment).filter((Apartment.timezone == None) | (Apartment.timezone == "")).all()  # noqa: E711
    for ap in apartments_without_timezone:
        ap.timezone = "Europe/Kyiv"
    db.commit()
    _seed_meter_types(db)
    _seed_service_catalog(db)
    _backfill_meter_types(db)
    _drop_legacy_meter_service_name_column(db)
    _drop_legacy_tariff_tables(db)
