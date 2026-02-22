from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

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


class InvoiceStatus(StrEnum):
    unpaid = "unpaid"
    paid = "paid"


class RentCurrency(StrEnum):
    uah = "UAH"
    usd = "USD"
    eur = "EUR"


class UnitType(StrEnum):
    kwh = "kWh"
    m3 = "m3"
    month = "month"


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


class Apartment(Base):
    __tablename__ = "apartments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    address: Mapped[str] = mapped_column(String(255))
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


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    utility_type: Mapped[UtilityType] = mapped_column(Enum(UtilityType))
    serial_number: Mapped[str | None] = mapped_column(String(128), default=None)
    initial_reading: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    installed_at: Mapped[date] = mapped_column(Date)

    apartment: Mapped[Apartment] = relationship(back_populates="meters")
    readings: Mapped[list[MeterReading]] = relationship(back_populates="meter", cascade="all, delete-orphan")


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
    effective_from: Mapped[date] = mapped_column(Date, index=True)

    apartment: Mapped[Apartment] = relationship(back_populates="tariffs")
    meter: Mapped[Meter | None] = relationship()


class ApartmentTariffSetting(Base):
    __tablename__ = "apartment_tariff_settings"
    __table_args__ = (UniqueConstraint("apartment_id", "service_name", name="uq_apartment_service_tariff"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    provider_company: Mapped[str | None] = mapped_column(String(255), default=None)
    personal_account: Mapped[str | None] = mapped_column(String(128), default=None)
    cabinet_url: Mapped[str | None] = mapped_column(String(255), default=None)
    cabinet_login: Mapped[str | None] = mapped_column(String(128), default=None)
    cabinet_password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    last_tariff_check_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    apartment: Mapped[Apartment] = relationship(back_populates="tariff_settings")


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
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), default=None, index=True)
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
