from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    ChargeMode,
    ContractExtensionType,
    InvoiceStatus,
    MaintenanceType,
    OwnerChargeKind,
    RentCurrency,
    UnitType,
    UtilityType,
)


class ApartmentCreate(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    address: str = Field(min_length=1, max_length=255)


class ApartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    address: str


class TenantContactIn(BaseModel):
    name: str
    relation: str | None = None
    phone: str | None = None
    note: str | None = None


class TenantContactOut(TenantContactIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TenantCreate(BaseModel):
    full_name: str
    phone: str | None = None
    access_code: str = Field(min_length=4, max_length=64)


class TenantUpdate(BaseModel):
    full_name: str
    primary_phone: str | None = None
    phones: list[str] = Field(default_factory=list)
    contacts: list[TenantContactIn] = Field(default_factory=list)
    bank_statement_name: str | None = None
    rent_amount: Decimal | None = None
    rent_currency: RentCurrency = RentCurrency.uah
    passport_number: str | None = None
    passport_issued_by: str | None = None
    passport_issue_date: date | None = None
    passport_expiry_date: date | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None
    access_code: str
    bank_statement_name: str | None
    rent_amount: Decimal | None
    rent_currency: RentCurrency
    photo_url: str | None
    passport_number: str | None
    passport_issued_by: str | None
    passport_issue_date: date | None
    passport_expiry_date: date | None
    phones: list[str] = Field(default_factory=list)
    contacts: list[TenantContactOut] = Field(default_factory=list)


class TenantBasicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None
    access_code: str


class TenancyCreate(BaseModel):
    apartment_id: int
    tenant_id: int
    start_date: date


class MeterCreate(BaseModel):
    apartment_id: int
    service_name: str
    utility_type: UtilityType
    serial_number: str | None = None
    initial_reading: Decimal = Field(ge=0)
    installed_at: date


class MeterUpdate(BaseModel):
    service_name: str
    utility_type: UtilityType
    serial_number: str | None = None
    initial_reading: Decimal = Field(ge=0)
    installed_at: date


class MeterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    apartment_id: int
    service_name: str
    utility_type: UtilityType
    serial_number: str | None
    initial_reading: Decimal
    installed_at: date


class TariffCreate(BaseModel):
    apartment_id: int
    service_name: str
    charge_mode: ChargeMode
    utility_type: UtilityType | None = None
    price_per_unit: Decimal = Field(gt=0)
    unit_name: UnitType
    effective_from: date
    initial_meter_reading: Decimal | None = Field(default=None, ge=0)
    meter_serial_number: str | None = None
    meter_id: int | None = None
    meter_register: str = "total"
    source_service_name: str | None = None


class TariffUpdate(BaseModel):
    price_per_unit: Decimal = Field(gt=0)
    unit_name: UnitType


class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    apartment_id: int
    service_name: str
    charge_mode: ChargeMode
    utility_type: UtilityType | None
    price_per_unit: Decimal
    unit_name: UnitType
    meter_id: int | None = None
    meter_register: str = "total"
    source_service_name: str | None = None
    effective_from: date


class ReadingCreate(BaseModel):
    meter_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    register_name: str = "total"
    value: Decimal = Field(ge=0)


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    meter_id: int
    year: int
    month: int
    register_name: str
    value: Decimal


class BillingGenerateRequest(BaseModel):
    apartment_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class BillingRecalculateRequest(BillingGenerateRequest):
    pass


class BillingLockRequest(BillingGenerateRequest):
    pass


class MissingServiceOut(BaseModel):
    service_name: str
    charge_mode: ChargeMode
    unit_name: UnitType


class ServiceActivationUpdate(BaseModel):
    inactive_from: date | None = None


class TariffApplyFromPeriod(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    price_per_unit: Decimal = Field(gt=0)
    unit_name: UnitType


class TariffBindingUpdate(BaseModel):
    meter_id: int | None = None
    meter_register: str = "total"
    source_service_name: str | None = None


class MeterInitialReadingUpdate(BaseModel):
    value: Decimal = Field(ge=0)


class UtilityPaymentCreate(BaseModel):
    apartment_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(gt=0)
    paid_at: date
    note: str | None = None


class ServiceLedgerUpsert(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    accrued: Decimal = Field(default=Decimal("0.00"))
    paid: Decimal = Field(default=Decimal("0.00"))
    adjustment: Decimal = Field(default=Decimal("0.00"))
    benefit: Decimal = Field(default=Decimal("0.00"))
    subsidy: Decimal = Field(default=Decimal("0.00"))


class ServiceLedgerRowOut(BaseModel):
    id: int
    apartment_id: int
    service_name: str
    year: int
    month: int
    accrued: Decimal
    paid: Decimal
    adjustment: Decimal
    benefit: Decimal
    subsidy: Decimal
    opening_balance: Decimal
    closing_balance: Decimal
    updated_at: datetime


class RentRecordUpsert(BaseModel):
    apartment_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    accrual_amount: Decimal = Field(ge=0)
    payment_amount: Decimal = Field(ge=0)
    paid_at: date | None = None
    confirmed: bool = False
    note: str | None = None
    currency: RentCurrency = RentCurrency.uah


class InvoiceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    service_name: str
    utility_type: UtilityType | None
    unit_name: UnitType
    consumption: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    apartment_id: int
    tenant_id: int
    year: int
    month: int
    status: InvoiceStatus
    total_amount: Decimal
    carry_over_debt: Decimal
    utility_payment_received: Decimal
    closing_balance: Decimal
    items: list[InvoiceItemOut]


class TenantDashboard(BaseModel):
    tenant_id: int
    tenant_name: str
    apartment_code: str
    apartment_address: str
    current_debt: Decimal
    current_invoice: InvoiceOut | None


class TenantHistory(BaseModel):
    invoices: list[InvoiceOut]


class ApartmentOverviewOut(BaseModel):
    apartment_id: int
    code: str
    address: str
    tenant_name: str | None
    utility_balance: Decimal
    rent_balance: Decimal
    total_balance: Decimal


class CalculationRowOut(BaseModel):
    meter_id: int | None = None
    service_name: str
    meter_register: str = "total"
    previous_reading: Decimal | None
    current_reading: Decimal | None
    difference: Decimal | None
    unit_name: UnitType
    unit_price: Decimal
    amount: Decimal
    can_edit_previous: bool = False


class BalanceExplainOut(BaseModel):
    previous_month_debt: Decimal
    month_charges: Decimal
    month_payments: Decimal
    month_payment_date: date | None = None
    month_payment_note: str | None = None
    current_balance: Decimal


class BillingChangeLogOut(BaseModel):
    id: int
    apartment_id: int
    year: int
    month: int
    action: str
    entity_type: str
    entity_id: int | None
    service_name: str | None
    actor_username: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RentMonthOut(BaseModel):
    accrual_amount: Decimal
    payment_amount: Decimal
    currency: RentCurrency
    paid_at: date | None
    confirmed: bool
    note: str | None


class ApartmentDetailOut(BaseModel):
    apartment_id: int
    code: str
    address: str
    tenant: TenantOut | None
    year: int
    month: int
    utility_balance: BalanceExplainOut
    rent: RentMonthOut | None
    rows: list[CalculationRowOut]
    calc_locked: bool = False


class TariffSettingUpsert(BaseModel):
    service_name: str
    provider_company: str | None = None
    personal_account: str | None = None
    cabinet_url: str | None = None
    cabinet_login: str | None = None
    cabinet_password: str | None = None
    last_tariff_check_at: datetime | None = None


class ApartmentTariffRowOut(BaseModel):
    tariff_id: int
    service_name: str
    charge_mode: ChargeMode
    utility_type: UtilityType | None
    unit_name: UnitType
    price_per_unit: Decimal
    meter_id: int | None = None
    meter_register: str = "total"
    source_service_name: str | None = None
    active_from: date | None = None
    inactive_from: date | None = None
    is_active_for_period: bool = True
    provider_company: str | None
    personal_account: str | None
    cabinet_url: str | None
    cabinet_login: str | None
    cabinet_password: str | None
    last_tariff_check_at: datetime | None


class MeterPeriodRowOut(BaseModel):
    meter_id: int
    service_name: str
    utility_type: UtilityType
    serial_number: str | None
    year: int
    month: int
    current_value: Decimal | None
    previous_value: Decimal
    difference: Decimal | None


class ContractCreate(BaseModel):
    contract_start_date: date
    contract_end_date: date | None = None
    term_months: int | None = None
    extension_type: ContractExtensionType = ContractExtensionType.none
    rent_amount: Decimal | None = None
    rent_currency: RentCurrency = RentCurrency.uah
    note: str | None = None


class RentalContractOut(BaseModel):
    id: int
    contract_start_date: date
    contract_end_date: date | None
    term_months: int | None
    extension_type: ContractExtensionType
    rent_amount: Decimal | None
    rent_currency: RentCurrency
    note: str | None
    scan_url: str | None = None


class TenancyOut(BaseModel):
    id: int
    start_date: date
    end_date: date | None
    tenant: TenantOut | None
    contracts: list[RentalContractOut] = Field(default_factory=list)


class OwnerChargeCreate(BaseModel):
    apartment_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    kind: OwnerChargeKind = OwnerChargeKind.owner_cost
    category: str = "Інше"
    description: str | None = None
    amount: Decimal
    currency: RentCurrency = RentCurrency.uah
    event_date: date

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v):
        if isinstance(v, str):
            cleaned = v.strip().replace(" ", "").replace(",", ".")
            if not cleaned:
                raise ValueError("Amount is required.")
            return Decimal(cleaned)
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if v is None:
            return "Інше"
        if isinstance(v, str):
            text = v.strip()
            return text or "Інше"
        return v


class OwnerChargeUpdate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    kind: OwnerChargeKind = OwnerChargeKind.owner_cost
    category: str = "Інше"
    description: str | None = None
    amount: Decimal
    currency: RentCurrency = RentCurrency.uah
    event_date: date

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, v):
        if isinstance(v, str):
            cleaned = v.strip().replace(" ", "").replace(",", ".")
            if not cleaned:
                raise ValueError("Amount is required.")
            return Decimal(cleaned)
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if v is None:
            return "Інше"
        if isinstance(v, str):
            text = v.strip()
            return text or "Інше"
        return v


class OwnerChargeOut(BaseModel):
    id: int
    apartment_id: int
    year: int
    month: int
    kind: OwnerChargeKind
    category: str
    description: str | None
    amount: Decimal
    currency: RentCurrency
    event_date: date


class MaintenanceRecordCreate(BaseModel):
    apartment_id: int
    maintenance_type: MaintenanceType
    title: str
    description: str | None = None
    contractor: str | None = None
    amount: Decimal | None = None
    currency: RentCurrency = RentCurrency.uah
    scheduled_for: date | None = None
    performed_at: date | None = None
    next_service_at: date | None = None
    note: str | None = None


class MaintenanceRecordUpdate(BaseModel):
    maintenance_type: MaintenanceType
    title: str
    description: str | None = None
    contractor: str | None = None
    amount: Decimal | None = None
    currency: RentCurrency = RentCurrency.uah
    scheduled_for: date | None = None
    performed_at: date | None = None
    next_service_at: date | None = None
    note: str | None = None


class MaintenanceRecordOut(BaseModel):
    id: int
    apartment_id: int
    maintenance_type: MaintenanceType
    title: str
    description: str | None
    contractor: str | None
    amount: Decimal | None
    currency: RentCurrency
    scheduled_for: date | None
    performed_at: date | None
    next_service_at: date | None
    note: str | None
