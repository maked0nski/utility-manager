from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    ChargeMode,
    ContractExtensionType,
    ChargeLineKind,
    InvoiceStatus,
    MaintenanceType,
    OwnerChargeKind,
    ProviderKind,
    RentCurrency,
    ServiceCalculationKind,
    UnitType,
    QuantitySource,
    UtilityType,
)

FIXED_QUANTITY_SOURCE_PATTERN = "^(auto|unit|apartment_registered_residents|apartment_area_m2)$"


class ApartmentCreate(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    country: str = Field(default="Україна", min_length=2, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    locality: str | None = Field(default=None, max_length=128)
    street: str | None = Field(default=None, max_length=128)
    house_number: str | None = Field(default=None, max_length=32)
    apartment_number: str | None = Field(default=None, max_length=32)
    postal_code: str | None = Field(default=None, max_length=16)
    registered_residents: int = Field(default=1, ge=1, le=50)
    area_m2: Decimal | None = Field(default=None, ge=0)
    living_area_m2: Decimal | None = Field(default=None, ge=0)
    entrance: str | None = Field(default=None, max_length=32)
    floor: str | None = Field(default=None, max_length=32)
    room_count: int | None = Field(default=None, ge=0, le=50)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    timezone: str = Field(default="Europe/Kyiv", min_length=3, max_length=64)
    location_note: str | None = None
    object_notes: str | None = None


class ApartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    address: str
    short_address: str
    country: str | None = None
    region: str | None = None
    locality: str | None = None
    street: str | None = None
    house_number: str | None = None
    apartment_number: str | None = None
    postal_code: str | None = None
    registered_residents: int = 1
    area_m2: Decimal | None = None
    living_area_m2: Decimal | None = None
    entrance: str | None = None
    floor: str | None = None
    room_count: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    google_maps_url: str | None = None
    timezone: str = "Europe/Kyiv"
    location_note: str | None = None
    object_notes: str | None = None


class ProviderCreate(BaseModel):
    name_full: str = Field(min_length=2, max_length=255)
    utility_type: UtilityType | None = None
    provider_kind: ProviderKind = ProviderKind.utility
    adapter_code: str = Field(default="manual_stub", min_length=2, max_length=64)
    is_active: bool = True
    note: str | None = None


class ProviderUpdate(BaseModel):
    name_full: str = Field(min_length=2, max_length=255)
    utility_type: UtilityType | None = None
    provider_kind: ProviderKind = ProviderKind.utility
    adapter_code: str = Field(default="manual_stub", min_length=2, max_length=64)
    is_active: bool = True
    note: str | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name_full: str
    utility_type: UtilityType | None
    provider_kind: ProviderKind
    adapter_code: str
    is_active: bool
    note: str | None = None
    created_at: datetime


class ServiceCatalogCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    calculation_kind: ServiceCalculationKind
    unit_name: UnitType
    requires_meter: bool = False
    allowed_meter_utility_type: UtilityType | None = None
    default_provider_utility_type: UtilityType | None = None
    derived_from_service_id: int | None = None
    display_order: int = Field(default=100, ge=0, le=9999)
    is_active: bool = True


class ServiceCatalogUpdate(ServiceCatalogCreate):
    pass


class ServiceCatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    calculation_kind: ServiceCalculationKind
    unit_name: UnitType
    requires_meter: bool
    allowed_meter_utility_type: UtilityType | None = None
    default_provider_utility_type: UtilityType | None = None
    derived_from_service_id: int | None = None
    display_order: int
    is_active: bool
    created_at: datetime


class ApartmentServiceConnectionCreate(BaseModel):
    apartment_id: int
    service_catalog_id: int
    provider_id: int | None = None
    personal_account: str | None = None
    started_at: date
    ended_at: date | None = None
    status: str = Field(default="active", min_length=2, max_length=32)
    note: str | None = None
    automation_id: int | None = None


class ApartmentServiceConnectionUpdate(BaseModel):
    provider_id: int | None = None
    personal_account: str | None = None
    started_at: date
    ended_at: date | None = None
    status: str = Field(default="active", min_length=2, max_length=32)
    note: str | None = None
    automation_id: int | None = None


class ConnectionChargeLineCreate(BaseModel):
    line_kind: ChargeLineKind
    label: str = Field(min_length=2, max_length=128)
    meter_id: int | None = None
    meter_register: str = Field(default="total", min_length=2, max_length=32)
    derived_from_line_id: int | None = None
    initial_reading: Decimal | None = Field(default=None, ge=0)
    unit_name: UnitType
    price_per_unit: Decimal = Field(gt=0)
    quantity_source: QuantitySource = QuantitySource.fixed_1
    quantity_multiplier: Decimal = Field(default=Decimal("1"), gt=0)
    effective_from: date
    effective_to: date | None = None
    is_active: bool = True


class ConnectionChargeLineUpdate(ConnectionChargeLineCreate):
    pass


class ConnectionChargeLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    connection_id: int
    line_kind: ChargeLineKind
    label: str
    meter_id: int | None = None
    meter_register: str
    derived_from_line_id: int | None = None
    initial_reading: Decimal | None = None
    unit_name: UnitType
    price_per_unit: Decimal
    quantity_source: QuantitySource
    quantity_multiplier: Decimal
    effective_from: date
    effective_to: date | None = None
    is_active: bool
    created_at: datetime


class ApartmentServiceConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    apartment_id: int
    service_catalog_id: int
    provider_id: int | None = None
    personal_account: str | None = None
    started_at: date
    ended_at: date | None = None
    status: str
    note: str | None = None
    automation_id: int | None = None
    created_at: datetime
    charge_lines: list[ConnectionChargeLineOut] = Field(default_factory=list)


class MeterTypeCreate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    utility_type: UtilityType
    sort_order: int = Field(default=100, ge=0, le=9999)
    is_active: bool = True


class MeterTypeUpdate(MeterTypeCreate):
    pass


class MeterTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    utility_type: UtilityType
    sort_order: int
    is_active: bool


class ApartmentEquipmentCreate(BaseModel):
    name: str
    category: str = "other"
    model_name: str | None = None
    serial_number: str | None = None
    installed_at: date | None = None
    manual_url: str | None = None
    service_interval_days: int | None = Field(default=None, ge=1)
    last_service_at: date | None = None
    next_service_at: date | None = None
    note: str | None = None
    is_active: bool = True


class ApartmentEquipmentUpdate(ApartmentEquipmentCreate):
    pass


class ApartmentEquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    apartment_id: int
    name: str
    category: str
    model_name: str | None
    serial_number: str | None
    installed_at: date | None
    manual_url: str | None
    service_interval_days: int | None
    last_service_at: date | None
    next_service_at: date | None
    note: str | None
    is_active: bool


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
    email: str | None = None
    access_code: str = Field(min_length=4, max_length=64)


class TenantUpdate(BaseModel):
    full_name: str
    primary_phone: str | None = None
    email: str | None = None
    phones: list[str] = Field(default_factory=list)
    contacts: list[TenantContactIn] = Field(default_factory=list)
    bank_statement_name: str | None = None
    rent_amount: Decimal | None = None
    rent_currency: RentCurrency = RentCurrency.uah
    passport_number: str | None = None
    passport_issued_by: str | None = None
    passport_issue_date: date | None = None
    passport_expiry_date: date | None = None
    portal_enabled: bool | None = None
    can_submit_meter_readings: bool | None = None
    portal_password: str | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None
    email: str | None = None
    access_code: str
    bank_statement_name: str | None
    rent_amount: Decimal | None
    rent_currency: RentCurrency
    photo_url: str | None
    passport_number: str | None
    passport_issued_by: str | None
    passport_issue_date: date | None
    passport_expiry_date: date | None
    portal_enabled: bool = False
    can_submit_meter_readings: bool = False
    phones: list[str] = Field(default_factory=list)
    contacts: list[TenantContactOut] = Field(default_factory=list)
    is_active_now: bool = False


class TenantBasicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None
    email: str | None = None
    access_code: str
    portal_enabled: bool = False
    can_submit_meter_readings: bool = False
    is_active_now: bool = False


class TenantLoginPayload(BaseModel):
    email: str
    password: str


class TenantChangePasswordPayload(BaseModel):
    new_password: str
    confirm_password: str


class TenantPasswordResetPayload(BaseModel):
    email: str
    access_code: str
    new_password: str
    confirm_password: str


class TenantProfileUpdate(BaseModel):
    email: str | None = None
    primary_phone: str | None = None
    phones: list[str] = Field(default_factory=list)


class TenantSessionOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class TenantMeOut(BaseModel):
    id: int
    full_name: str
    email: str | None = None
    phone: str | None = None
    phones: list[str] = Field(default_factory=list)
    portal_enabled: bool = False
    can_submit_meter_readings: bool = False


class TenancyCreate(BaseModel):
    apartment_id: int
    tenant_id: int
    start_date: date


class TenantRefreshPayload(BaseModel):
    refresh_token: str


class MeterCreate(BaseModel):
    apartment_id: int
    meter_type_id: int
    serial_number: str | None = None
    initial_reading: Decimal | None = Field(default=None, ge=0)
    installed_at: date


class MeterUpdate(BaseModel):
    meter_type_id: int
    serial_number: str | None = None
    initial_reading: Decimal | None = Field(default=None, ge=0)
    installed_at: date


class MeterReplaceRequest(BaseModel):
    serial_number: str | None = None
    initial_reading: Decimal = Field(ge=0)
    installed_at: date


class MeterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    apartment_id: int
    meter_type_id: int | None = None
    meter_type_name: str | None = None
    display_name: str | None = None
    utility_type: UtilityType
    serial_number: str | None
    initial_reading: Decimal
    installed_at: date
    retired_at: date | None = None
    replaced_by_meter_id: int | None = None
    is_active: bool = True


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
    fixed_quantity_source: str = Field(default="auto", pattern=FIXED_QUANTITY_SOURCE_PATTERN)
    fixed_quantity_multiplier: Decimal = Field(default=Decimal("1"), gt=0)


class TariffUpdate(BaseModel):
    price_per_unit: Decimal = Field(gt=0)
    unit_name: UnitType
    fixed_quantity_source: str = Field(default="auto", pattern=FIXED_QUANTITY_SOURCE_PATTERN)
    fixed_quantity_multiplier: Decimal = Field(default=Decimal("1"), gt=0)


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
    fixed_quantity_source: str = "auto"
    fixed_quantity_multiplier: Decimal = Decimal("1")
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


class ElectricityPlanMode(str):
    pass


class ElectricityPlanUpsert(BaseModel):
    plan_mode: str = Field(pattern="^(single|dual|day_night|tri_zone)$")
    meter_id: int
    effective_from: date
    single_service_name: str = "Електроенергія"
    day_service_name: str = "Електроенергія денний тариф"
    night_service_name: str = "Електроенергія нічний тариф"
    peak_service_name: str = "Електроенергія піковий тариф"
    semi_peak_service_name: str = "Електроенергія напівпіковий тариф"
    off_peak_service_name: str = "Електроенергія нічний тариф"
    single_price_per_unit: Decimal | None = Field(default=None, gt=0)
    day_price_per_unit: Decimal | None = Field(default=None, gt=0)
    night_price_per_unit: Decimal | None = Field(default=None, gt=0)
    peak_price_per_unit: Decimal | None = Field(default=None, gt=0)
    semi_peak_price_per_unit: Decimal | None = Field(default=None, gt=0)
    off_peak_price_per_unit: Decimal | None = Field(default=None, gt=0)
    single_initial_reading: Decimal | None = Field(default=None, ge=0)
    day_initial_reading: Decimal | None = Field(default=None, ge=0)
    night_initial_reading: Decimal | None = Field(default=None, ge=0)
    peak_initial_reading: Decimal | None = Field(default=None, ge=0)
    semi_peak_initial_reading: Decimal | None = Field(default=None, ge=0)
    off_peak_initial_reading: Decimal | None = Field(default=None, ge=0)


class ElectricityPlanHistoryOut(BaseModel):
    id: int
    apartment_id: int
    meter_id: int
    meter_service_name: str
    meter_serial_number: str | None = None
    plan_mode: str
    effective_from: date
    single_service_name: str | None = None
    day_service_name: str | None = None
    night_service_name: str | None = None
    peak_service_name: str | None = None
    semi_peak_service_name: str | None = None
    off_peak_service_name: str | None = None
    single_price_per_unit: Decimal | None = None
    day_price_per_unit: Decimal | None = None
    night_price_per_unit: Decimal | None = None
    peak_price_per_unit: Decimal | None = None
    semi_peak_price_per_unit: Decimal | None = None
    off_peak_price_per_unit: Decimal | None = None
    single_initial_reading: Decimal | None = None
    day_initial_reading: Decimal | None = None
    night_initial_reading: Decimal | None = None
    peak_initial_reading: Decimal | None = None
    semi_peak_initial_reading: Decimal | None = None
    off_peak_initial_reading: Decimal | None = None
    note: str | None = None
    created_at: datetime
    can_delete: bool = False
    delete_block_reason: str | None = None


class MeterExpectedRegisterItem(BaseModel):
    register_name: str
    label: str
    service_name: str | None = None
    previous_reading: Decimal | None = None
    current_reading: Decimal | None = None


class MeterExpectedRegistersOut(BaseModel):
    meter_id: int
    meter_service_name: str
    plan_mode: str
    effective_from: date | None = None
    registers: list[MeterExpectedRegisterItem]


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
    amount: Decimal = Field(gt=0)
    paid_at: date
    note: str | None = None
    payer_type: str | None = Field(default=None, pattern="^(tenant|owner)$")
    tenant_id: int | None = None


class UtilityPaymentUpdate(BaseModel):
    amount: Decimal = Field(gt=0)
    paid_at: date
    note: str | None = None
    payer_type: str | None = Field(default=None, pattern="^(tenant|owner)$")
    tenant_id: int | None = None


class UtilityPaymentOut(BaseModel):
    id: int
    apartment_id: int
    tenant_id: int | None = None
    tenant_name: str | None = None
    year: int
    month: int
    amount: Decimal
    paid_at: date
    note: str | None = None
    payer_type: str


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
    latest_payment_amount: Decimal | None = None
    latest_payment_date: date | None = None


class TenantHistory(BaseModel):
    invoices: list[InvoiceOut]


class ApartmentOverviewOut(BaseModel):
    apartment_id: int
    code: str
    address: str
    short_address: str
    tenant_name: str | None
    utility_balance: Decimal
    rent_balance: Decimal
    total_balance: Decimal


class CalculationRowOut(BaseModel):
    line_id: int | None = None
    meter_id: int | None = None
    source_line_id: int | None = None
    service_name: str
    service_group_key: str | None = None
    service_group_label: str | None = None
    service_line_label: str | None = None
    meter_register: str = "total"
    meter_register_label: str | None = None
    meter_plan_mode: str | None = None
    meter_expected_registers: list[str] = Field(default_factory=list)
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
    actual_current_balance: Decimal | None = None
    report_generated_at: date | None = None
    report_payments_to_date: Decimal | None = None
    report_payment_date: date | None = None
    report_payment_note: str | None = None
    report_balance: Decimal | None = None


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
    short_address: str
    country: str | None = None
    region: str | None = None
    locality: str | None = None
    street: str | None = None
    house_number: str | None = None
    apartment_number: str | None = None
    postal_code: str | None = None
    registered_residents: int = 1
    area_m2: Decimal | None = None
    living_area_m2: Decimal | None = None
    entrance: str | None = None
    floor: str | None = None
    room_count: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    google_maps_url: str | None = None
    timezone: str = "Europe/Kyiv"
    location_note: str | None = None
    object_notes: str | None = None
    tenant: TenantOut | None
    year: int
    month: int
    utility_balance: BalanceExplainOut
    rent: RentMonthOut | None
    rows: list[CalculationRowOut]
    calc_locked: bool = False


class TariffSettingUpsert(BaseModel):
    service_name: str
    provider_id: int | None = None
    provider_company: str | None = None
    personal_account: str | None = None
    cabinet_url: str | None = None
    cabinet_login: str | None = None
    cabinet_password: str | None = None
    last_tariff_check_at: datetime | None = None
    auto_check_enabled: bool | None = None
    auto_check_time: str | None = None
    auto_check_timezone: str | None = None
    auto_check_window_day_from: int | None = Field(default=None, ge=1, le=31)
    auto_check_window_day_to: int | None = Field(default=None, ge=1, le=31)


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
    fixed_quantity_source: str = "auto"
    fixed_quantity_multiplier: Decimal = Decimal("1")
    apartment_registered_residents: int = 1
    apartment_area_m2: Decimal = Decimal("0")
    active_from: date | None = None
    inactive_from: date | None = None
    is_active_for_period: bool = True
    provider_id: int | None = None
    provider_name: str | None = None
    provider_company: str | None
    automation_connected: bool = False
    personal_account: str | None
    cabinet_url: str | None
    cabinet_login: str | None
    cabinet_password: str | None
    last_tariff_check_at: datetime | None
    auto_check_enabled: bool = False
    auto_check_time: str = "09:00"
    auto_check_timezone: str = "Europe/Kyiv"
    auto_check_window_day_from: int = 1
    auto_check_window_day_to: int = 10
    auto_check_target_year: int | None = None
    auto_check_target_month: int | None = None
    auto_check_completed_for_period: bool = False
    auto_check_status: str | None = None
    auto_check_message: str | None = None
    auto_check_last_value_raw: Decimal | None = None
    auto_check_last_value_rounded: Decimal | None = None
    auto_check_last_checked_at: datetime | None = None
    auto_check_last_updated_at: datetime | None = None
    auto_check_next_at: datetime | None = None
    submit_enabled: bool = False
    submit_target_year: int | None = None
    submit_target_month: int | None = None
    submit_completed_for_period: bool = False
    submit_next_at: datetime | None = None
    submit_state_reason: str | None = None


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


class AutomationRowOut(BaseModel):
    automation_id: int | None = None
    template_id: int | None = None
    template_name: str | None = None
    template_code: str | None = None
    apartment_id: int
    apartment_code: str
    apartment_address: str
    service_name: str
    provider_id: int | None = None
    provider_name: str | None = None
    provider_company: str | None = None
    personal_account: str | None = None
    cabinet_url: str | None = None
    cabinet_login: str | None = None
    cabinet_password: str | None = None
    auto_check_enabled: bool = False
    auto_check_time: str = "09:00"
    auto_check_timezone: str = "Europe/Kyiv"
    auto_check_window_day_from: int = 1
    auto_check_window_day_to: int = 10
    auto_check_target_year: int | None = None
    auto_check_target_month: int | None = None
    auto_check_completed_for_period: bool = False
    auto_check_status: str | None = None
    auto_check_message: str | None = None
    auto_check_last_value_raw: Decimal | None = None
    auto_check_last_value_rounded: Decimal | None = None
    auto_check_last_checked_at: datetime | None = None
    auto_check_last_updated_at: datetime | None = None
    auto_check_next_at: datetime | None = None
    submit_enabled: bool = False
    submit_time: str = "09:00"
    submit_window_day_from: int = 28
    submit_window_day_to: int = 3
    submit_target_year: int | None = None
    submit_target_month: int | None = None
    submit_completed_for_period: bool = False
    submit_next_at: datetime | None = None
    submit_state_reason: str | None = None


class AutomationTemplateCreate(BaseModel):
    code: str = Field(min_length=3, max_length=96)
    name: str = Field(min_length=2, max_length=255)
    provider_id: int | None = None
    utility_type: UtilityType | None = None
    cabinet_url: str | None = None
    description: str | None = None
    supports_accrual: bool = True
    supports_meter_submit: bool = False
    is_active: bool = True


class AutomationTemplateUpdate(AutomationTemplateCreate):
    pass


class AutomationTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    provider_id: int | None = None
    provider_name: str | None = None
    utility_type: UtilityType | None = None
    cabinet_url: str | None = None
    description: str | None = None
    supports_accrual: bool = True
    supports_meter_submit: bool = False
    is_active: bool = True
    created_at: datetime


class ApartmentAutomationUpsert(BaseModel):
    apartment_id: int
    template_id: int
    provider_id: int | None = None
    personal_account: str | None = None
    cabinet_url: str | None = None
    cabinet_login: str | None = None
    cabinet_password: str | None = None
    is_enabled: bool = True
    accrual_enabled: bool = True
    accrual_time: str = "09:00"
    accrual_window_day_from: int = Field(default=1, ge=1, le=31)
    accrual_window_day_to: int = Field(default=10, ge=1, le=31)
    submit_enabled: bool = False
    submit_time: str = "09:00"
    submit_window_day_from: int = Field(default=28, ge=1, le=31)
    submit_window_day_to: int = Field(default=3, ge=1, le=31)


class ApartmentAutomationOut(BaseModel):
    id: int
    apartment_id: int
    apartment_address: str
    apartment_timezone: str
    template_id: int
    template_name: str
    template_code: str
    provider_id: int | None = None
    provider_name: str | None = None
    personal_account: str | None = None
    cabinet_url: str | None = None
    cabinet_login: str | None = None
    cabinet_password: str | None = None
    is_enabled: bool = True
    accrual_enabled: bool = True
    accrual_time: str = "09:00"
    accrual_window_day_from: int = 1
    accrual_window_day_to: int = 10
    submit_enabled: bool = False
    submit_time: str = "09:00"
    submit_window_day_from: int = 28
    submit_window_day_to: int = 3
    submit_target_year: int | None = None
    submit_target_month: int | None = None
    submit_completed_for_period: bool = False
    submit_next_at: datetime | None = None
    submit_state_reason: str | None = None
    auto_check_status: str | None = None
    auto_check_message: str | None = None
    auto_check_last_checked_at: datetime | None = None
    auto_check_last_updated_at: datetime | None = None
    auto_check_next_at: datetime | None = None


class AutomationRunLogOut(BaseModel):
    id: int
    automation_id: int | None = None
    apartment_id: int
    service_name: str
    register_name: str | None = None
    target_year: int | None = None
    target_month: int | None = None
    mode: str
    status: str
    message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class MeterSubmitEvaluateOut(BaseModel):
    can_submit: bool
    reason: str
    automation_id: int | None = None
    template_name: str | None = None
    target_year: int | None = None
    target_month: int | None = None


class MeterSubmitDispatchRequest(BaseModel):
    apartment_id: int
    meter_id: int
    register_name: str = "total"
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class MeterSubmitDispatchOut(BaseModel):
    dispatched: bool
    message: str


class AutomationCycleRunOut(BaseModel):
    id: int | None = None
    trigger_mode: str = "scheduled"
    processed_accrual_automations: int
    processed_submit_automations: int
    processed_legacy_settings: int
    submitted_readings: int
    message: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    phases: list["AutomationCyclePhaseRunOut"] = Field(default_factory=list)


class AutomationCyclePhaseRunOut(BaseModel):
    id: int | None = None
    phase: str
    status: str = "completed"
    processed_count: int
    skipped_count: int = 0
    submitted_readings: int = 0
    duration_ms: int | None = None
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AutomationCyclePreviewItem(BaseModel):
    automation_id: int | None = None
    apartment_id: int
    apartment_address: str
    service_name: str
    phase: str
    action: str
    reason_code: str
    reason: str


class AutomationCyclePreviewOut(BaseModel):
    items: list[AutomationCyclePreviewItem]
    message: str


class AutomationCycleRunLogDetailOut(BaseModel):
    id: int
    apartment_id: int
    apartment_address: str
    service_name: str
    phase: str
    mode: str
    status: str
    register_name: str | None = None
    target_year: int | None = None
    target_month: int | None = None
    message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class AutomationCycleRunDetailOut(BaseModel):
    id: int
    trigger_mode: str
    message: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    phases: list[AutomationCyclePhaseRunOut] = Field(default_factory=list)
    logs: list[AutomationCycleRunLogDetailOut] = Field(default_factory=list)


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
