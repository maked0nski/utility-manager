from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from urllib.parse import quote_plus

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UtilityType(StrEnum):
    electricity = "electricity"
    water = "water"
    gas = "gas"
    heating = "heating"
    sewage = "sewage"
    internet = "internet"
    other = "other"


class ChargeMode(StrEnum):
    metered = "metered"
    fixed = "fixed"


class ServiceCalculationKind(StrEnum):
    fixed = "fixed"
    metered = "metered"
    derived = "derived"


class ProviderKind(StrEnum):
    utility = "utility"
    management_company = "management_company"
    telecom = "telecom"
    security = "security"
    other = "other"


class ChargeLineKind(StrEnum):
    fixed = "fixed"
    meter_register = "meter_register"
    derived = "derived"


class QuantitySource(StrEnum):
    fixed_1 = "fixed_1"
    registered_residents = "registered_residents"
    area_m2 = "area_m2"
    derived_consumption = "derived_consumption"


class InvoiceStatus(StrEnum):
    unpaid = "unpaid"
    paid = "paid"


class BillingStatementStatus(StrEnum):
    draft = "draft"
    prepared = "prepared"
    sent = "sent"
    cancelled = "cancelled"


class RentCurrency(StrEnum):
    uah = "UAH"
    usd = "USD"
    eur = "EUR"


class UnitType(StrEnum):
    kwh = "kWh"
    m3 = "m3"
    month = "month"


class ElectricityPlanMode(StrEnum):
    single = "single"
    day_night = "day_night"
    tri_zone = "tri_zone"


class Role(StrEnum):
    admin = "admin"
    operator = "operator"
    read_only = "read_only"


class ContractExtensionType(StrEnum):
    none = "none"
    prolongation = "prolongation"
    extension = "extension"


class OwnerChargeKind(StrEnum):
    reimbursement = "reimbursement"
    owner_cost = "owner_cost"


class MaintenanceType(StrEnum):
    planned = "planned"
    unplanned = "unplanned"


class ProviderImportBatchStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class ProviderImportRowStatus(StrEnum):
    staged = "staged"
    applied = "applied"
    skipped = "skipped"
    error = "error"


class Apartment(Base):
    __tablename__ = "apartments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    address: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(128), default=None)
    region: Mapped[str | None] = mapped_column(String(128), default=None)
    locality: Mapped[str | None] = mapped_column(String(128), default=None)
    street: Mapped[str | None] = mapped_column(String(128), default=None)
    house_number: Mapped[str | None] = mapped_column(String(32), default=None)
    apartment_number: Mapped[str | None] = mapped_column(String(32), default=None)
    postal_code: Mapped[str | None] = mapped_column(String(16), default=None)
    registered_residents: Mapped[int] = mapped_column(default=1)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    living_area_m2: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    entrance: Mapped[str | None] = mapped_column(String(32), default=None)
    floor: Mapped[str | None] = mapped_column(String(32), default=None)
    room_count: Mapped[int | None] = mapped_column(default=None)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), default=None)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), default=None)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
    location_note: Mapped[str | None] = mapped_column(String(255), default=None)
    object_notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    tenancies: Mapped[list[Tenancy]] = relationship(back_populates="apartment")
    meters: Mapped[list[Meter]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    tariff_settings: Mapped[list[ApartmentTariffSetting]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    rent_ledgers: Mapped[list[RentLedger]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    tariffs: Mapped[list[Tariff]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    owner_charges: Mapped[list[OwnerCharge]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    maintenance_records: Mapped[list[MaintenanceRecord]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    services: Mapped[list[ApartmentService]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    billing_locks: Mapped[list[BillingLock]] = relationship(back_populates="apartment", cascade="all, delete-orphan")
    billing_change_logs: Mapped[list[BillingChangeLog]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    service_ledger_entries: Mapped[list[ServiceLedgerEntry]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    equipment_items: Mapped[list[ApartmentEquipment]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    provider_import_batches: Mapped[list[ProviderImportBatch]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    automations: Mapped[list[ApartmentAutomation]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    service_connections: Mapped[list[ApartmentServiceConnection]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    billing_month_snapshots: Mapped[list[BillingMonthSnapshot]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )
    billing_statements: Mapped[list[BillingStatement]] = relationship(
        back_populates="apartment", cascade="all, delete-orphan"
    )

    @property
    def short_address(self) -> str:
        if self.street or self.house_number or self.apartment_number:
            parts = [part.strip() for part in [self.street, self.house_number] if part and part.strip()]
            short = " ".join(parts)
            if self.apartment_number and self.apartment_number.strip():
                short = f"{short} кв {self.apartment_number.strip()}".strip()
            if short:
                return short
        head = (self.address or "").split(",")[0].strip()
        return head or (self.address or "")

    @property
    def google_maps_url(self) -> str | None:
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        query = (self.address or "").strip()
        if not query:
            return None
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name_full: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    utility_type: Mapped[UtilityType | None] = mapped_column(Enum(UtilityType), nullable=True, index=True)
    provider_kind: Mapped[ProviderKind] = mapped_column(Enum(ProviderKind), default=ProviderKind.utility)
    adapter_code: Mapped[str] = mapped_column(String(64), default="manual_stub", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    tariff_settings: Mapped[list[ApartmentTariffSetting]] = relationship(back_populates="provider")
    automation_templates: Mapped[list[AutomationTemplate]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
    apartment_automations: Mapped[list[ApartmentAutomation]] = relationship(back_populates="provider")
    service_connections: Mapped[list[ApartmentServiceConnection]] = relationship(back_populates="provider")


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"
    __table_args__ = (
        UniqueConstraint("code", name="uq_service_catalog_code"),
        UniqueConstraint("name", name="uq_service_catalog_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    calculation_kind: Mapped[ServiceCalculationKind] = mapped_column(Enum(ServiceCalculationKind), index=True)
    unit_name: Mapped[UnitType] = mapped_column(Enum(UnitType))
    requires_meter: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_meter_utility_type: Mapped[UtilityType | None] = mapped_column(Enum(UtilityType), nullable=True)
    default_provider_utility_type: Mapped[UtilityType | None] = mapped_column(Enum(UtilityType), nullable=True)
    derived_from_service_id: Mapped[int | None] = mapped_column(ForeignKey("service_catalog.id"), default=None)
    display_order: Mapped[int] = mapped_column(default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    derived_from_service: Mapped[ServiceCatalog | None] = relationship(remote_side="ServiceCatalog.id")
    service_connections: Mapped[list[ApartmentServiceConnection]] = relationship(back_populates="service_catalog")


class AutomationTemplate(Base):
    __tablename__ = "automation_templates"
    __table_args__ = (UniqueConstraint("code", name="uq_automation_template_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(96), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), default=None, index=True)
    utility_type: Mapped[UtilityType | None] = mapped_column(Enum(UtilityType), nullable=True)
    cabinet_url: Mapped[str | None] = mapped_column(String(255), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    supports_accrual: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_meter_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    provider: Mapped[Provider | None] = relationship(back_populates="automation_templates")
    apartment_automations: Mapped[list[ApartmentAutomation]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class ApartmentAutomation(Base):
    __tablename__ = "apartment_automations"
    __table_args__ = (
        UniqueConstraint("apartment_id", "template_id", name="uq_apartment_automation_template"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("automation_templates.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), default=None, index=True)
    personal_account: Mapped[str | None] = mapped_column(String(128), default=None)
    cabinet_url: Mapped[str | None] = mapped_column(String(255), default=None)
    cabinet_login: Mapped[str | None] = mapped_column(String(128), default=None)
    cabinet_password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    accrual_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    accrual_time: Mapped[str] = mapped_column(String(5), default="09:00")
    accrual_window_day_from: Mapped[int] = mapped_column(default=1)
    accrual_window_day_to: Mapped[int] = mapped_column(default=10)
    accrual_completed_for_period: Mapped[bool] = mapped_column(Boolean, default=False)

    submit_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    submit_time: Mapped[str] = mapped_column(String(5), default="09:00")
    submit_window_day_from: Mapped[int] = mapped_column(default=28)
    submit_window_day_to: Mapped[int] = mapped_column(default=3)
    submit_target_year: Mapped[int | None] = mapped_column(default=None, index=True)
    submit_target_month: Mapped[int | None] = mapped_column(default=None, index=True)
    submit_completed_for_period: Mapped[bool] = mapped_column(Boolean, default=False)

    auto_check_target_year: Mapped[int | None] = mapped_column(default=None, index=True)
    auto_check_target_month: Mapped[int | None] = mapped_column(default=None, index=True)
    auto_check_status: Mapped[str | None] = mapped_column(String(32), default=None)
    auto_check_message: Mapped[str | None] = mapped_column(String(255), default=None)
    auto_check_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    auto_check_last_updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    auto_check_next_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="automations")
    template: Mapped[AutomationTemplate] = relationship(back_populates="apartment_automations")
    provider: Mapped[Provider | None] = relationship(back_populates="apartment_automations")
    run_logs: Mapped[list[AutomationRunLog]] = relationship(
        back_populates="automation", cascade="all, delete-orphan"
    )


class AutomationRunLog(Base):
    __tablename__ = "automation_run_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("apartment_automations.id"), default=None, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    register_name: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    target_year: Mapped[int | None] = mapped_column(default=None, index=True)
    target_month: Mapped[int | None] = mapped_column(default=None, index=True)
    mode: Mapped[str] = mapped_column(String(32), default="full")
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    message: Mapped[str | None] = mapped_column(String(255), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    automation: Mapped[ApartmentAutomation | None] = relationship(back_populates="run_logs")
    apartment: Mapped[Apartment] = relationship()


class AutomationCycleRun(Base):
    __tablename__ = "automation_cycle_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trigger_mode: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    processed_accrual_automations: Mapped[int] = mapped_column(default=0)
    processed_submit_automations: Mapped[int] = mapped_column(default=0)
    processed_legacy_settings: Mapped[int] = mapped_column(default=0)
    submitted_readings: Mapped[int] = mapped_column(default=0)
    message: Mapped[str | None] = mapped_column(String(255), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class AutomationCyclePhaseRun(Base):
    __tablename__ = "automation_cycle_phase_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cycle_run_id: Mapped[int] = mapped_column(ForeignKey("automation_cycle_runs.id"), index=True)
    phase: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    processed_count: Mapped[int] = mapped_column(default=0)
    skipped_count: Mapped[int] = mapped_column(default=0)
    submitted_readings: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    message: Mapped[str | None] = mapped_column(String(255), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.admin)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), default=None)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, default=None)
    password_hash: Mapped[str | None] = mapped_column(Text, default=None)
    portal_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    can_submit_meter_readings: Mapped[bool] = mapped_column(Boolean, default=False)
    session_version: Mapped[int] = mapped_column(default=1)
    access_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    bank_statement_name: Mapped[str | None] = mapped_column(String(255), default=None)
    rent_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    rent_currency: Mapped[RentCurrency] = mapped_column(Enum(RentCurrency), default=RentCurrency.uah)
    photo_path: Mapped[str | None] = mapped_column(String(512), default=None)
    passport_number: Mapped[str | None] = mapped_column(String(64), default=None)
    passport_issued_by: Mapped[str | None] = mapped_column(String(255), default=None)
    passport_issue_date: Mapped[date | None] = mapped_column(Date, default=None)
    passport_expiry_date: Mapped[date | None] = mapped_column(Date, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    phones: Mapped[list[TenantPhone]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    contacts: Mapped[list[TenantContact]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    tenancies: Mapped[list[Tenancy]] = relationship(back_populates="tenant")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="tenant")
    utility_payments: Mapped[list[UtilityPayment]] = relationship(back_populates="tenant")
    rent_ledgers: Mapped[list[RentLedger]] = relationship(back_populates="tenant")


class TenantPhone(Base):
    __tablename__ = "tenant_phones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    phone: Mapped[str] = mapped_column(String(32))

    tenant: Mapped[Tenant] = relationship(back_populates="phones")


class TenantContact(Base):
    __tablename__ = "tenant_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    relation: Mapped[str | None] = mapped_column(String(128), default=None)
    phone: Mapped[str | None] = mapped_column(String(32), default=None)
    note: Mapped[str | None] = mapped_column(String(255), default=None)

    tenant: Mapped[Tenant] = relationship(back_populates="contacts")


class Tenancy(Base):
    __tablename__ = "tenancies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)

    apartment: Mapped[Apartment] = relationship(back_populates="tenancies")
    tenant: Mapped[Tenant] = relationship(back_populates="tenancies")
    contracts: Mapped[list[RentalContract]] = relationship(back_populates="tenancy", cascade="all, delete-orphan")


class RentalContract(Base):
    __tablename__ = "rental_contracts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tenancy_id: Mapped[int] = mapped_column(ForeignKey("tenancies.id"), index=True)
    contract_start_date: Mapped[date] = mapped_column(Date)
    contract_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    term_months: Mapped[int | None] = mapped_column(default=None)
    extension_type: Mapped[ContractExtensionType] = mapped_column(Enum(ContractExtensionType), default=ContractExtensionType.none)
    rent_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    rent_currency: Mapped[RentCurrency] = mapped_column(Enum(RentCurrency), default=RentCurrency.uah)
    scan_path: Mapped[str | None] = mapped_column(String(512), default=None)
    note: Mapped[str | None] = mapped_column(String(255), default=None)

    tenancy: Mapped[Tenancy] = relationship(back_populates="contracts")


class MeterType(Base):
    __tablename__ = "meter_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    utility_type: Mapped[UtilityType] = mapped_column(Enum(UtilityType), index=True)
    default_service_name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    meters: Mapped[list[Meter]] = relationship(back_populates="meter_type")


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    meter_type_id: Mapped[int | None] = mapped_column(ForeignKey("meter_types.id"), index=True, default=None)
    utility_type: Mapped[UtilityType] = mapped_column(Enum(UtilityType))
    serial_number: Mapped[str | None] = mapped_column(String(128), default=None)
    initial_reading: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    installed_at: Mapped[date] = mapped_column(Date)
    retired_at: Mapped[date | None] = mapped_column(Date, default=None)
    replaced_by_meter_id: Mapped[int | None] = mapped_column(ForeignKey("meters.id"), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    apartment: Mapped[Apartment] = relationship(back_populates="meters")
    meter_type: Mapped[MeterType | None] = relationship(back_populates="meters")
    readings: Mapped[list[MeterReading]] = relationship(back_populates="meter", cascade="all, delete-orphan")
    electricity_plans: Mapped[list[ElectricityMeterPlan]] = relationship(
        back_populates="meter", cascade="all, delete-orphan"
    )

    @property
    def meter_type_name(self) -> str | None:
        return self.meter_type.name if self.meter_type else None

    @property
    def display_name(self) -> str:
        if self.meter_type and (self.meter_type.name or "").strip():
            return self.meter_type.name.strip()
        return {
            UtilityType.electricity: "Електролічильник",
            UtilityType.water: "Лічильник води",
            UtilityType.gas: "Газовий лічильник",
            UtilityType.heating: "Лічильник опалення",
            UtilityType.sewage: "Лічильник водовідведення",
            UtilityType.internet: "Інтернет-лічильник",
            UtilityType.other: "Лічильник",
        }.get(self.utility_type, "Лічильник")


class ApartmentServiceConnection(Base):
    __tablename__ = "apartment_service_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_catalog_id: Mapped[int] = mapped_column(ForeignKey("service_catalog.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), default=None, index=True)
    personal_account: Mapped[str | None] = mapped_column(String(128), default=None)
    started_at: Mapped[date] = mapped_column(Date, index=True)
    ended_at: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("apartment_automations.id"), default=None, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="service_connections")
    service_catalog: Mapped[ServiceCatalog] = relationship(back_populates="service_connections")
    provider: Mapped[Provider | None] = relationship(back_populates="service_connections")
    automation: Mapped[ApartmentAutomation | None] = relationship()
    charge_lines: Mapped[list[ConnectionChargeLine]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class ConnectionChargeLine(Base):
    __tablename__ = "connection_charge_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("apartment_service_connections.id"), index=True)
    line_kind: Mapped[ChargeLineKind] = mapped_column(Enum(ChargeLineKind), index=True)
    label: Mapped[str] = mapped_column(String(128))
    meter_id: Mapped[int | None] = mapped_column(ForeignKey("meters.id"), default=None, index=True)
    meter_register: Mapped[str] = mapped_column(String(32), default="total")
    derived_from_line_id: Mapped[int | None] = mapped_column(ForeignKey("connection_charge_lines.id"), default=None, index=True)
    initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)
    unit_name: Mapped[UnitType] = mapped_column(Enum(UnitType))
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    quantity_source: Mapped[QuantitySource] = mapped_column(Enum(QuantitySource), default=QuantitySource.fixed_1)
    quantity_multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("1.000"))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    connection: Mapped[ApartmentServiceConnection] = relationship(back_populates="charge_lines")
    meter: Mapped[Meter | None] = relationship()
    derived_from_line: Mapped[ConnectionChargeLine | None] = relationship(remote_side="ConnectionChargeLine.id")


class ElectricityMeterPlan(Base):
    __tablename__ = "electricity_meter_plans"
    __table_args__ = (
        UniqueConstraint("meter_id", "effective_from", name="uq_electricity_meter_plan_date"),
        Index("ix_electricity_meter_plans_lookup", "apartment_id", "meter_id", "effective_from"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    plan_mode: Mapped[ElectricityPlanMode] = mapped_column(Enum(ElectricityPlanMode), index=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)

    single_service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    day_service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    night_service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    peak_service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    semi_peak_service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    off_peak_service_name: Mapped[str | None] = mapped_column(String(128), default=None)

    single_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    day_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    night_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    peak_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    semi_peak_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    off_peak_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)

    single_initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)
    day_initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)
    night_initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)
    peak_initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)
    semi_peak_initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)
    off_peak_initial_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), default=None)

    note: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship()
    meter: Mapped[Meter] = relationship(back_populates="electricity_plans")


class Tariff(Base):
    __tablename__ = "tariffs"
    __table_args__ = (UniqueConstraint("apartment_id", "service_name", "effective_from", name="uq_tariff_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    charge_mode: Mapped[ChargeMode] = mapped_column(Enum(ChargeMode))
    utility_type: Mapped[UtilityType | None] = mapped_column(Enum(UtilityType), nullable=True)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    unit_name: Mapped[UnitType] = mapped_column(Enum(UnitType))
    meter_id: Mapped[int | None] = mapped_column(ForeignKey("meters.id"), default=None, index=True)
    meter_register: Mapped[str] = mapped_column(String(32), default="total")
    source_service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    fixed_quantity_source: Mapped[str] = mapped_column(String(32), default="auto")
    fixed_quantity_multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("1.000"))
    effective_from: Mapped[date] = mapped_column(Date, index=True)

    apartment: Mapped[Apartment] = relationship(back_populates="tariffs")
    meter: Mapped[Meter | None] = relationship()


class ApartmentTariffSetting(Base):
    __tablename__ = "apartment_tariff_settings"
    __table_args__ = (UniqueConstraint("apartment_id", "service_name", name="uq_apartment_service_tariff"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), default=None, index=True)
    provider_company: Mapped[str | None] = mapped_column(String(255), default=None)
    personal_account: Mapped[str | None] = mapped_column(String(128), default=None)
    cabinet_url: Mapped[str | None] = mapped_column(String(255), default=None)
    cabinet_login: Mapped[str | None] = mapped_column(String(128), default=None)
    cabinet_password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    last_tariff_check_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    auto_check_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_check_time: Mapped[str] = mapped_column(String(5), default="09:00")
    auto_check_timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
    auto_check_window_day_from: Mapped[int] = mapped_column(default=1)
    auto_check_window_day_to: Mapped[int] = mapped_column(default=10)
    auto_check_target_year: Mapped[int | None] = mapped_column(default=None, index=True)
    auto_check_target_month: Mapped[int | None] = mapped_column(default=None, index=True)
    auto_check_completed_for_period: Mapped[bool] = mapped_column(default=False)
    auto_check_status: Mapped[str | None] = mapped_column(String(32), default=None)
    auto_check_message: Mapped[str | None] = mapped_column(String(255), default=None)
    auto_check_last_value_raw: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    auto_check_last_value_rounded: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    auto_check_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    auto_check_last_updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    auto_check_next_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    apartment: Mapped[Apartment] = relationship(back_populates="tariff_settings")
    provider: Mapped[Provider | None] = relationship(back_populates="tariff_settings")


class ApartmentService(Base):
    __tablename__ = "apartment_services"
    __table_args__ = (UniqueConstraint("apartment_id", "service_name", name="uq_apartment_service"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    active_from: Mapped[date] = mapped_column(Date)
    inactive_from: Mapped[date | None] = mapped_column(Date, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="services")


class MeterReading(Base):
    __tablename__ = "meter_readings"
    __table_args__ = (UniqueConstraint("meter_id", "register_name", "year", "month", name="uq_reading_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    register_name: Mapped[str] = mapped_column(String(32), default="total")
    value: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    meter: Mapped[Meter] = relationship(back_populates="readings")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("apartment_id", "year", "month", name="uq_invoice_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    carry_over_debt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    utility_payment_received: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="invoices")
    tenant: Mapped[Tenant] = relationship(back_populates="invoices")
    items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    utility_payments: Mapped[list[UtilityPayment]] = relationship(back_populates="invoice")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128))
    utility_type: Mapped[UtilityType | None] = mapped_column(Enum(UtilityType), nullable=True)
    unit_name: Mapped[UnitType] = mapped_column(Enum(UnitType))
    consumption: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class UtilityPayment(Base):
    __tablename__ = "utility_payments"
    __table_args__ = (Index("ix_utility_payments_apartment_period", "apartment_id", "year", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), default=None, index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), default=None, index=True)
    payer_type: Mapped[str] = mapped_column(String(16), default="tenant")
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_at: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    confirmed: Mapped[bool] = mapped_column(default=True)

    tenant: Mapped[Tenant] = relationship(back_populates="utility_payments")
    invoice: Mapped[Invoice | None] = relationship(back_populates="utility_payments")


class RentLedger(Base):
    __tablename__ = "rent_ledgers"
    __table_args__ = (UniqueConstraint("apartment_id", "year", "month", name="uq_rent_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    accrual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    currency: Mapped[RentCurrency] = mapped_column(Enum(RentCurrency), default=RentCurrency.uah)
    paid_at: Mapped[date | None] = mapped_column(Date, default=None)
    confirmed: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None] = mapped_column(String(255), default=None)

    apartment: Mapped[Apartment] = relationship(back_populates="rent_ledgers")
    tenant: Mapped[Tenant] = relationship(back_populates="rent_ledgers")


class OwnerCharge(Base):
    __tablename__ = "owner_charges"
    __table_args__ = (Index("ix_owner_charges_apartment_period_kind", "apartment_id", "year", "month", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    tenancy_id: Mapped[int | None] = mapped_column(ForeignKey("tenancies.id"), default=None, index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    kind: Mapped[OwnerChargeKind] = mapped_column(Enum(OwnerChargeKind), default=OwnerChargeKind.owner_cost)
    category: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(255), default=None)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[RentCurrency] = mapped_column(Enum(RentCurrency), default=RentCurrency.uah)
    event_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="owner_charges")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    __table_args__ = (Index("ix_maintenance_records_apartment_dates", "apartment_id", "performed_at", "scheduled_for"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    tenancy_id: Mapped[int | None] = mapped_column(ForeignKey("tenancies.id"), default=None, index=True)
    maintenance_type: Mapped[MaintenanceType] = mapped_column(Enum(MaintenanceType))
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(255), default=None)
    contractor: Mapped[str | None] = mapped_column(String(255), default=None)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    currency: Mapped[RentCurrency] = mapped_column(Enum(RentCurrency), default=RentCurrency.uah)
    scheduled_for: Mapped[date | None] = mapped_column(Date, default=None)
    performed_at: Mapped[date | None] = mapped_column(Date, default=None)
    next_service_at: Mapped[date | None] = mapped_column(Date, default=None)
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="maintenance_records")


class BillingLock(Base):
    __tablename__ = "billing_locks"
    __table_args__ = (UniqueConstraint("apartment_id", "year", "month", name="uq_billing_lock_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="billing_locks")


class BillingMonthSnapshot(Base):
    __tablename__ = "billing_month_snapshots"
    __table_args__ = (
        UniqueConstraint("apartment_id", "year", "month", name="uq_billing_month_snapshot_period"),
        Index("ix_billing_month_snapshots_period", "apartment_id", "year", "month"),
        Index("ix_billing_month_snapshots_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), default="confirmed")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    utility_accrual: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    compensation_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    month_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    payments_in_month: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    rows_json: Mapped[str | None] = mapped_column(Text, default=None)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    confirmed_by: Mapped[str | None] = mapped_column(String(64), default=None)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    reopened_by: Mapped[str | None] = mapped_column(String(64), default=None)
    reopen_reason: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    apartment: Mapped[Apartment] = relationship(back_populates="billing_month_snapshots")
    statements: Mapped[list[BillingStatement]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class BillingStatement(Base):
    __tablename__ = "billing_statements"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "version", name="uq_billing_statements_snapshot_version"),
        Index("ix_billing_statements_period", "apartment_id", "year", "month"),
        Index("ix_billing_statements_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("billing_month_snapshots.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[BillingStatementStatus] = mapped_column(
        Enum(BillingStatementStatus), default=BillingStatementStatus.draft
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    generated_by: Mapped[str | None] = mapped_column(String(64), default=None)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    sent_channel: Mapped[str | None] = mapped_column(String(32), default=None)
    sent_to: Mapped[str | None] = mapped_column(String(255), default=None)
    month_closing_balance_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    payments_after_month_to_generated_at: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    balance_due_on_generated_at: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    payload_json: Mapped[str | None] = mapped_column(Text, default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    apartment: Mapped[Apartment] = relationship(back_populates="billing_statements")
    snapshot: Mapped[BillingMonthSnapshot] = relationship(back_populates="statements")


class BillingChangeLog(Base):
    __tablename__ = "billing_change_logs"
    __table_args__ = (
        Index(
            "ix_billing_change_logs_apartment_period_created",
            "apartment_id",
            "year",
            "month",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(default=None)
    service_name: Mapped[str | None] = mapped_column(String(128), default=None)
    actor_username: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="billing_change_logs")


class ServiceLedgerEntry(Base):
    __tablename__ = "service_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "apartment_id",
            "service_name",
            "year",
            "month",
            name="uq_service_ledger_period",
        ),
        Index(
            "ix_service_ledger_apartment_service_period",
            "apartment_id",
            "service_name",
            "year",
            "month",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    accrued: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    adjustment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    benefit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    subsidy: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="service_ledger_entries")


class ApartmentEquipment(Base):
    __tablename__ = "apartment_equipments"
    __table_args__ = (
        Index("ix_apartment_equipments_apartment_name", "apartment_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), default="other")
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)
    serial_number: Mapped[str | None] = mapped_column(String(128), default=None)
    installed_at: Mapped[date | None] = mapped_column(Date, default=None)
    manual_url: Mapped[str | None] = mapped_column(String(512), default=None)
    service_interval_days: Mapped[int | None] = mapped_column(default=None)
    last_service_at: Mapped[date | None] = mapped_column(Date, default=None)
    next_service_at: Mapped[date | None] = mapped_column(Date, default=None)
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    apartment: Mapped[Apartment] = relationship(back_populates="equipment_items")


class ProviderImportBatch(Base):
    __tablename__ = "provider_import_batches"
    __table_args__ = (
        Index("ix_provider_import_batches_provider_requested", "provider_code", "requested_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    provider_code: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ProviderImportBatchStatus] = mapped_column(
        Enum(ProviderImportBatchStatus), default=ProviderImportBatchStatus.pending
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    source_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    period_year: Mapped[int | None] = mapped_column(default=None, index=True)
    period_month: Mapped[int | None] = mapped_column(default=None, index=True)
    error_message: Mapped[str | None] = mapped_column(String(255), default=None)
    raw_meta_json: Mapped[str | None] = mapped_column(Text, default=None)

    apartment: Mapped[Apartment] = relationship(back_populates="provider_import_batches")
    rows: Mapped[list[ProviderImportRow]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class ProviderImportRow(Base):
    __tablename__ = "provider_import_rows"
    __table_args__ = (
        Index(
            "ix_provider_import_rows_batch_service_period",
            "batch_id",
            "service_catalog_code",
            "service_name",
            "period_year",
            "period_month",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("provider_import_batches.id"), index=True)
    service_catalog_code: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    period_year: Mapped[int] = mapped_column(index=True)
    period_month: Mapped[int] = mapped_column(index=True)
    accrued: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    adjustment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    benefit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    subsidy: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    status: Mapped[ProviderImportRowStatus] = mapped_column(
        Enum(ProviderImportRowStatus), default=ProviderImportRowStatus.staged
    )
    error_message: Mapped[str | None] = mapped_column(String(255), default=None)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, default=None)

    batch: Mapped[ProviderImportBatch] = relationship(back_populates="rows")
