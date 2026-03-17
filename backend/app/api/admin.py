from datetime import UTC, date, datetime, timedelta
from calendar import monthrange
from decimal import Decimal
import json
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, require_authenticated_admin, require_write_access
from app.core.config import settings
from app.core.security import decrypt_text, encrypt_text
from app.core.auth import hash_password
from app.db.session import get_db
from app.models import (
    AdminUser,
    Apartment,
    ApartmentAutomation,
    ApartmentEquipment,
    ApartmentServiceConnection,
    AutomationTemplate,
    AutomationCyclePhaseRun,
    AutomationCycleRun,
    AutomationRunLog,
    BillingChangeLog,
    BillingLock,
    ChargeLineKind,
    ChargeMode,
    ContractExtensionType,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    ConnectionChargeLine,
    Meter,
    MeterType,
    MeterReading,
    MaintenanceRecord,
    OwnerCharge,
    OwnerChargeKind,
    Provider,
    ProviderImportBatch,
    ProviderImportRow,
    QuantitySource,
    RentLedger,
    RentCurrency,
    RentalContract,
    ServiceCatalog,
    ServiceLedgerEntry,
    Tenancy,
    Tenant,
    TenantContact,
    TenantPhone,
    UnitType,
    UtilityPayment,
    UtilityType,
)
from app.schemas import (
    ApartmentCreate,
    ApartmentEquipmentCreate,
    ApartmentEquipmentOut,
    ApartmentEquipmentUpdate,
    ApartmentAutomationOut,
    ApartmentAutomationUpsert,
    ApartmentServiceConnectionCreate,
    ApartmentServiceConnectionOut,
    ApartmentServiceConnectionUpdate,
    AutomationCycleRunOut,
    AutomationCyclePreviewItem,
    AutomationCyclePhaseRunOut,
    AutomationCycleRunDetailOut,
    AutomationCycleRunLogDetailOut,
    AutomationCyclePreviewOut,
    AutomationRunLogOut,
    ApartmentDetailOut,
    AutomationRowOut,
    AutomationTemplateCreate,
    AutomationTemplateOut,
    AutomationTemplateUpdate,
    ApartmentOverviewOut,
    ApartmentOut,
    ApartmentTariffRowOut,
    BalanceExplainOut,
    BillingChangeLogOut,
    BillingGenerateRequest,
    BillingLockRequest,
    BillingRecalculateRequest,
    CalculationRowOut,
    ConnectionChargeLineCreate,
    ConnectionChargeLineOut,
    ConnectionChargeLineUpdate,
    MaintenanceRecordCreate,
    MaintenanceRecordOut,
    MaintenanceRecordUpdate,
    MeterPeriodRowOut,
    MeterReplaceRequest,
    MeterSubmitDispatchOut,
    MeterSubmitDispatchRequest,
    MeterSubmitEvaluateOut,
    MeterInitialReadingUpdate,
    MeterTypeCreate,
    MeterTypeOut,
    MeterTypeUpdate,
    MissingServiceOut,
    InvoiceOut,
    MeterCreate,
    MeterUpdate,
    MeterOut,
    OwnerChargeCreate,
    OwnerChargeOut,
    OwnerChargeUpdate,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    ReadingCreate,
    ReadingOut,
    RentMonthOut,
    RentRecordUpsert,
    ServiceCatalogCreate,
    ServiceCatalogOut,
    ServiceCatalogUpdate,
    TariffCreate,
    TariffOut,
    TariffSettingUpsert,
    TariffApplyFromPeriod,
    TariffBindingUpdate,
    TariffUpdate,
    ServiceActivationUpdate,
    ElectricityPlanUpsert,
    ElectricityPlanHistoryOut,
    MeterExpectedRegisterItem,
    MeterExpectedRegistersOut,
    ServiceLedgerRowOut,
    ServiceLedgerUpsert,
    TenancyOut,
    TenantCreate,
    TenantOut,
    TenantUpdate,
    TenancyCreate,
    UtilityPaymentCreate,
    UtilityPaymentOut,
    UtilityPaymentUpdate,
)
from app.services.billing import _resolve_previous_reading_by_register, build_connection_charge_rows, generate_invoice
from app.services.tariff_rules import fixed_charge_multiplier

router = APIRouter(dependencies=[Depends(require_authenticated_admin)])

STORAGE_ROOT = Path("storage")
TENANT_PHOTO_DIR = STORAGE_ROOT / "tenant_photos"
CONTRACT_SCAN_DIR = STORAGE_ROOT / "contracts"
TENANT_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
CONTRACT_SCAN_DIR.mkdir(parents=True, exist_ok=True)


def _month_key(year: int, month: int) -> int:
    return year * 100 + month


def _default_meter_service_name(utility_type: UtilityType) -> str:
    return {
        UtilityType.electricity: "Електролічильник",
        UtilityType.water: "Лічильник води",
        UtilityType.gas: "Газовий лічильник",
        UtilityType.heating: "Лічильник опалення",
        UtilityType.sewage: "Лічильник водовідведення",
        UtilityType.internet: "Інтернет-лічильник",
        UtilityType.other: "Лічильник",
    }.get(utility_type, "Лічильник")


def _slugify_meter_type_code(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9а-яіїєґ]+", "_", value.lower(), flags=re.IGNORECASE)
    normalized = re.sub(r"^_+|_+$", "", normalized)
    return normalized[:64] or "meter_type"


def _meter_display_name(meter: Meter | None) -> str:
    if meter is None:
        return "Лічильник"
    if meter.meter_type and (meter.meter_type.name or "").strip():
        return meter.meter_type.name.strip()
    return _default_meter_service_name(meter.utility_type)


def _get_meter_type_or_404(db: Session, meter_type_id: int) -> MeterType:
    meter_type = db.get(MeterType, meter_type_id)
    if meter_type is None:
        raise HTTPException(status_code=404, detail="Meter type not found.")
    return meter_type


def _meter_out(meter: Meter) -> MeterOut:
    return MeterOut(
        id=meter.id,
        apartment_id=meter.apartment_id,
        meter_type_id=meter.meter_type_id,
        meter_type_name=meter.meter_type_name,
        display_name=_meter_display_name(meter),
        utility_type=meter.utility_type,
        serial_number=meter.serial_number,
        initial_reading=Decimal(meter.initial_reading),
        installed_at=meter.installed_at,
        retired_at=meter.retired_at,
        replaced_by_meter_id=meter.replaced_by_meter_id,
        is_active=meter.is_active,
    )


def _recalc_service_ledger_from_period(
    db: Session,
    apartment_id: int,
    service_name: str,
    start_year: int,
    start_month: int,
) -> None:
    start_key = _month_key(start_year, start_month)
    rows = db.scalars(
        select(ServiceLedgerEntry)
        .where(ServiceLedgerEntry.apartment_id == apartment_id)
        .where(ServiceLedgerEntry.service_name == service_name)
        .order_by(ServiceLedgerEntry.year, ServiceLedgerEntry.month, ServiceLedgerEntry.id)
    ).all()
    carry = Decimal("0.00")
    for row in rows:
        row_key = _month_key(row.year, row.month)
        if row_key < start_key:
            carry = Decimal(row.closing_balance)
            continue
        row.opening_balance = carry.quantize(Decimal("0.01"))
        row.closing_balance = (
            Decimal(row.opening_balance)
            + Decimal(row.accrued)
            + Decimal(row.adjustment)
            - Decimal(row.benefit)
            - Decimal(row.subsidy)
            - Decimal(row.paid)
        ).quantize(Decimal("0.01"))
        row.updated_at = datetime.now(UTC)
        carry = Decimal(row.closing_balance)


def _generate_apartment_code(db: Session, address: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", address).strip("-").upper()
    if not base:
        base = "APT"
    base = base[:48]
    for _ in range(20):
        candidate = f"{base}-{uuid4().hex[:6].upper()}"[:64]
        exists = db.scalar(select(Apartment).where(Apartment.code == candidate))
        if exists is None:
            return candidate
    return f"APT-{uuid4().hex[:12].upper()}"[:64]


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _service_connection_out(row: ApartmentServiceConnection, db: Session) -> ApartmentServiceConnectionOut:
    charge_lines = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == row.id)
        .order_by(ConnectionChargeLine.effective_from, ConnectionChargeLine.id)
    ).all()
    return ApartmentServiceConnectionOut(
        id=row.id,
        apartment_id=row.apartment_id,
        service_catalog_id=row.service_catalog_id,
        provider_id=row.provider_id,
        personal_account=row.personal_account,
        started_at=row.started_at,
        ended_at=row.ended_at,
        status=row.status,
        note=row.note,
        automation_id=row.automation_id,
        created_at=row.created_at,
        charge_lines=[
            ConnectionChargeLineOut(
                id=line.id,
                connection_id=line.connection_id,
                line_kind=line.line_kind,
                label=line.label,
                meter_id=line.meter_id,
                meter_register=line.meter_register,
                derived_from_line_id=line.derived_from_line_id,
                initial_reading=line.initial_reading,
                unit_name=line.unit_name,
                price_per_unit=line.price_per_unit,
                quantity_source=line.quantity_source,
                quantity_multiplier=line.quantity_multiplier,
                effective_from=line.effective_from,
                effective_to=line.effective_to,
                is_active=line.is_active,
                created_at=line.created_at,
            )
            for line in charge_lines
        ],
    )


def _compose_short_apartment_address(payload: ApartmentCreate) -> str:
    street = _clean_optional_text(payload.street)
    house_number = _clean_optional_text(payload.house_number)
    apartment_number = _clean_optional_text(payload.apartment_number)
    parts = [part for part in [street, house_number] if part]
    short_address = " ".join(parts).strip()
    if apartment_number:
        short_address = f"{short_address} кв {apartment_number}".strip()
    return short_address


def _compose_full_apartment_address(payload: ApartmentCreate) -> str:
    manual_address = _clean_optional_text(payload.address)
    short_address = _compose_short_apartment_address(payload)
    locality = _clean_optional_text(payload.locality)
    region = _clean_optional_text(payload.region)
    country = _clean_optional_text(payload.country) or "Україна"
    postal_code = _clean_optional_text(payload.postal_code)

    has_structured_address = any([short_address, locality, region, postal_code])
    if not has_structured_address:
        return manual_address or ""
    structured_parts = [part for part in [short_address, locality, region, country, postal_code] if part]
    return ", ".join(structured_parts)


def _apply_apartment_profile(apartment: Apartment, payload: ApartmentCreate) -> str:
    full_address = _compose_full_apartment_address(payload)
    if not full_address:
        raise HTTPException(status_code=422, detail="Заповніть адресу нерухомості.")
    apartment.address = full_address
    apartment.country = _clean_optional_text(payload.country) or "Україна"
    apartment.region = _clean_optional_text(payload.region)
    apartment.locality = _clean_optional_text(payload.locality)
    apartment.street = _clean_optional_text(payload.street)
    apartment.house_number = _clean_optional_text(payload.house_number)
    apartment.apartment_number = _clean_optional_text(payload.apartment_number)
    apartment.postal_code = _clean_optional_text(payload.postal_code)
    apartment.registered_residents = payload.registered_residents
    apartment.area_m2 = payload.area_m2
    apartment.living_area_m2 = payload.living_area_m2
    apartment.entrance = _clean_optional_text(payload.entrance)
    apartment.floor = _clean_optional_text(payload.floor)
    apartment.room_count = payload.room_count
    apartment.latitude = payload.latitude
    apartment.longitude = payload.longitude
    apartment.timezone = payload.timezone or "Europe/Kyiv"
    apartment.location_note = _clean_optional_text(payload.location_note)
    apartment.object_notes = _clean_optional_text(payload.object_notes)
    return full_address


def _prev_month(y: int, m: int) -> tuple[int, int]:
    if m == 1:
        return y - 1, 12
    return y, m - 1


def _next_month(y: int, m: int) -> tuple[int, int]:
    if m == 12:
        return y + 1, 1
    return y, m + 1


def _period_key(year: int, month: int) -> int:
    return year * 100 + month


def _period_from_date(value: date) -> tuple[int, int]:
    return value.year, value.month


def _payments_sum_by_received_month(db: Session, apartment_id: int, year: int, month: int) -> Decimal:
    period_start = date(year, month, 1)
    period_end = date(year, month, monthrange(year, month)[1])
    rows = db.scalars(
        select(UtilityPayment)
        .where(UtilityPayment.apartment_id == apartment_id)
        .where(UtilityPayment.paid_at >= period_start)
        .where(UtilityPayment.paid_at <= period_end)
    ).all()
    return sum((Decimal(row.amount) for row in rows), Decimal("0.00")).quantize(Decimal("0.01"))


def _payments_received_between(
    db: Session,
    apartment_id: int,
    start_date: date,
    end_date: date,
) -> tuple[Decimal, UtilityPayment | None]:
    rows = db.scalars(
        select(UtilityPayment)
        .where(UtilityPayment.apartment_id == apartment_id)
        .where(UtilityPayment.paid_at >= start_date)
        .where(UtilityPayment.paid_at <= end_date)
        .order_by(UtilityPayment.paid_at.asc(), UtilityPayment.id.asc())
    ).all()
    total = sum((Decimal(row.amount) for row in rows), Decimal("0.00")).quantize(Decimal("0.01"))
    latest = rows[-1] if rows else None
    return total, latest


def _preview_reason(code: str, message: str) -> tuple[str, str]:
    return code, message


def _legacy_api_disabled(endpoint_name: str) -> None:
    raise HTTPException(
        status_code=410,
        detail=f"{endpoint_name} вимкнено. Використовуйте нову модель 'Послуги об'єкта' та charge lines.",
    )


def _infer_cycle_log_phase(log: AutomationRunLog) -> str:
    if log.automation_id is None:
        return "legacy"
    if (log.mode or "").strip().lower() == "readings":
        return "submit"
    return "accrual"


def _default_period() -> tuple[int, int]:
    today = date.today()
    return _prev_month(today.year, today.month)


def _reimbursement_map_uah(db: Session, apartment_id: int) -> dict[tuple[int, int], Decimal]:
    rows = db.scalars(
        select(OwnerCharge)
        .where(OwnerCharge.apartment_id == apartment_id)
        .where(OwnerCharge.kind == OwnerChargeKind.reimbursement)
        .where(OwnerCharge.currency == RentCurrency.uah)
    ).all()
    out: dict[tuple[int, int], Decimal] = {}
    for row in rows:
        key = (row.year, row.month)
        out[key] = out.get(key, Decimal("0.00")) + Decimal(row.amount)
    return out


def _effective_utility_period(
    db: Session, apartment_id: int, year: int, month: int
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    reimbursements = _reimbursement_map_uah(db, apartment_id)
    invoices = db.scalars(select(Invoice).where(Invoice.apartment_id == apartment_id)).all()
    invoice_map = {(inv.year, inv.month): inv for inv in invoices}
    payments = db.scalars(select(UtilityPayment).where(UtilityPayment.apartment_id == apartment_id)).all()
    payment_map: dict[tuple[int, int], Decimal] = {}
    for p in payments:
        key = _period_from_date(p.paid_at)
        payment_map[key] = (payment_map.get(key, Decimal("0.00")) + Decimal(p.amount)).quantize(Decimal("0.01"))

    target = (year, month)
    known_keys = set(invoice_map.keys()) | set(payment_map.keys()) | set(reimbursements.keys()) | {target}
    start_year, start_month = min(known_keys, key=lambda x: _month_key(x[0], x[1]))
    carry = Decimal("0.00")

    y, m = start_year, start_month
    while _month_key(y, m) <= _month_key(year, month):
        inv = invoice_map.get((y, m))
        if inv is not None:
            reimbursement = reimbursements.get((y, m), Decimal("0.00"))
            month_charges = (Decimal(inv.total_amount) - reimbursement).quantize(Decimal("0.01"))
        else:
            rows = _build_period_rows(db, apartment_id, y, m, None)
            month_charges = sum((Decimal(r.amount) for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))
        month_payments = payment_map.get((y, m), Decimal("0.00")).quantize(Decimal("0.01"))
        current = (carry + month_charges - month_payments).quantize(Decimal("0.01"))
        if y == year and m == month:
            return carry, month_charges, month_payments, current
        carry = current
        y, m = _next_month(y, m)

    return Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")


def _latest_confirmed_utility_period(db: Session, apartment_id: int) -> tuple[int, int] | None:
    locks = db.scalars(select(BillingLock).where(BillingLock.apartment_id == apartment_id)).all()
    if not locks:
        return None
    return max(((row.year, row.month) for row in locks), key=lambda x: _month_key(x[0], x[1]))


def _actual_current_utility_balance(db: Session, apartment_id: int) -> Decimal:
    latest_confirmed = _latest_confirmed_utility_period(db, apartment_id)
    if not latest_confirmed:
        return Decimal("0.00")
    _, _, _, confirmed_balance = _effective_utility_period(
        db,
        apartment_id,
        latest_confirmed[0],
        latest_confirmed[1],
    )
    month_end = date(latest_confirmed[0], latest_confirmed[1], monthrange(latest_confirmed[0], latest_confirmed[1])[1])
    later_payments = db.scalars(
        select(UtilityPayment)
        .where(UtilityPayment.apartment_id == apartment_id)
        .where(UtilityPayment.paid_at > month_end)
    ).all()
    paid_after_confirmation = sum((Decimal(row.amount) for row in later_payments), Decimal("0.00")).quantize(
        Decimal("0.01")
    )
    return (Decimal(confirmed_balance) - paid_after_confirmation).quantize(Decimal("0.01"))


def _confirmed_previous_utility_debt(db: Session, apartment_id: int, year: int, month: int) -> Decimal:
    target_key = _month_key(year, month)
    confirmed_periods = [
        (row.year, row.month)
        for row in db.scalars(select(BillingLock).where(BillingLock.apartment_id == apartment_id)).all()
        if _month_key(row.year, row.month) < target_key
    ]
    if not confirmed_periods:
        return Decimal("0.00")
    last_confirmed = max(confirmed_periods, key=lambda x: _month_key(x[0], x[1]))
    _, _, _, confirmed_balance = _effective_utility_period(db, apartment_id, last_confirmed[0], last_confirmed[1])
    confirmed_month_end = date(
        last_confirmed[0],
        last_confirmed[1],
        monthrange(last_confirmed[0], last_confirmed[1])[1],
    )
    period_start = date(year, month, 1)
    later_payments = db.scalars(
        select(UtilityPayment)
        .where(UtilityPayment.apartment_id == apartment_id)
        .where(UtilityPayment.paid_at > confirmed_month_end)
        .where(UtilityPayment.paid_at < period_start)
    ).all()
    paid_before_period = sum((Decimal(row.amount) for row in later_payments), Decimal("0.00")).quantize(Decimal("0.01"))
    return (Decimal(confirmed_balance) - paid_before_period).quantize(Decimal("0.01"))


def _active_tenancy(db: Session, apartment_id: int, on_date: date) -> Tenancy | None:
    tenancies = db.scalars(select(Tenancy).where(Tenancy.apartment_id == apartment_id)).all()
    for tenancy in tenancies:
        if tenancy.start_date <= on_date and (tenancy.end_date is None or tenancy.end_date >= on_date):
            return tenancy
    return None


def _sync_invoice_payment_totals(db: Session, apartment_id: int, year: int, month: int) -> None:
    invoice = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == apartment_id, Invoice.year == year, Invoice.month == month)
        )
    )
    if invoice is None:
        return
    paid_total = _payments_sum_by_received_month(db, apartment_id, year, month)
    invoice.utility_payment_received = paid_total
    invoice.closing_balance = (
        Decimal(invoice.carry_over_debt) + Decimal(invoice.total_amount) - Decimal(invoice.utility_payment_received)
    ).quantize(Decimal("0.01"))
    invoice.status = InvoiceStatus.paid if invoice.closing_balance <= 0 else InvoiceStatus.unpaid


ELECTRICITY_REGISTER_LABELS = {
    "total": "Загальний",
    "day": "Денний",
    "night": "Нічний",
    "peak": "Піковий",
    "semi_peak": "Напівпіковий",
    "off_peak": "Нічний",
}

ELECTRICITY_REGISTER_ORDER = {
    "total": 0,
    "day": 1,
    "night": 2,
    "peak": 3,
    "semi_peak": 4,
    "off_peak": 5,
}


def _active_meter_charge_lines(
    db: Session,
    meter_id: int,
    year: int,
    month: int,
) -> list[ConnectionChargeLine]:
    period_start = date(year, month, 1)
    return db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.meter_id == meter_id)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.is_active.is_(True))
        .where(ConnectionChargeLine.effective_from <= period_start)
        .where(
            and_(
                ApartmentServiceConnection.id == ConnectionChargeLine.connection_id,
                ApartmentServiceConnection.status == "active",
                ApartmentServiceConnection.started_at <= period_start,
            )
        )
        .where(
            or_(
                ApartmentServiceConnection.ended_at.is_(None),
                ApartmentServiceConnection.ended_at >= period_start,
            )
        )
        .where(
            or_(
                ConnectionChargeLine.effective_to.is_(None),
                ConnectionChargeLine.effective_to >= period_start,
            )
        )
        .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
    ).all()


def _electricity_plan_mode_from_registers(registers: list[str]) -> str | None:
    normalized = [register for register in registers if register]
    if normalized == ["total"]:
        return "single"
    if set(normalized) == {"day", "night"}:
        return "day_night"
    if set(normalized) == {"peak", "semi_peak", "off_peak"}:
        return "tri_zone"
    return None


def _resolve_electricity_plan_initial(
    db: Session,
    meter: Meter | None,
    register_name: str,
    year: int,
    month: int,
    fallback: Decimal,
) -> Decimal:
    if meter is None or meter.utility_type != UtilityType.electricity:
        return fallback
    active_line = next(
        (
            line
            for line in _active_meter_charge_lines(db, meter.id, year, month)
            if (line.meter_register or "total") == register_name
        ),
        None,
    )
    if active_line is not None and active_line.initial_reading is not None:
        return Decimal(active_line.initial_reading)
    return fallback


def _prev_reading(
    db: Session,
    meter_id: int,
    register_name: str,
    year: int,
    month: int,
    initial: Decimal,
) -> Decimal:
    meter = db.get(Meter, meter_id)
    initial = _resolve_electricity_plan_initial(db, meter, register_name, year, month, initial)
    rows = db.scalars(
        select(MeterReading)
        .where(MeterReading.meter_id == meter_id)
        .where(MeterReading.register_name == register_name)
    ).all()
    prev = [r for r in rows if _month_key(r.year, r.month) < _month_key(year, month)]
    if not prev:
        return initial
    last = sorted(prev, key=lambda r: _month_key(r.year, r.month), reverse=True)[0]
    return Decimal(last.value)


def _build_period_rows(
    db: Session,
    apartment_id: int,
    year: int,
    month: int,
    invoice: Invoice | None,
) -> list[CalculationRowOut]:
    connection_rows = build_connection_charge_rows(db, apartment_id, year, month)
    rows = [
        CalculationRowOut(
            line_id=row.get("line_id"),
            meter_id=row["meter_id"],
            source_line_id=row.get("source_line_id"),
            service_name=row["service_name"],
            service_group_key=row.get("service_group_key"),
            service_group_label=row.get("service_group_label"),
            service_line_label=row.get("service_line_label"),
            meter_register=row["meter_register"],
            meter_register_label=row.get("meter_register_label"),
            meter_plan_mode=row.get("meter_plan_mode"),
            meter_expected_registers=row.get("meter_expected_registers", []),
            previous_reading=row.get("previous_reading"),
            current_reading=row.get("current_reading"),
            difference=row.get("difference"),
            unit_name=row["unit_name"],
            unit_price=row["unit_price"],
            amount=row["amount"],
            can_edit_previous=bool(row.get("can_edit_previous")),
        )
        for row in connection_rows
    ]

    reimbursements = db.scalars(
        select(OwnerCharge)
        .where(OwnerCharge.apartment_id == apartment_id)
        .where(OwnerCharge.year == year)
        .where(OwnerCharge.month == month)
        .where(OwnerCharge.kind == OwnerChargeKind.reimbursement)
        .order_by(OwnerCharge.event_date, OwnerCharge.id)
    ).all()
    for reimbursement in reimbursements:
        amount = (Decimal(reimbursement.amount) * Decimal("-1")).quantize(Decimal("0.01"))
        rows.append(
            CalculationRowOut(
                meter_id=None,
                source_line_id=None,
                service_name=f"Відшкодування: {reimbursement.category}",
                service_group_key=None,
                service_group_label=None,
                service_line_label=None,
                meter_register="total",
                meter_register_label=None,
                meter_plan_mode=None,
                meter_expected_registers=[],
                previous_reading=None,
                current_reading=None,
                difference=None,
                unit_name=UnitType.month,
                unit_price=amount,
                amount=amount,
            )
        )
    return rows


def _recalc_invoice(db: Session, invoice: Invoice, carry_over: Decimal) -> None:
    for old in list(invoice.items):
        db.delete(old)
    db.flush()

    apartment_id = invoice.apartment_id
    year = invoice.year
    month = invoice.month
    connection_rows = build_connection_charge_rows(db, apartment_id, year, month)
    total = Decimal("0.00")
    for row in connection_rows:
        amount = Decimal(row["amount"]).quantize(Decimal("0.01"))
        consumption = Decimal(row["difference"]) if row["difference"] is not None else Decimal("0.000")
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                service_name=str(row["service_name"]),
                utility_type=row["utility_type"],
                unit_name=UnitType(row["unit_name"]),
                consumption=consumption,
                unit_price=Decimal(row["unit_price"]),
                amount=amount,
            )
        )
        total += amount

    invoice.total_amount = total
    invoice.carry_over_debt = carry_over.quantize(Decimal("0.01"))
    invoice.closing_balance = (invoice.carry_over_debt + invoice.total_amount - Decimal(invoice.utility_payment_received)).quantize(
        Decimal("0.01")
    )
    invoice.status = InvoiceStatus.paid if invoice.closing_balance <= 0 else InvoiceStatus.unpaid


def _recalc_from_period(db: Session, apartment_id: int, start_year: int, start_month: int) -> None:
    invoices = db.scalars(select(Invoice).where(Invoice.apartment_id == apartment_id)).all()
    invoices = sorted(invoices, key=lambda x: _month_key(x.year, x.month))
    carry = Decimal("0.00")
    for inv in invoices:
        _sync_invoice_payment_totals(db, apartment_id, inv.year, inv.month)
        _recalc_invoice(db, inv, carry)
        carry = Decimal(inv.closing_balance)
    db.commit()


def _is_month_locked(db: Session, apartment_id: int, year: int, month: int) -> bool:
    row = db.scalar(
        select(BillingLock).where(
            and_(
                BillingLock.apartment_id == apartment_id,
                BillingLock.year == year,
                BillingLock.month == month,
            )
        )
    )
    return row is not None


def _log_billing_change(
    db: Session,
    *,
    apartment_id: int,
    year: int,
    month: int,
    actor_username: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    service_name: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        BillingChangeLog(
            apartment_id=apartment_id,
            year=year,
            month=month,
            actor_username=actor_username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            service_name=service_name,
            details_json=json.dumps(details or {}, ensure_ascii=False),
        )
    )


def _tenant_out(tenant: Tenant | None) -> TenantOut | None:
    if tenant is None:
        return None
    today = date.today()
    is_active_now = any(
        tenancy.start_date <= today and (tenancy.end_date is None or tenancy.end_date >= today)
        for tenancy in tenant.tenancies
    )
    return TenantOut(
        id=tenant.id,
        full_name=tenant.full_name,
        phone=tenant.phone,
        email=tenant.email,
        access_code=tenant.access_code,
        bank_statement_name=tenant.bank_statement_name,
        rent_amount=tenant.rent_amount,
        rent_currency=tenant.rent_currency,
        photo_url=f"/admin/storage/{tenant.photo_path}" if tenant.photo_path else None,
        passport_number=tenant.passport_number,
        passport_issued_by=tenant.passport_issued_by,
        passport_issue_date=tenant.passport_issue_date,
        passport_expiry_date=tenant.passport_expiry_date,
        portal_enabled=tenant.portal_enabled,
        can_submit_meter_readings=tenant.can_submit_meter_readings,
        phones=[p.phone for p in tenant.phones],
        contacts=tenant.contacts,
        is_active_now=is_active_now,
    )


def _validate_tenant_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must include at least one digit.")


@router.get("/storage/{file_path:path}")
def get_protected_storage_file(file_path: str):
    root = Path(settings.storage_dir).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid file path.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(target)


@router.get("/apartments", response_model=list[ApartmentOut])
def list_apartments(db: Session = Depends(get_db)):
    return db.scalars(select(Apartment).order_by(Apartment.address)).all()


@router.post("/apartments", response_model=ApartmentOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_apartment(payload: ApartmentCreate, db: Session = Depends(get_db)):
    code = payload.code.strip() if payload.code else ""
    full_address = _compose_full_apartment_address(payload)
    apartment = Apartment(code=code or _generate_apartment_code(db, full_address or "APT"), address=full_address)
    _apply_apartment_profile(apartment, payload)
    db.add(apartment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Apartment code already exists.")
    db.refresh(apartment)
    return apartment


@router.put("/apartments/{apartment_id}", response_model=ApartmentOut, dependencies=[Depends(require_write_access)])
def update_apartment(apartment_id: int, payload: ApartmentCreate, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    code = payload.code.strip() if payload.code else ""
    if code:
        apartment.code = code
    _apply_apartment_profile(apartment, payload)
    db.commit()
    db.refresh(apartment)
    return apartment


@router.delete("/apartments/{apartment_id}", dependencies=[Depends(require_write_access)])
def delete_apartment(apartment_id: int, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")

    tenant_ids: set[int] = set(
        db.scalars(select(Tenancy.tenant_id).where(Tenancy.apartment_id == apartment_id)).all()
    )
    tenant_ids.update(db.scalars(select(Invoice.tenant_id).where(Invoice.apartment_id == apartment_id)).all())
    tenant_ids.update(
        tenant_id
        for tenant_id in db.scalars(select(UtilityPayment.tenant_id).where(UtilityPayment.apartment_id == apartment_id)).all()
        if tenant_id is not None
    )
    tenant_ids.update(db.scalars(select(RentLedger.tenant_id).where(RentLedger.apartment_id == apartment_id)).all())

    # Explicit cleanup for linked rows to guarantee stable apartment removal in SQLite and Postgres.
    tenancies = db.scalars(select(Tenancy).where(Tenancy.apartment_id == apartment_id)).all()
    for tenancy in tenancies:
        for contract in list(tenancy.contracts):
            db.delete(contract)
        db.delete(tenancy)

    meter_ids = db.scalars(select(Meter.id).where(Meter.apartment_id == apartment_id)).all()
    if meter_ids:
        for meter in db.scalars(select(Meter).where(Meter.id.in_(meter_ids))).all():
            for reading in list(meter.readings):
                db.delete(reading)
            db.delete(meter)

    for invoice in db.scalars(select(Invoice).where(Invoice.apartment_id == apartment_id)).all():
        for item in list(invoice.items):
            db.delete(item)
        db.delete(invoice)

    for row in db.scalars(select(UtilityPayment).where(UtilityPayment.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(RentLedger).where(RentLedger.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(OwnerCharge).where(OwnerCharge.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(ApartmentEquipment).where(ApartmentEquipment.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(ServiceLedgerEntry).where(ServiceLedgerEntry.apartment_id == apartment_id)).all():
        db.delete(row)
    for batch in db.scalars(select(ProviderImportBatch).where(ProviderImportBatch.apartment_id == apartment_id)).all():
        for import_row in db.scalars(select(ProviderImportRow).where(ProviderImportRow.batch_id == batch.id)).all():
            db.delete(import_row)
        db.delete(batch)
    for row in db.scalars(select(BillingLock).where(BillingLock.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(BillingChangeLog).where(BillingChangeLog.apartment_id == apartment_id)).all():
        db.delete(row)

    db.delete(apartment)
    db.flush()

    # Remove orphan tenant test records that are no longer linked to any apartment data.
    for tenant_id in tenant_ids:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            continue
        has_links = (
            db.scalar(select(Tenancy.id).where(Tenancy.tenant_id == tenant_id).limit(1)) is not None
            or db.scalar(select(Invoice.id).where(Invoice.tenant_id == tenant_id).limit(1)) is not None
            or db.scalar(select(UtilityPayment.id).where(UtilityPayment.tenant_id == tenant_id).limit(1)) is not None
            or db.scalar(select(RentLedger.id).where(RentLedger.tenant_id == tenant_id).limit(1)) is not None
        )
        if not has_links:
            db.delete(tenant)

    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/equipment", response_model=list[ApartmentEquipmentOut])
def list_apartment_equipment(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    return db.scalars(
        select(ApartmentEquipment)
        .where(ApartmentEquipment.apartment_id == apartment_id)
        .order_by(ApartmentEquipment.name, ApartmentEquipment.id)
    ).all()


@router.post(
    "/apartments/{apartment_id}/equipment",
    response_model=ApartmentEquipmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def create_apartment_equipment(
    apartment_id: int,
    payload: ApartmentEquipmentCreate,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    row = ApartmentEquipment(apartment_id=apartment_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put(
    "/apartments/{apartment_id}/equipment/{equipment_id}",
    response_model=ApartmentEquipmentOut,
    dependencies=[Depends(require_write_access)],
)
def update_apartment_equipment(
    apartment_id: int,
    equipment_id: int,
    payload: ApartmentEquipmentUpdate,
    db: Session = Depends(get_db),
):
    row = db.get(ApartmentEquipment, equipment_id)
    if row is None or row.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Equipment not found.")
    data = payload.model_dump()
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete(
    "/apartments/{apartment_id}/equipment/{equipment_id}",
    dependencies=[Depends(require_write_access)],
)
def delete_apartment_equipment(
    apartment_id: int,
    equipment_id: int,
    db: Session = Depends(get_db),
):
    row = db.get(ApartmentEquipment, equipment_id)
    if row is None or row.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Equipment not found.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    tenant = Tenant(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        password_hash=None,
        portal_enabled=False,
        can_submit_meter_readings=False,
        access_code=payload.access_code,
    )
    db.add(tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant access code or email already exists.")
    db.refresh(tenant)
    return _tenant_out(tenant)


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    tenants = db.scalars(select(Tenant).order_by(Tenant.full_name)).all()
    return [_tenant_out(tenant) for tenant in tenants]


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return _tenant_out(tenant)


@router.put("/tenants/{tenant_id}", response_model=TenantOut, dependencies=[Depends(require_write_access)])
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    tenant.full_name = payload.full_name
    tenant.phone = payload.primary_phone
    tenant.email = payload.email
    tenant.bank_statement_name = payload.bank_statement_name
    tenant.rent_amount = payload.rent_amount
    tenant.rent_currency = payload.rent_currency
    tenant.passport_number = payload.passport_number
    tenant.passport_issued_by = payload.passport_issued_by
    tenant.passport_issue_date = payload.passport_issue_date
    tenant.passport_expiry_date = payload.passport_expiry_date
    if payload.portal_enabled is not None:
        tenant.portal_enabled = payload.portal_enabled
    if payload.can_submit_meter_readings is not None:
        tenant.can_submit_meter_readings = payload.can_submit_meter_readings
    if payload.portal_password:
        _validate_tenant_password_strength(payload.portal_password)
        tenant.password_hash = hash_password(payload.portal_password)

    for row in list(tenant.phones):
        db.delete(row)
    for row in list(tenant.contacts):
        db.delete(row)
    for phone in payload.phones:
        if phone.strip():
            db.add(TenantPhone(tenant_id=tenant.id, phone=phone.strip()))
    for c in payload.contacts:
        db.add(TenantContact(tenant_id=tenant.id, name=c.name, relation=c.relation, phone=c.phone, note=c.note))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant email already exists.")
    db.refresh(tenant)
    return _tenant_out(tenant)


@router.delete("/tenants/{tenant_id}", dependencies=[Depends(require_write_access)])
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    has_links = (
        db.scalar(select(Tenancy.id).where(Tenancy.tenant_id == tenant_id).limit(1)) is not None
        or db.scalar(select(Invoice.id).where(Invoice.tenant_id == tenant_id).limit(1)) is not None
        or db.scalar(select(UtilityPayment.id).where(UtilityPayment.tenant_id == tenant_id).limit(1)) is not None
        or db.scalar(select(RentLedger.id).where(RentLedger.tenant_id == tenant_id).limit(1)) is not None
    )
    if has_links:
        raise HTTPException(
            status_code=409,
            detail="Tenant has linked records. Finish tenancy and keep history instead of deleting.",
        )
    db.delete(tenant)
    db.commit()
    return {"status": "deleted"}


@router.post("/tenants/{tenant_id}/photo", dependencies=[Depends(require_write_access)])
async def upload_tenant_photo(tenant_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    suffix = Path(file.filename or "photo.jpg").suffix or ".jpg"
    filename = f"{tenant_id}_{uuid4().hex}{suffix}"
    target = TENANT_PHOTO_DIR / filename
    data = await file.read()
    target.write_bytes(data)
    tenant.photo_path = str(Path("tenant_photos") / filename)
    db.commit()
    return {"photo_url": f"/storage/{tenant.photo_path}"}


@router.get("/apartments/{apartment_id}/tenancies", response_model=list[TenancyOut])
def list_tenancies(apartment_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(Tenancy).where(Tenancy.apartment_id == apartment_id).order_by(Tenancy.start_date.desc())).all()
    out = []
    for t in rows:
        tenant = db.get(Tenant, t.tenant_id)
        out.append(
            {
                "id": t.id,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "tenant": _tenant_out(tenant),
                "contracts": [
                    {
                        "id": c.id,
                        "contract_start_date": c.contract_start_date,
                        "contract_end_date": c.contract_end_date,
                        "term_months": c.term_months,
                        "extension_type": c.extension_type,
                        "rent_amount": c.rent_amount,
                        "rent_currency": c.rent_currency,
                        "scan_url": f"/storage/{c.scan_path}" if c.scan_path else None,
                        "note": c.note,
                    }
                    for c in t.contracts
                ],
            }
        )
    return out


@router.post("/tenancies", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def assign_tenant(payload: TenancyCreate, db: Session = Depends(get_db)):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    if db.get(Tenant, payload.tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    active = db.scalar(select(Tenancy).where(and_(Tenancy.apartment_id == payload.apartment_id, Tenancy.end_date.is_(None))))
    if active:
        active.end_date = payload.start_date - timedelta(days=1)
    db.add(Tenancy(apartment_id=payload.apartment_id, tenant_id=payload.tenant_id, start_date=payload.start_date))
    db.commit()
    return {"status": "assigned"}


@router.put("/tenancies/{tenancy_id}/end", dependencies=[Depends(require_write_access)])
def end_tenancy(tenancy_id: int, end_date: date = Form(...), db: Session = Depends(get_db)):
    tenancy = db.get(Tenancy, tenancy_id)
    if tenancy is None:
        raise HTTPException(status_code=404, detail="Tenancy not found.")
    tenancy.end_date = end_date
    db.commit()
    return {"status": "updated"}


@router.post("/tenancies/{tenancy_id}/contracts", dependencies=[Depends(require_write_access)])
async def add_contract(
    tenancy_id: int,
    contract_start_date: date = Form(...),
    contract_end_date: date | None = Form(None),
    term_months: int | None = Form(None),
    extension_type: ContractExtensionType = Form(ContractExtensionType.none),
    rent_amount: Decimal | None = Form(None),
    rent_currency: str = Form("UAH"),
    note: str | None = Form(None),
    scan: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    tenancy = db.get(Tenancy, tenancy_id)
    if tenancy is None:
        raise HTTPException(status_code=404, detail="Tenancy not found.")
    scan_path = None
    if scan is not None:
        suffix = Path(scan.filename or "contract.pdf").suffix or ".pdf"
        filename = f"{tenancy_id}_{uuid4().hex}{suffix}"
        target = CONTRACT_SCAN_DIR / filename
        target.write_bytes(await scan.read())
        scan_path = str(Path("contracts") / filename)

    contract = RentalContract(
        tenancy_id=tenancy_id,
        contract_start_date=contract_start_date,
        contract_end_date=contract_end_date,
        term_months=term_months,
        extension_type=extension_type,
        rent_amount=rent_amount,
        rent_currency=rent_currency,
        note=note,
        scan_path=scan_path,
    )
    db.add(contract)
    db.commit()
    return {"status": "saved"}


@router.post("/meters", response_model=MeterOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_meter(payload: MeterCreate, db: Session = Depends(get_db)):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    meter_type = _get_meter_type_or_404(db, payload.meter_type_id)
    meter = Meter(
        apartment_id=payload.apartment_id,
        meter_type_id=meter_type.id,
        utility_type=meter_type.utility_type,
        serial_number=payload.serial_number,
        initial_reading=payload.initial_reading if payload.initial_reading is not None else Decimal("0"),
        installed_at=payload.installed_at,
    )
    db.add(meter)
    db.commit()
    db.refresh(meter)
    return _meter_out(meter)


@router.put("/meters/{meter_id}", response_model=MeterOut, dependencies=[Depends(require_write_access)])
def update_meter(meter_id: int, payload: MeterUpdate, db: Session = Depends(get_db)):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    meter_type = _get_meter_type_or_404(db, payload.meter_type_id)
    meter.meter_type_id = meter_type.id
    meter.utility_type = meter_type.utility_type
    meter.serial_number = payload.serial_number
    if payload.initial_reading is not None:
        meter.initial_reading = payload.initial_reading
    meter.installed_at = payload.installed_at
    db.commit()
    db.refresh(meter)
    return _meter_out(meter)


@router.post("/meters/{meter_id}/replace", response_model=MeterOut, dependencies=[Depends(require_write_access)])
def replace_meter(
    meter_id: int,
    payload: MeterReplaceRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    old_meter = db.get(Meter, meter_id)
    if old_meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    if payload.installed_at <= old_meter.installed_at:
        raise HTTPException(status_code=400, detail="Replacement date must be later than current meter installation date.")

    new_meter = Meter(
        apartment_id=old_meter.apartment_id,
        meter_type_id=old_meter.meter_type_id,
        utility_type=old_meter.utility_type,
        serial_number=payload.serial_number,
        initial_reading=payload.initial_reading,
        installed_at=payload.installed_at,
        is_active=True,
    )
    db.add(new_meter)
    db.flush()

    old_meter.retired_at = payload.installed_at
    old_meter.replaced_by_meter_id = new_meter.id
    old_meter.is_active = False

    bound_lines = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.meter_id == old_meter.id)
        .order_by(ConnectionChargeLine.effective_from.asc(), ConnectionChargeLine.id.asc())
    ).all()

    latest_before_replace: dict[tuple[int, str, str, str], ConnectionChargeLine] = {}
    for line in bound_lines:
        if line.effective_from >= payload.installed_at:
            line.meter_id = new_meter.id
            continue
        signature = (
            line.connection_id,
            line.label,
            line.line_kind.value,
            line.meter_register or "total",
        )
        current = latest_before_replace.get(signature)
        if current is None or line.effective_from > current.effective_from:
            latest_before_replace[signature] = line

    for signature, source_line in latest_before_replace.items():
        target = db.scalar(
            select(ConnectionChargeLine).where(
                and_(
                    ConnectionChargeLine.connection_id == source_line.connection_id,
                    ConnectionChargeLine.label == source_line.label,
                    ConnectionChargeLine.line_kind == source_line.line_kind,
                    ConnectionChargeLine.meter_register == (source_line.meter_register or "total"),
                    ConnectionChargeLine.effective_from == payload.installed_at,
                )
            )
        )
        if target is None:
            if source_line.effective_to is None or source_line.effective_to >= payload.installed_at:
                source_line.effective_to = payload.installed_at - timedelta(days=1)
            target = ConnectionChargeLine(
                connection_id=source_line.connection_id,
                line_kind=source_line.line_kind,
                label=source_line.label,
                meter_id=new_meter.id,
                meter_register=source_line.meter_register or "total",
                derived_from_line_id=source_line.derived_from_line_id,
                unit_name=source_line.unit_name,
                price_per_unit=source_line.price_per_unit,
                quantity_source=source_line.quantity_source,
                quantity_multiplier=source_line.quantity_multiplier,
                effective_from=payload.installed_at,
                effective_to=None,
                is_active=source_line.is_active,
            )
            db.add(target)
        else:
            target.meter_id = new_meter.id
            target.meter_register = source_line.meter_register or "total"
            target.derived_from_line_id = source_line.derived_from_line_id
            target.quantity_source = source_line.quantity_source
            target.quantity_multiplier = source_line.quantity_multiplier

    db.commit()
    _recalc_from_period(db, old_meter.apartment_id, payload.installed_at.year, payload.installed_at.month)
    _log_billing_change(
        db,
        apartment_id=old_meter.apartment_id,
        year=payload.installed_at.year,
        month=payload.installed_at.month,
        actor_username=user.username,
        action="meter_replaced",
        entity_type="meter",
        entity_id=new_meter.id,
        service_name=_meter_display_name(old_meter),
        details={
            "old_meter_id": old_meter.id,
            "new_meter_id": new_meter.id,
            "new_serial_number": new_meter.serial_number,
            "installed_at": payload.installed_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(new_meter)
    return _meter_out(new_meter)


@router.delete("/meters/{meter_id}", dependencies=[Depends(require_write_access)])
def delete_meter(meter_id: int, db: Session = Depends(get_db)):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    bound_line = db.scalar(select(ConnectionChargeLine).where(ConnectionChargeLine.meter_id == meter_id).limit(1))
    if bound_line is not None:
        raise HTTPException(
            status_code=409,
            detail="Meter is used in service charge lines. Rebind or delete related charge lines first.",
        )
    db.delete(meter)
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/meters", response_model=list[MeterOut])
def list_meters(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    meters = db.scalars(select(Meter).where(Meter.apartment_id == apartment_id).order_by(Meter.id)).all()
    return [_meter_out(meter) for meter in meters]


@router.get("/apartments/{apartment_id}/meter-period", response_model=list[MeterPeriodRowOut])
def meter_period(apartment_id: int, year: int, month: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows: list[MeterPeriodRowOut] = []
    meters = db.scalars(select(Meter).where(Meter.apartment_id == apartment_id).order_by(Meter.id)).all()
    for meter in meters:
        register_name = "total"
        current = db.scalar(
            select(MeterReading).where(
                and_(
                    MeterReading.meter_id == meter.id,
                    MeterReading.register_name == register_name,
                    MeterReading.year == year,
                    MeterReading.month == month,
                )
            )
        )
        prev = _prev_reading(db, meter.id, register_name, year, month, Decimal(meter.initial_reading))
        current_value = Decimal(current.value) if current else None
        rows.append(
            MeterPeriodRowOut(
                meter_id=meter.id,
                service_name=_meter_display_name(meter),
                utility_type=meter.utility_type,
                serial_number=meter.serial_number,
                year=year,
                month=month,
                current_value=current_value,
                previous_value=prev,
                difference=(current_value - prev) if current_value is not None else None,
            )
        )
    return rows


@router.post("/tariffs", response_model=TariffOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_tariff(
    payload: TariffCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")


@router.put("/tariffs/{tariff_id}", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def update_tariff(
    tariff_id: int,
    payload: TariffUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")


@router.put("/tariffs/{tariff_id}/binding", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def update_tariff_binding(
    tariff_id: int,
    payload: TariffBindingUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")


@router.post("/tariffs/{tariff_id}/apply-from-period", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def apply_tariff_from_period(
    tariff_id: int,
    payload: TariffApplyFromPeriod,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")


@router.put("/apartments/{apartment_id}/services/{service_name}/activation", dependencies=[Depends(require_write_access)])
def update_service_activation(
    apartment_id: int,
    service_name: str,
    payload: ServiceActivationUpdate,
    db: Session = Depends(get_db),
):
    _legacy_api_disabled("Legacy service activation API")


@router.delete("/tariffs/{tariff_id}", dependencies=[Depends(require_write_access)])
def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(get_current_admin_user)
):
    _legacy_api_disabled("Legacy tariff API")


@router.put(
    "/apartments/{apartment_id}/electricity-plan",
    dependencies=[Depends(require_write_access)],
)
def upsert_electricity_plan(
    apartment_id: int,
    payload: ElectricityPlanUpsert,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    meter = db.get(Meter, payload.meter_id)
    if meter is None or meter.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Meter not found for this apartment.")
    if meter.utility_type != UtilityType.electricity:
        raise HTTPException(status_code=400, detail="Selected meter is not electricity type.")
    normalized_plan_mode = "day_night" if payload.plan_mode == "dual" else payload.plan_mode
    electricity_catalog = db.scalar(select(ServiceCatalog).where(ServiceCatalog.code == "electricity"))
    if electricity_catalog is None:
        raise HTTPException(status_code=409, detail="Service catalog item 'electricity' not found.")
    connection = db.scalar(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .where(ApartmentServiceConnection.service_catalog_id == electricity_catalog.id)
        .order_by(ApartmentServiceConnection.started_at.desc(), ApartmentServiceConnection.id.desc())
    )
    if connection is None:
        connection = ApartmentServiceConnection(
            apartment_id=apartment_id,
            service_catalog_id=electricity_catalog.id,
            provider_id=None,
            personal_account=None,
            started_at=payload.effective_from,
            ended_at=None,
            status="active",
            note=None,
            automation_id=None,
        )
        db.add(connection)
        db.flush()
    elif connection.started_at > payload.effective_from:
        connection.started_at = payload.effective_from
    connection.status = "active"

    if normalized_plan_mode == "single":
        if payload.single_price_per_unit is None:
            raise HTTPException(status_code=400, detail="single_price_per_unit is required for single plan.")
        desired_lines = [("total", payload.single_service_name, payload.single_price_per_unit, payload.single_initial_reading)]
    elif normalized_plan_mode == "day_night":
        if payload.day_price_per_unit is None or payload.night_price_per_unit is None:
            raise HTTPException(status_code=400, detail="day_price_per_unit and night_price_per_unit are required for dual plan.")
        desired_lines = [
            ("day", payload.day_service_name, payload.day_price_per_unit, payload.day_initial_reading),
            ("night", payload.night_service_name, payload.night_price_per_unit, payload.night_initial_reading),
        ]
    elif normalized_plan_mode == "tri_zone":
        if payload.peak_price_per_unit is None or payload.semi_peak_price_per_unit is None or payload.off_peak_price_per_unit is None:
            raise HTTPException(status_code=400, detail="peak/semi_peak/off_peak prices are required for tri-zone plan.")
        desired_lines = [
            ("peak", payload.peak_service_name, payload.peak_price_per_unit, payload.peak_initial_reading),
            ("semi_peak", payload.semi_peak_service_name, payload.semi_peak_price_per_unit, payload.semi_peak_initial_reading),
            ("off_peak", payload.off_peak_service_name, payload.off_peak_price_per_unit, payload.off_peak_initial_reading),
        ]
    else:
        raise HTTPException(status_code=400, detail="Unsupported plan_mode.")

    existing_on_date = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == connection.id)
        .where(ConnectionChargeLine.meter_id == meter.id)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.effective_from == payload.effective_from)
    ).all()
    existing_by_register = {(line.meter_register or "total"): line for line in existing_on_date}
    desired_registers = {register_name for register_name, _, _, _ in desired_lines}

    active_spanning_lines = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == connection.id)
        .where(ConnectionChargeLine.meter_id == meter.id)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.effective_from < payload.effective_from)
        .where(
            or_(
                ConnectionChargeLine.effective_to.is_(None),
                ConnectionChargeLine.effective_to >= payload.effective_from,
            )
        )
    ).all()
    for line in active_spanning_lines:
        current_register = (line.meter_register or "total").strip() or "total"
        if current_register in desired_registers or current_register in ELECTRICITY_REGISTER_ORDER:
            line.effective_to = payload.effective_from - timedelta(days=1)

    saved_line: ConnectionChargeLine | None = None
    changed_services: list[str] = []
    for register_name, label, price_per_unit, initial_reading in desired_lines:
        target = existing_by_register.get(register_name)
        if target is None:
            target = ConnectionChargeLine(
                connection_id=connection.id,
                line_kind=ChargeLineKind.meter_register,
                label=label.strip(),
                meter_id=meter.id,
                meter_register=register_name,
                derived_from_line_id=None,
                initial_reading=initial_reading,
                unit_name=UnitType.kWh,
                price_per_unit=price_per_unit,
                quantity_source=QuantitySource.fixed_1,
                quantity_multiplier=Decimal("1.000"),
                effective_from=payload.effective_from,
                effective_to=None,
                is_active=True,
            )
            db.add(target)
        else:
            target.label = label.strip()
            target.initial_reading = initial_reading
            target.unit_name = UnitType.kWh
            target.price_per_unit = price_per_unit
            target.quantity_source = QuantitySource.fixed_1
            target.quantity_multiplier = Decimal("1.000")
            target.effective_to = None
            target.is_active = True
        changed_services.append(label.strip())
        if saved_line is None:
            saved_line = target

    for register_name, stale_line in existing_by_register.items():
        if register_name not in desired_registers:
            db.delete(stale_line)

    db.commit()
    _recalc_from_period(db, apartment_id, payload.effective_from.year, payload.effective_from.month)
    _log_billing_change(
        db,
        apartment_id=apartment_id,
        year=payload.effective_from.year,
        month=payload.effective_from.month,
        actor_username=user.username,
        action="electricity_plan_updated",
        entity_type="charge_line",
        entity_id=saved_line.id if saved_line else None,
        service_name="Електроенергія",
        details={
            "plan_mode": normalized_plan_mode,
            "meter_id": meter.id,
            "effective_from": payload.effective_from.isoformat(),
            "changed_services": changed_services,
            "single_price_per_unit": str(payload.single_price_per_unit) if payload.single_price_per_unit is not None else None,
            "day_price_per_unit": str(payload.day_price_per_unit) if payload.day_price_per_unit is not None else None,
            "night_price_per_unit": str(payload.night_price_per_unit) if payload.night_price_per_unit is not None else None,
            "peak_price_per_unit": str(payload.peak_price_per_unit) if payload.peak_price_per_unit is not None else None,
            "semi_peak_price_per_unit": str(payload.semi_peak_price_per_unit) if payload.semi_peak_price_per_unit is not None else None,
            "off_peak_price_per_unit": str(payload.off_peak_price_per_unit) if payload.off_peak_price_per_unit is not None else None,
            "single_initial_reading": str(payload.single_initial_reading) if payload.single_initial_reading is not None else None,
            "day_initial_reading": str(payload.day_initial_reading) if payload.day_initial_reading is not None else None,
            "night_initial_reading": str(payload.night_initial_reading) if payload.night_initial_reading is not None else None,
            "peak_initial_reading": str(payload.peak_initial_reading) if payload.peak_initial_reading is not None else None,
            "semi_peak_initial_reading": str(payload.semi_peak_initial_reading) if payload.semi_peak_initial_reading is not None else None,
            "off_peak_initial_reading": str(payload.off_peak_initial_reading) if payload.off_peak_initial_reading is not None else None,
        },
    )
    db.commit()
    return {"status": "saved", "plan_mode": normalized_plan_mode}


@router.get("/apartments/{apartment_id}/electricity-plans", response_model=list[ElectricityPlanHistoryOut])
def list_electricity_plans(
    apartment_id: int,
    db: Session = Depends(get_db),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    electricity_catalog = db.scalar(select(ServiceCatalog).where(ServiceCatalog.code == "electricity"))
    if electricity_catalog is None:
        return []
    connections = db.scalars(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .where(ApartmentServiceConnection.service_catalog_id == electricity_catalog.id)
    ).all()
    connection_ids = [connection.id for connection in connections]
    if not connection_ids:
        return []
    rows = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id.in_(connection_ids))
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.meter_id.is_not(None))
        .order_by(ConnectionChargeLine.meter_id.desc(), ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
    ).all()
    grouped: dict[tuple[int, date], list[ConnectionChargeLine]] = {}
    for row in rows:
        grouped.setdefault((row.meter_id, row.effective_from), []).append(row)
    out: list[ElectricityPlanHistoryOut] = []
    for (meter_id, effective_from), group_rows in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0]), reverse=True):
        meter = db.get(Meter, meter_id)
        register_map: dict[str, ConnectionChargeLine] = {}
        ordered_registers: list[str] = []
        for line in sorted(group_rows, key=lambda item: (ELECTRICITY_REGISTER_ORDER.get(item.meter_register or "total", 99), item.id)):
            register_name = (line.meter_register or "total").strip() or "total"
            if register_name not in register_map:
                register_map[register_name] = line
                ordered_registers.append(register_name)
        plan_mode = _electricity_plan_mode_from_registers(ordered_registers) or "single"
        next_effective_from = next(
            (
                group_effective_from
                for group_meter_id, group_effective_from in sorted(grouped.keys(), key=lambda value: value[1])
                if group_meter_id == meter_id and group_effective_from > effective_from
            ),
            None,
        )
        readings = db.scalars(
            select(MeterReading)
            .where(MeterReading.meter_id == meter_id)
            .order_by(MeterReading.year.asc(), MeterReading.month.asc())
        ).all()
        next_key = (
            _period_key(next_effective_from.year, next_effective_from.month) if next_effective_from is not None else None
        )
        period_has_readings = any(
            _period_key(reading.year, reading.month) >= _period_key(effective_from.year, effective_from.month)
            and (next_key is None or _period_key(reading.year, reading.month) < next_key)
            for reading in readings
        )
        delete_block_reason = (
            "Є збережені показники у періоді дії цього режиму. Спершу приберіть або перенесіть ці показники."
            if period_has_readings
            else None
        )
        out.append(
            ElectricityPlanHistoryOut(
                id=min(line.id for line in group_rows),
                apartment_id=apartment_id,
                meter_id=meter_id,
                meter_service_name=_meter_display_name(meter),
                meter_serial_number=meter.serial_number if meter else None,
                plan_mode=plan_mode,
                effective_from=effective_from,
                single_service_name=register_map.get("total").label if register_map.get("total") else None,
                day_service_name=register_map.get("day").label if register_map.get("day") else None,
                night_service_name=register_map.get("night").label if register_map.get("night") else None,
                peak_service_name=register_map.get("peak").label if register_map.get("peak") else None,
                semi_peak_service_name=register_map.get("semi_peak").label if register_map.get("semi_peak") else None,
                off_peak_service_name=register_map.get("off_peak").label if register_map.get("off_peak") else None,
                single_price_per_unit=register_map.get("total").price_per_unit if register_map.get("total") else None,
                day_price_per_unit=register_map.get("day").price_per_unit if register_map.get("day") else None,
                night_price_per_unit=register_map.get("night").price_per_unit if register_map.get("night") else None,
                peak_price_per_unit=register_map.get("peak").price_per_unit if register_map.get("peak") else None,
                semi_peak_price_per_unit=register_map.get("semi_peak").price_per_unit if register_map.get("semi_peak") else None,
                off_peak_price_per_unit=register_map.get("off_peak").price_per_unit if register_map.get("off_peak") else None,
                single_initial_reading=register_map.get("total").initial_reading if register_map.get("total") else None,
                day_initial_reading=register_map.get("day").initial_reading if register_map.get("day") else None,
                night_initial_reading=register_map.get("night").initial_reading if register_map.get("night") else None,
                peak_initial_reading=register_map.get("peak").initial_reading if register_map.get("peak") else None,
                semi_peak_initial_reading=register_map.get("semi_peak").initial_reading if register_map.get("semi_peak") else None,
                off_peak_initial_reading=register_map.get("off_peak").initial_reading if register_map.get("off_peak") else None,
                note=None,
                created_at=min((line.created_at for line in group_rows if line.created_at is not None), default=datetime.now(UTC)),
                can_delete=not period_has_readings,
                delete_block_reason=delete_block_reason,
            )
        )
    return out


@router.delete("/apartments/{apartment_id}/electricity-plans/{plan_id}")
def delete_electricity_plan(
    apartment_id: int,
    plan_id: int,
    user: AdminUser = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    plan = db.get(ConnectionChargeLine, plan_id)
    if plan is None or plan.meter_id is None:
        raise HTTPException(status_code=404, detail="Electricity plan not found.")
    connection = db.get(ApartmentServiceConnection, plan.connection_id)
    if connection is None or connection.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Electricity plan not found.")
    effective_from = plan.effective_from
    meter_id = plan.meter_id
    plan_lines = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == connection.id)
        .where(ConnectionChargeLine.meter_id == meter_id)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.effective_from == effective_from)
    ).all()
    next_plan = db.scalar(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == connection.id)
        .where(ConnectionChargeLine.meter_id == meter_id)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.effective_from > effective_from)
        .order_by(ConnectionChargeLine.effective_from.asc(), ConnectionChargeLine.id.asc())
    )
    next_key = _period_key(next_plan.effective_from.year, next_plan.effective_from.month) if next_plan is not None else None
    readings = db.scalars(select(MeterReading).where(MeterReading.meter_id == meter_id)).all()
    has_readings = any(
        _period_key(reading.year, reading.month) >= _period_key(effective_from.year, effective_from.month)
        and (next_key is None or _period_key(reading.year, reading.month) < next_key)
        for reading in readings
    )
    if has_readings:
        raise HTTPException(
            status_code=409,
            detail="Неможливо видалити режим: у періоді його дії вже є збережені показники.",
        )
    changed_services = [line.label for line in plan_lines if (line.label or "").strip()]
    for line in plan_lines:
        previous_line = db.scalar(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == line.connection_id)
            .where(ConnectionChargeLine.meter_id == line.meter_id)
            .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
            .where(ConnectionChargeLine.meter_register == line.meter_register)
            .where(ConnectionChargeLine.effective_from < line.effective_from)
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        )
        if previous_line is not None and previous_line.effective_to == effective_from - timedelta(days=1):
            previous_line.effective_to = next_plan.effective_from - timedelta(days=1) if next_plan is not None else None
        db.delete(line)
    db.commit()
    _recalc_from_period(db, apartment_id, effective_from.year, effective_from.month)
    _log_billing_change(
        db,
        apartment_id=apartment_id,
        year=effective_from.year,
        month=effective_from.month,
        actor_username=user.username,
        action="electricity_plan_deleted",
        entity_type="electricity_plan",
        entity_id=plan_id,
        service_name="Електроенергія",
        details={
            "meter_id": meter_id,
            "effective_from": effective_from.isoformat(),
            "changed_services": changed_services,
        },
    )
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/meters/{meter_id}/expected-registers", response_model=MeterExpectedRegistersOut)
def get_meter_expected_registers(
    apartment_id: int,
    meter_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    meter = db.get(Meter, meter_id)
    if meter is None or meter.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Meter not found for this apartment.")
    active_lines = _active_meter_charge_lines(db, meter_id, year, month)
    if meter.utility_type != UtilityType.electricity or not active_lines:
        current = db.scalar(
            select(MeterReading).where(
                MeterReading.meter_id == meter_id,
                MeterReading.register_name == "total",
                MeterReading.year == year,
                MeterReading.month == month,
            )
        )
        return MeterExpectedRegistersOut(
            meter_id=meter.id,
            meter_service_name=_meter_display_name(meter),
            plan_mode="single",
            effective_from=None,
            registers=[
                MeterExpectedRegisterItem(
                    register_name="total",
                    label="Загальний",
                    service_name=_meter_display_name(meter),
                    previous_reading=_resolve_previous_reading_by_register(
                        db,
                        meter_id,
                        "total",
                        year,
                        month,
                        Decimal(meter.initial_reading or 0),
                    ),
                    current_reading=Decimal(current.value) if current else None,
                )
            ],
        )

    register_map: dict[str, ConnectionChargeLine] = {}
    ordered_registers: list[str] = []
    for line in sorted(active_lines, key=lambda item: (ELECTRICITY_REGISTER_ORDER.get(item.meter_register or "total", 99), item.id)):
        register_name = (line.meter_register or "total").strip() or "total"
        if register_name not in register_map:
            register_map[register_name] = line
            ordered_registers.append(register_name)

    registers: list[MeterExpectedRegisterItem] = []
    for register_name in ordered_registers:
        current = db.scalar(
            select(MeterReading).where(
                MeterReading.meter_id == meter_id,
                MeterReading.register_name == register_name,
                MeterReading.year == year,
                MeterReading.month == month,
            )
        )
        registers.append(
            MeterExpectedRegisterItem(
                register_name=register_name,
                label=ELECTRICITY_REGISTER_LABELS.get(register_name, register_name),
                service_name=register_map[register_name].label,
                previous_reading=_resolve_previous_reading_by_register(
                    db,
                    meter_id,
                    register_name,
                    year,
                    month,
                    Decimal(meter.initial_reading or 0),
                ),
                current_reading=Decimal(current.value) if current else None,
            )
        )
    return MeterExpectedRegistersOut(
        meter_id=meter.id,
        meter_service_name=_meter_display_name(meter),
        plan_mode=_electricity_plan_mode_from_registers(ordered_registers) or "single",
        effective_from=max((line.effective_from for line in active_lines), default=None),
        registers=registers,
    )


@router.post("/readings", response_model=ReadingOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def add_or_update_reading(
    payload: ReadingCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    meter = db.get(Meter, payload.meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    previous_value = _resolve_previous_reading_by_register(
        db,
        payload.meter_id,
        payload.register_name,
        payload.year,
        payload.month,
        Decimal(meter.initial_reading or 0),
    )
    if Decimal(payload.value) < previous_value:
        raise HTTPException(
            status_code=422,
            detail=(
                "Поточний показник не може бути меншим за попередній. "
                f"Попередній показник для цього реєстру: {previous_value}"
            ),
        )
    existing = db.scalar(
        select(MeterReading).where(
            and_(
                MeterReading.meter_id == payload.meter_id,
                MeterReading.register_name == payload.register_name,
                MeterReading.year == payload.year,
                MeterReading.month == payload.month,
            )
        )
    )
    if existing:
        old_value = Decimal(existing.value)
        existing.value = payload.value
        db.commit()
        _recalc_from_period(db, meter.apartment_id, payload.year, payload.month)
        db.refresh(existing)
        _log_billing_change(
            db,
            apartment_id=meter.apartment_id,
            year=payload.year,
            month=payload.month,
            actor_username=user.username,
            action="reading_updated",
            entity_type="meter_reading",
            entity_id=existing.id,
            service_name=_meter_display_name(meter),
            details={
                "register_name": payload.register_name,
                "old_value": str(old_value),
                "new_value": str(existing.value),
            },
        )
        db.commit()
        return existing

    reading = MeterReading(**payload.model_dump())
    db.add(reading)
    db.commit()
    _recalc_from_period(db, meter.apartment_id, payload.year, payload.month)
    db.refresh(reading)
    _log_billing_change(
        db,
        apartment_id=meter.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="reading_created",
        entity_type="meter_reading",
        entity_id=reading.id,
        service_name=_meter_display_name(meter),
        details={"register_name": payload.register_name, "new_value": str(reading.value)},
    )
    db.commit()
    return reading


@router.put("/meters/{meter_id}/initial-reading", dependencies=[Depends(require_write_access)])
def update_meter_initial_reading(
    meter_id: int,
    payload: MeterInitialReadingUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    old_value = Decimal(meter.initial_reading)
    meter.initial_reading = payload.value
    db.commit()
    first = db.scalar(
        select(MeterReading)
        .where(MeterReading.meter_id == meter_id)
        .order_by(MeterReading.year.asc(), MeterReading.month.asc())
    )
    if first is not None:
        _recalc_from_period(db, meter.apartment_id, first.year, first.month)
        log_year, log_month = first.year, first.month
    else:
        today = date.today()
        log_year, log_month = today.year, today.month
    _log_billing_change(
        db,
        apartment_id=meter.apartment_id,
        year=log_year,
        month=log_month,
        actor_username=user.username,
        action="meter_initial_reading_updated",
        entity_type="meter",
        entity_id=meter.id,
        service_name=_meter_display_name(meter),
        details={"old_value": str(old_value), "new_value": str(meter.initial_reading)},
    )
    db.commit()
    return {"status": "updated"}


@router.post("/billing/generate", response_model=InvoiceOut, dependencies=[Depends(require_write_access)])
def generate_billing(payload: BillingGenerateRequest, db: Session = Depends(get_db)):
    try:
        return generate_invoice(db, payload.apartment_id, payload.year, payload.month)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/billing/recalculate", dependencies=[Depends(require_write_access)])
def recalculate_billing(
    payload: BillingRecalculateRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    invoice = db.scalar(
        select(Invoice).where(
            and_(
                Invoice.apartment_id == payload.apartment_id,
                Invoice.year == payload.year,
                Invoice.month == payload.month,
            )
        )
    )
    if invoice is None:
        try:
            generate_invoice(db, payload.apartment_id, payload.year, payload.month)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
    _recalc_from_period(db, payload.apartment_id, payload.year, payload.month)
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="month_recalculated",
        entity_type="invoice",
        details={},
    )
    db.commit()
    return {"status": "recalculated"}


@router.post("/billing/lock", dependencies=[Depends(require_write_access)])
def lock_billing_month(
    payload: BillingLockRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    row = db.scalar(
        select(BillingLock).where(
            and_(
                BillingLock.apartment_id == payload.apartment_id,
                BillingLock.year == payload.year,
                BillingLock.month == payload.month,
            )
        )
    )
    if row is None:
        db.add(BillingLock(apartment_id=payload.apartment_id, year=payload.year, month=payload.month))
        db.commit()
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="month_locked",
        entity_type="billing_lock",
        details={},
    )
    db.commit()
    return {"status": "locked"}


@router.post("/billing/unlock", dependencies=[Depends(require_write_access)])
def unlock_billing_month(
    payload: BillingLockRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    row = db.scalar(
        select(BillingLock).where(
            and_(
                BillingLock.apartment_id == payload.apartment_id,
                BillingLock.year == payload.year,
                BillingLock.month == payload.month,
            )
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="month_unlocked",
        entity_type="billing_lock",
        details={},
    )
    db.commit()
    return {"status": "unlocked"}


@router.post("/payments/utilities", dependencies=[Depends(require_write_access)])
def add_utility_payment(
    payload: UtilityPaymentCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    payment_year, payment_month = _period_from_date(payload.paid_at)
    invoice = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == payload.apartment_id, Invoice.year == payment_year, Invoice.month == payment_month)
        )
    )
    if invoice is None:
        try:
            generate_invoice(db, payload.apartment_id, payment_year, payment_month)
        except ValueError:
            pass
        invoice = db.scalar(
            select(Invoice).where(
                and_(Invoice.apartment_id == payload.apartment_id, Invoice.year == payment_year, Invoice.month == payment_month)
            )
        )

    tenancy_on_payment_date = _active_tenancy(db, payload.apartment_id, payload.paid_at)
    payer_type = payload.payer_type or ("tenant" if tenancy_on_payment_date is not None else "owner")
    if payer_type not in {"tenant", "owner"}:
        raise HTTPException(status_code=400, detail="Invalid payer type.")

    tenant_id: int | None = None
    if payer_type == "tenant":
        tenant_id = payload.tenant_id
        if tenant_id is None and tenancy_on_payment_date is not None:
            tenant_id = tenancy_on_payment_date.tenant_id
        if tenant_id is None and invoice is not None:
            tenant_id = invoice.tenant_id
        if tenant_id is None or db.get(Tenant, tenant_id) is None:
            raise HTTPException(status_code=400, detail="Tenant payment requires a valid tenant.")

    previous_total = db.scalars(
        select(UtilityPayment).where(
            and_(
                UtilityPayment.apartment_id == payload.apartment_id,
                UtilityPayment.paid_at >= date(payment_year, payment_month, 1),
                UtilityPayment.paid_at <= date(payment_year, payment_month, monthrange(payment_year, payment_month)[1]),
            )
        )
    ).all()
    before_total_amount = sum((Decimal(row.amount) for row in previous_total), Decimal("0.00")).quantize(Decimal("0.01"))
    payment_row = UtilityPayment(
        apartment_id=payload.apartment_id,
        tenant_id=tenant_id,
        invoice_id=invoice.id if invoice else None,
        payer_type=payer_type,
        year=payment_year,
        month=payment_month,
        amount=payload.amount,
        paid_at=payload.paid_at,
        note=payload.note,
        confirmed=True,
    )
    db.add(payment_row)
    db.flush()
    _sync_invoice_payment_totals(db, payload.apartment_id, payment_year, payment_month)
    db.commit()
    _recalc_from_period(db, payload.apartment_id, payment_year, payment_month)
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payment_year,
        month=payment_month,
        actor_username=user.username,
        action="utility_payment_saved",
        entity_type="utility_payment",
        entity_id=payment_row.id,
        details={
            "payer_type": payer_type,
            "tenant_id": tenant_id,
            "payment_amount": str(payload.amount),
            "payment_paid_at": payload.paid_at.isoformat(),
            "payment_note": payload.note,
            "period_paid_before": str(before_total_amount),
            "period_paid_after": str(
                sum(
                    (
                        Decimal(row.amount)
                        for row in db.scalars(
                            select(UtilityPayment).where(
                                and_(
                                    UtilityPayment.apartment_id == payload.apartment_id,
                                    UtilityPayment.paid_at >= date(payment_year, payment_month, 1),
                                    UtilityPayment.paid_at <= date(payment_year, payment_month, monthrange(payment_year, payment_month)[1]),
                                )
                            )
                        ).all()
                    ),
                    Decimal("0.00"),
                ).quantize(Decimal("0.01"))
            ),
        },
    )
    db.commit()
    return {"status": "saved"}


@router.get("/apartments/{apartment_id}/utility-payments", response_model=list[UtilityPaymentOut])
def list_utility_payments(
    apartment_id: int,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    query = select(UtilityPayment).where(UtilityPayment.apartment_id == apartment_id)
    if year is not None:
        query = query.where(text("YEAR(paid_at) = :year")).params(year=year)
    if month is not None:
        query = query.where(text("MONTH(paid_at) = :month")).params(month=month)
    rows = db.scalars(query.order_by(UtilityPayment.paid_at.desc(), UtilityPayment.id.desc())).all()
    out: list[UtilityPaymentOut] = []
    for row in rows:
        tenant = db.get(Tenant, row.tenant_id) if row.tenant_id else None
        out.append(
            UtilityPaymentOut(
                id=row.id,
                apartment_id=row.apartment_id,
                tenant_id=row.tenant_id,
                tenant_name=tenant.full_name if tenant else None,
                year=row.paid_at.year,
                month=row.paid_at.month,
                amount=row.amount,
                paid_at=row.paid_at,
                note=row.note,
                payer_type=row.payer_type or "tenant",
            )
        )
    return out


@router.put("/payments/utilities/{payment_id}", dependencies=[Depends(require_write_access)])
def update_utility_payment(
    payment_id: int,
    payload: UtilityPaymentUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    row = db.get(UtilityPayment, payment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if db.get(Apartment, row.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    before = {
        "year": row.paid_at.year,
        "month": row.paid_at.month,
        "amount": str(row.amount),
        "paid_at": row.paid_at.isoformat(),
        "note": row.note,
        "payer_type": row.payer_type,
        "tenant_id": row.tenant_id,
    }

    tenancy_on_payment_date = _active_tenancy(db, row.apartment_id, payload.paid_at)
    payer_type = payload.payer_type or ("tenant" if tenancy_on_payment_date is not None else "owner")
    if payer_type not in {"tenant", "owner"}:
        raise HTTPException(status_code=400, detail="Invalid payer type.")
    tenant_id: int | None = None
    if payer_type == "tenant":
        tenant_id = payload.tenant_id
        if tenant_id is None and tenancy_on_payment_date is not None:
            tenant_id = tenancy_on_payment_date.tenant_id
        if tenant_id is None:
            raise HTTPException(status_code=400, detail="Tenant payment requires a tenant.")
        if db.get(Tenant, tenant_id) is None:
            raise HTTPException(status_code=400, detail="Tenant not found.")

    payment_year, payment_month = _period_from_date(payload.paid_at)
    row.year = payment_year
    row.month = payment_month
    row.amount = payload.amount
    row.paid_at = payload.paid_at
    row.note = payload.note
    row.payer_type = payer_type
    row.tenant_id = tenant_id
    invoice = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == row.apartment_id, Invoice.year == payment_year, Invoice.month == payment_month)
        )
    )
    row.invoice_id = invoice.id if invoice else None

    _sync_invoice_payment_totals(db, row.apartment_id, before["year"], before["month"])
    _sync_invoice_payment_totals(db, row.apartment_id, row.year, row.month)
    db.commit()
    before_key = _month_key(before["year"], before["month"])
    after_key = _month_key(row.year, row.month)
    recalc_year, recalc_month = (
        (before["year"], before["month"]) if before_key <= after_key else (row.year, row.month)
    )
    _recalc_from_period(db, row.apartment_id, recalc_year, recalc_month)
    _log_billing_change(
        db,
        apartment_id=row.apartment_id,
        year=row.year,
        month=row.month,
        actor_username=user.username,
        action="utility_payment_updated",
        entity_type="utility_payment",
        entity_id=row.id,
        details={
            "before": before,
            "after": {
                "year": row.year,
                "month": row.month,
                "amount": str(row.amount),
                "paid_at": row.paid_at.isoformat(),
                "note": row.note,
                "payer_type": row.payer_type,
                "tenant_id": row.tenant_id,
            },
        },
    )
    db.commit()
    return {"status": "updated"}


@router.delete("/payments/utilities/{payment_id}", dependencies=[Depends(require_write_access)])
def delete_utility_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    row = db.get(UtilityPayment, payment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    apartment_id = row.apartment_id
    year = row.year
    month = row.month
    amount = str(row.amount)
    payer_type = row.payer_type
    tenant_id = row.tenant_id
    db.delete(row)
    _sync_invoice_payment_totals(db, apartment_id, year, month)
    db.commit()
    _recalc_from_period(db, apartment_id, year, month)
    _log_billing_change(
        db,
        apartment_id=apartment_id,
        year=year,
        month=month,
        actor_username=user.username,
        action="utility_payment_deleted",
        entity_type="utility_payment",
        entity_id=payment_id,
        details={
            "amount": amount,
            "payer_type": payer_type,
            "tenant_id": tenant_id,
        },
    )
    db.commit()
    return {"status": "deleted"}


@router.put(
    "/apartments/{apartment_id}/service-ledger/{service_name}",
    response_model=ServiceLedgerRowOut,
    dependencies=[Depends(require_write_access)],
)
def upsert_service_ledger_month(
    apartment_id: int,
    service_name: str,
    payload: ServiceLedgerUpsert,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    normalized_service_name = service_name.strip()
    if not normalized_service_name:
        raise HTTPException(status_code=400, detail="Service name is required.")
    row = db.scalar(
        select(ServiceLedgerEntry).where(
            and_(
                ServiceLedgerEntry.apartment_id == apartment_id,
                ServiceLedgerEntry.service_name == normalized_service_name,
                ServiceLedgerEntry.year == payload.year,
                ServiceLedgerEntry.month == payload.month,
            )
        )
    )
    if row is None:
        row = ServiceLedgerEntry(
            apartment_id=apartment_id,
            service_name=normalized_service_name,
            year=payload.year,
            month=payload.month,
        )
        db.add(row)
        db.flush()
    old_values = {
        "accrued": str(row.accrued),
        "paid": str(row.paid),
        "adjustment": str(row.adjustment),
        "benefit": str(row.benefit),
        "subsidy": str(row.subsidy),
    }
    row.accrued = payload.accrued
    row.paid = payload.paid
    row.adjustment = payload.adjustment
    row.benefit = payload.benefit
    row.subsidy = payload.subsidy
    row.updated_at = datetime.now(UTC)
    _recalc_service_ledger_from_period(
        db,
        apartment_id=apartment_id,
        service_name=normalized_service_name,
        start_year=payload.year,
        start_month=payload.month,
    )
    db.commit()
    db.refresh(row)
    _log_billing_change(
        db,
        apartment_id=apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="service_ledger_saved",
        entity_type="service_ledger",
        entity_id=row.id,
        service_name=normalized_service_name,
        details={
            "old": old_values,
            "new": {
                "accrued": str(row.accrued),
                "paid": str(row.paid),
                "adjustment": str(row.adjustment),
                "benefit": str(row.benefit),
                "subsidy": str(row.subsidy),
            },
            "opening_balance": str(row.opening_balance),
            "closing_balance": str(row.closing_balance),
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.get(
    "/apartments/{apartment_id}/service-ledger/{service_name}/history",
    response_model=list[ServiceLedgerRowOut],
)
def service_ledger_history(
    apartment_id: int,
    service_name: str,
    limit: int = 24,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    safe_limit = min(max(limit, 1), 120)
    rows = db.scalars(
        select(ServiceLedgerEntry)
        .where(ServiceLedgerEntry.apartment_id == apartment_id)
        .where(ServiceLedgerEntry.service_name == service_name.strip())
        .order_by(ServiceLedgerEntry.year.desc(), ServiceLedgerEntry.month.desc(), ServiceLedgerEntry.id.desc())
        .limit(safe_limit)
    ).all()
    return rows


@router.put("/rent", dependencies=[Depends(require_write_access)])
def upsert_rent(payload: RentRecordUpsert, db: Session = Depends(get_db)):
    tenancy = _active_tenancy(db, payload.apartment_id, date(payload.year, payload.month, 1))
    if tenancy is None:
        raise HTTPException(status_code=400, detail="No active tenant.")
    row = db.scalar(
        select(RentLedger).where(
            and_(RentLedger.apartment_id == payload.apartment_id, RentLedger.year == payload.year, RentLedger.month == payload.month)
        )
    )
    if row is None:
        row = RentLedger(apartment_id=payload.apartment_id, tenant_id=tenancy.tenant_id, year=payload.year, month=payload.month)
        db.add(row)
    row.tenant_id = tenancy.tenant_id
    row.accrual_amount = payload.accrual_amount
    row.payment_amount = payload.payment_amount
    row.currency = payload.currency
    row.paid_at = payload.paid_at
    row.confirmed = payload.confirmed
    row.note = payload.note
    db.commit()
    return {"status": "saved"}


@router.get("/dashboard/apartments", response_model=list[ApartmentOverviewOut])
def apartments_overview(db: Session = Depends(get_db)):
    apartments = db.scalars(select(Apartment).order_by(Apartment.address)).all()
    result: list[ApartmentOverviewOut] = []
    for a in apartments:
        utility_balance = _actual_current_utility_balance(db, a.id)
        rent_balance = Decimal("0.00")
        for row in db.scalars(select(RentLedger).where(RentLedger.apartment_id == a.id)).all():
            rent_balance += Decimal(row.accrual_amount) - Decimal(row.payment_amount)
        tenancy = _active_tenancy(db, a.id, date.today())
        tenant_name = db.get(Tenant, tenancy.tenant_id).full_name if tenancy else None
        result.append(
            ApartmentOverviewOut(
                apartment_id=a.id,
                code=a.code,
                address=a.address,
                short_address=a.short_address,
                tenant_name=tenant_name,
                utility_balance=utility_balance,
                rent_balance=rent_balance,
                total_balance=utility_balance + rent_balance,
            )
        )
    return result


@router.get("/dashboard/apartments/{apartment_id}", response_model=ApartmentDetailOut)
def apartment_detail(apartment_id: int, year: int | None = None, month: int | None = None, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    if year is None or month is None:
        year, month = _default_period()

    tenancy = _active_tenancy(db, apartment_id, date(year, month, 1))
    tenant = db.get(Tenant, tenancy.tenant_id) if tenancy else None
    invoice = db.scalar(select(Invoice).where(and_(Invoice.apartment_id == apartment_id, Invoice.year == year, Invoice.month == month)))
    prev_debt, month_charges, month_payments, current_balance = _effective_utility_period(db, apartment_id, year, month)
    confirmed_previous_debt = _confirmed_previous_utility_debt(db, apartment_id, year, month)
    actual_current_balance = _actual_current_utility_balance(db, apartment_id)
    report_generated_at = date.today()
    month_payment_row = db.scalar(
        select(UtilityPayment)
        .where(
            UtilityPayment.apartment_id == apartment_id,
            UtilityPayment.paid_at >= date(year, month, 1),
            UtilityPayment.paid_at <= date(year, month, monthrange(year, month)[1]),
        )
        .order_by(UtilityPayment.paid_at.desc(), UtilityPayment.id.desc())
    )

    rows = _build_period_rows(db, apartment_id, year, month, invoice)

    month_charges_from_rows = sum((Decimal(r.amount) for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))
    current_balance_from_rows = (confirmed_previous_debt + month_charges_from_rows - month_payments).quantize(Decimal("0.01"))
    report_payments_to_date, report_payment_row = _payments_received_between(
        db,
        apartment_id=apartment_id,
        start_date=date(year, month, 1),
        end_date=report_generated_at,
    )
    report_balance = (confirmed_previous_debt + month_charges_from_rows - report_payments_to_date).quantize(Decimal("0.01"))

    rent = db.scalar(select(RentLedger).where(and_(RentLedger.apartment_id == apartment_id, RentLedger.year == year, RentLedger.month == month)))
    calc_locked = _is_month_locked(db, apartment_id, year, month)
    return ApartmentDetailOut(
        apartment_id=apartment.id,
        code=apartment.code,
        address=apartment.address,
        short_address=apartment.short_address,
        country=apartment.country,
        region=apartment.region,
        locality=apartment.locality,
        street=apartment.street,
        house_number=apartment.house_number,
        apartment_number=apartment.apartment_number,
        postal_code=apartment.postal_code,
        registered_residents=apartment.registered_residents,
        area_m2=apartment.area_m2,
        living_area_m2=apartment.living_area_m2,
        entrance=apartment.entrance,
        floor=apartment.floor,
        room_count=apartment.room_count,
        latitude=apartment.latitude,
        longitude=apartment.longitude,
        google_maps_url=apartment.google_maps_url,
        timezone=apartment.timezone or "Europe/Kyiv",
        location_note=apartment.location_note,
        object_notes=apartment.object_notes,
        tenant=_tenant_out(tenant),
        year=year,
        month=month,
        utility_balance=BalanceExplainOut(
            previous_month_debt=confirmed_previous_debt,
            month_charges=month_charges_from_rows,
            month_payments=month_payments,
            month_payment_date=month_payment_row.paid_at if month_payment_row else None,
            month_payment_note=month_payment_row.note if month_payment_row else None,
            current_balance=current_balance_from_rows,
            actual_current_balance=actual_current_balance,
            report_generated_at=report_generated_at,
            report_payments_to_date=report_payments_to_date,
            report_payment_date=report_payment_row.paid_at if report_payment_row else None,
            report_payment_note=report_payment_row.note if report_payment_row else None,
            report_balance=report_balance,
        ),
        rent=(
            RentMonthOut(
                accrual_amount=rent.accrual_amount,
                payment_amount=rent.payment_amount,
                currency=rent.currency,
                paid_at=rent.paid_at,
                confirmed=rent.confirmed,
                note=rent.note,
            )
            if rent
            else None
        ),
        rows=rows,
        calc_locked=calc_locked,
    )


@router.get("/billing/history", response_model=list[BillingChangeLogOut])
def billing_history(
    apartment_id: int,
    year: int,
    month: int,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    safe_limit = min(max(limit, 1), 500)
    rows = db.scalars(
        select(BillingChangeLog)
        .where(BillingChangeLog.apartment_id == apartment_id)
        .where(BillingChangeLog.year == year)
        .where(BillingChangeLog.month == month)
        .order_by(BillingChangeLog.created_at.desc(), BillingChangeLog.id.desc())
        .limit(safe_limit)
    ).all()
    out: list[BillingChangeLogOut] = []
    for row in rows:
        details: dict = {}
        if row.details_json:
            try:
                parsed = json.loads(row.details_json)
                if isinstance(parsed, dict):
                    details = parsed
            except json.JSONDecodeError:
                details = {"raw": row.details_json}
        out.append(
            BillingChangeLogOut(
                id=row.id,
                apartment_id=row.apartment_id,
                year=row.year,
                month=row.month,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                service_name=row.service_name,
                actor_username=row.actor_username,
                details=details,
                created_at=row.created_at,
            )
        )
    return out


@router.get("/apartments/{apartment_id}/tariffs", response_model=list[ApartmentTariffRowOut])
def apartment_tariffs(apartment_id: int, year: int | None = None, month: int | None = None, db: Session = Depends(get_db)):
    _legacy_api_disabled("Legacy tariff list API")
    raise AssertionError("unreachable")


@router.get("/automations", response_model=list[AutomationRowOut])
def list_automations(db: Session = Depends(get_db)):
    automations = db.scalars(
        select(ApartmentAutomation).order_by(ApartmentAutomation.apartment_id, ApartmentAutomation.id)
    ).all()
    apartments = {a.id: a for a in db.scalars(select(Apartment)).all()}
    out: list[AutomationRowOut] = []
    for automation in automations:
        apartment = apartments.get(automation.apartment_id)
        if apartment is None:
            continue
        service_name = _automation_service_name(db, automation=automation)
        out.append(_automation_row_out(db, automation, apartment, service_name))
    return out


@router.get("/automation-templates", response_model=list[AutomationTemplateOut])
def list_automation_templates(db: Session = Depends(get_db)):
    rows = db.scalars(select(AutomationTemplate).order_by(AutomationTemplate.name)).all()
    out: list[AutomationTemplateOut] = []
    for row in rows:
        out.append(
            AutomationTemplateOut(
                id=row.id,
                code=row.code,
                name=row.name,
                provider_id=row.provider_id,
                provider_name=row.provider.name_full if row.provider else None,
                utility_type=row.utility_type,
                cabinet_url=row.cabinet_url,
                description=row.description,
                supports_accrual=row.supports_accrual,
                supports_meter_submit=row.supports_meter_submit,
                is_active=row.is_active,
                created_at=row.created_at,
            )
        )
    return out


def _automation_template_out(row: AutomationTemplate) -> AutomationTemplateOut:
    return AutomationTemplateOut(
        id=row.id,
        code=row.code,
        name=row.name,
        provider_id=row.provider_id,
        provider_name=row.provider.name_full if row.provider else None,
        utility_type=row.utility_type,
        cabinet_url=row.cabinet_url,
        description=row.description,
        supports_accrual=row.supports_accrual,
        supports_meter_submit=row.supports_meter_submit,
        is_active=row.is_active,
        created_at=row.created_at,
    )


@router.post(
    "/automation-templates",
    response_model=AutomationTemplateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def create_automation_template(payload: AutomationTemplateCreate, db: Session = Depends(get_db)):
    provider = db.get(Provider, payload.provider_id) if payload.provider_id else None
    if payload.provider_id and provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row = AutomationTemplate(
        code=payload.code.strip(),
        name=payload.name.strip(),
        provider_id=payload.provider_id,
        utility_type=payload.utility_type,
        cabinet_url=payload.cabinet_url,
        description=payload.description,
        supports_accrual=payload.supports_accrual,
        supports_meter_submit=payload.supports_meter_submit,
        is_active=payload.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Automation template code already exists.")
    db.refresh(row)
    return _automation_template_out(row)


@router.put(
    "/automation-templates/{template_id}",
    response_model=AutomationTemplateOut,
    dependencies=[Depends(require_write_access)],
)
def update_automation_template(template_id: int, payload: AutomationTemplateUpdate, db: Session = Depends(get_db)):
    row = db.get(AutomationTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation template not found.")
    provider = db.get(Provider, payload.provider_id) if payload.provider_id else None
    if payload.provider_id and provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row.code = payload.code.strip()
    row.name = payload.name.strip()
    row.provider_id = payload.provider_id
    row.utility_type = payload.utility_type
    row.cabinet_url = payload.cabinet_url
    row.description = payload.description
    row.supports_accrual = payload.supports_accrual
    row.supports_meter_submit = payload.supports_meter_submit
    row.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Automation template code already exists.")
    db.refresh(row)
    return _automation_template_out(row)


@router.delete("/automation-templates/{template_id}", dependencies=[Depends(require_write_access)])
def delete_automation_template(template_id: int, db: Session = Depends(get_db)):
    row = db.get(AutomationTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation template not found.")
    linked = db.scalar(select(ApartmentAutomation.id).where(ApartmentAutomation.template_id == template_id).limit(1))
    if linked is not None:
        raise HTTPException(status_code=409, detail="Automation template is linked to apartments.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/automations", response_model=list[ApartmentAutomationOut])
def apartment_automations(apartment_id: int, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows = db.scalars(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .order_by(ApartmentAutomation.id.desc())
    ).all()
    out: list[ApartmentAutomationOut] = []
    for row in rows:
        out.append(_apartment_automation_out(row, apartment))
    return out


@router.put("/apartments/{apartment_id}/automations", response_model=ApartmentAutomationOut, dependencies=[Depends(require_write_access)])
def upsert_apartment_automation(apartment_id: int, payload: ApartmentAutomationUpsert, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    template = db.get(AutomationTemplate, payload.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Automation template not found.")
    provider = db.get(Provider, payload.provider_id) if payload.provider_id else None
    if payload.provider_id and provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row = db.scalar(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .where(ApartmentAutomation.template_id == payload.template_id)
    )
    if row is None:
        row = ApartmentAutomation(apartment_id=apartment_id, template_id=payload.template_id)
        db.add(row)
    row.provider_id = payload.provider_id or template.provider_id
    row.personal_account = payload.personal_account
    row.cabinet_url = payload.cabinet_url or template.cabinet_url
    row.cabinet_login = payload.cabinet_login
    if payload.cabinet_password is not None:
        row.cabinet_password_encrypted = encrypt_text(payload.cabinet_password)
    row.is_enabled = payload.is_enabled
    row.accrual_enabled = payload.accrual_enabled
    row.accrual_time = payload.accrual_time or "09:00"
    row.accrual_window_day_from = payload.accrual_window_day_from
    row.accrual_window_day_to = payload.accrual_window_day_to
    row.submit_enabled = payload.submit_enabled
    row.submit_time = payload.submit_time or "09:00"
    row.submit_window_day_from = payload.submit_window_day_from
    row.submit_window_day_to = payload.submit_window_day_to
    db.commit()
    db.refresh(row)
    return _apartment_automation_out(row, apartment)


@router.delete("/apartments/{apartment_id}/automations/{template_id}", dependencies=[Depends(require_write_access)])
def delete_apartment_automation(apartment_id: int, template_id: int, db: Session = Depends(get_db)):
    row = db.scalar(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .where(ApartmentAutomation.template_id == template_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Apartment automation not found.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.get("/automations/{automation_id}/logs", response_model=list[AutomationRunLogOut])
def automation_logs(automation_id: int, limit: int = 5, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AutomationRunLog)
        .where(AutomationRunLog.automation_id == automation_id)
        .order_by(AutomationRunLog.started_at.desc())
        .limit(max(1, min(limit, 20)))
    ).all()
    return [
        AutomationRunLogOut(
            id=row.id,
            automation_id=row.automation_id,
            apartment_id=row.apartment_id,
            service_name=row.service_name,
            register_name=row.register_name,
            target_year=row.target_year,
            target_month=row.target_month,
            mode=row.mode,
            status=row.status,
            message=row.message,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
        for row in rows
    ]


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)):
    return db.scalars(select(Provider).order_by(Provider.name_full)).all()


@router.get("/service-catalog", response_model=list[ServiceCatalogOut])
def list_service_catalog(db: Session = Depends(get_db)):
    return db.scalars(select(ServiceCatalog).order_by(ServiceCatalog.display_order, ServiceCatalog.name)).all()


@router.post("/service-catalog", response_model=ServiceCatalogOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_service_catalog_item(payload: ServiceCatalogCreate, db: Session = Depends(get_db)):
    if payload.derived_from_service_id and db.get(ServiceCatalog, payload.derived_from_service_id) is None:
        raise HTTPException(status_code=404, detail="Derived source service not found.")
    row = ServiceCatalog(
        code=payload.code.strip(),
        name=payload.name.strip(),
        calculation_kind=payload.calculation_kind,
        unit_name=payload.unit_name,
        requires_meter=payload.requires_meter,
        allowed_meter_utility_type=payload.allowed_meter_utility_type,
        default_provider_utility_type=payload.default_provider_utility_type,
        derived_from_service_id=payload.derived_from_service_id,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service with this code or name already exists.")
    db.refresh(row)
    return row


@router.put("/service-catalog/{service_catalog_id}", response_model=ServiceCatalogOut, dependencies=[Depends(require_write_access)])
def update_service_catalog_item(service_catalog_id: int, payload: ServiceCatalogUpdate, db: Session = Depends(get_db)):
    row = db.get(ServiceCatalog, service_catalog_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Service catalog item not found.")
    if payload.derived_from_service_id == service_catalog_id:
        raise HTTPException(status_code=422, detail="Service cannot derive from itself.")
    if payload.derived_from_service_id and db.get(ServiceCatalog, payload.derived_from_service_id) is None:
        raise HTTPException(status_code=404, detail="Derived source service not found.")
    row.code = payload.code.strip()
    row.name = payload.name.strip()
    row.calculation_kind = payload.calculation_kind
    row.unit_name = payload.unit_name
    row.requires_meter = payload.requires_meter
    row.allowed_meter_utility_type = payload.allowed_meter_utility_type
    row.default_provider_utility_type = payload.default_provider_utility_type
    row.derived_from_service_id = payload.derived_from_service_id
    row.display_order = payload.display_order
    row.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service with this code or name already exists.")
    db.refresh(row)
    return row


@router.delete("/service-catalog/{service_catalog_id}", dependencies=[Depends(require_write_access)])
def delete_service_catalog_item(service_catalog_id: int, db: Session = Depends(get_db)):
    row = db.get(ServiceCatalog, service_catalog_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Service catalog item not found.")
    in_use = db.scalar(
        select(ApartmentServiceConnection.id).where(ApartmentServiceConnection.service_catalog_id == service_catalog_id).limit(1)
    )
    in_use = in_use or db.scalar(
        select(ServiceCatalog.id).where(ServiceCatalog.derived_from_service_id == service_catalog_id).limit(1)
    )
    if in_use is not None:
        raise HTTPException(status_code=409, detail="Service is already used in object services or as a derived source.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/service-connections", response_model=list[ApartmentServiceConnectionOut])
def list_service_connections(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows = db.scalars(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .order_by(ApartmentServiceConnection.started_at, ApartmentServiceConnection.id)
    ).all()
    return [_service_connection_out(row, db) for row in rows]


@router.post("/service-connections", response_model=ApartmentServiceConnectionOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_service_connection(payload: ApartmentServiceConnectionCreate, db: Session = Depends(get_db)):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    if db.get(ServiceCatalog, payload.service_catalog_id) is None:
        raise HTTPException(status_code=404, detail="Service catalog item not found.")
    if payload.provider_id and db.get(Provider, payload.provider_id) is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    if payload.automation_id and db.get(ApartmentAutomation, payload.automation_id) is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    row = ApartmentServiceConnection(
        apartment_id=payload.apartment_id,
        service_catalog_id=payload.service_catalog_id,
        provider_id=payload.provider_id,
        personal_account=_clean_optional_text(payload.personal_account),
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        status=payload.status.strip(),
        note=_clean_optional_text(payload.note),
        automation_id=payload.automation_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _service_connection_out(row, db)


@router.put("/service-connections/{connection_id}", response_model=ApartmentServiceConnectionOut, dependencies=[Depends(require_write_access)])
def update_service_connection(connection_id: int, payload: ApartmentServiceConnectionUpdate, db: Session = Depends(get_db)):
    row = db.get(ApartmentServiceConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Service connection not found.")
    if payload.provider_id and db.get(Provider, payload.provider_id) is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    if payload.automation_id and db.get(ApartmentAutomation, payload.automation_id) is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    row.provider_id = payload.provider_id
    row.personal_account = _clean_optional_text(payload.personal_account)
    row.started_at = payload.started_at
    row.ended_at = payload.ended_at
    row.status = payload.status.strip()
    row.note = _clean_optional_text(payload.note)
    row.automation_id = payload.automation_id
    db.commit()
    db.refresh(row)
    return _service_connection_out(row, db)


@router.delete("/service-connections/{connection_id}", dependencies=[Depends(require_write_access)])
def delete_service_connection(connection_id: int, db: Session = Depends(get_db)):
    row = db.get(ApartmentServiceConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Service connection not found.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


def _validate_charge_line_payload(
    db: Session,
    connection: ApartmentServiceConnection,
    payload: ConnectionChargeLineCreate | ConnectionChargeLineUpdate,
    *,
    current_line_id: int | None = None,
) -> tuple[int | None, int | None, QuantitySource]:
    if payload.effective_to is not None and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=422, detail="effective_to must be >= effective_from.")

    meter_id = payload.meter_id
    derived_from_line_id = payload.derived_from_line_id
    quantity_source = payload.quantity_source

    if meter_id is not None:
        meter = db.get(Meter, meter_id)
        if meter is None:
            raise HTTPException(status_code=404, detail="Meter not found.")
        if meter.apartment_id != connection.apartment_id:
            raise HTTPException(status_code=409, detail="Meter belongs to another apartment.")

    if current_line_id is not None and derived_from_line_id == current_line_id:
        raise HTTPException(status_code=422, detail="Charge line cannot derive from itself.")

    if payload.line_kind == ChargeLineKind.fixed:
        if meter_id is not None:
            raise HTTPException(status_code=422, detail="Fixed line cannot have meter.")
        if derived_from_line_id is not None:
            raise HTTPException(status_code=422, detail="Fixed line cannot have derived source.")
        if quantity_source == QuantitySource.derived_consumption:
            raise HTTPException(status_code=422, detail="Fixed line cannot use derived consumption.")
        return meter_id, derived_from_line_id, quantity_source

    if payload.line_kind == ChargeLineKind.meter_register:
        if meter_id is None:
            raise HTTPException(status_code=422, detail="Meter line requires meter.")
        if derived_from_line_id is not None:
            raise HTTPException(status_code=422, detail="Meter line cannot have derived source.")
        if quantity_source == QuantitySource.derived_consumption:
            raise HTTPException(status_code=422, detail="Meter line cannot use derived consumption.")
        return meter_id, derived_from_line_id, quantity_source

    if payload.line_kind == ChargeLineKind.derived:
        if derived_from_line_id is None:
            raise HTTPException(status_code=422, detail="Derived line requires source line.")
        if meter_id is not None:
            raise HTTPException(status_code=422, detail="Derived line cannot have meter.")
        source_line = db.get(ConnectionChargeLine, derived_from_line_id)
        if source_line is None:
            raise HTTPException(status_code=404, detail="Derived source line not found.")
        source_connection = db.get(ApartmentServiceConnection, source_line.connection_id)
        if source_connection is None or source_connection.apartment_id != connection.apartment_id:
            raise HTTPException(status_code=409, detail="Derived source belongs to another apartment.")
        if source_line.line_kind == ChargeLineKind.derived:
            raise HTTPException(status_code=422, detail="Derived source must be fixed or meter line.")
        target_service = db.get(ServiceCatalog, connection.service_catalog_id)
        if target_service is not None and target_service.derived_from_service_id is not None:
            if source_connection.service_catalog_id != target_service.derived_from_service_id:
                raise HTTPException(
                    status_code=422,
                    detail="Derived source must match donor service defined in catalog.",
                )
            if source_line.line_kind != ChargeLineKind.meter_register:
                raise HTTPException(
                    status_code=422,
                    detail="Derived source for this service must be meter-based.",
                )
        return meter_id, derived_from_line_id, QuantitySource.derived_consumption

    return meter_id, derived_from_line_id, quantity_source


@router.post("/service-connections/{connection_id}/charge-lines", response_model=ConnectionChargeLineOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_charge_line(connection_id: int, payload: ConnectionChargeLineCreate, db: Session = Depends(get_db)):
    connection = db.get(ApartmentServiceConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Service connection not found.")
    meter_id, derived_from_line_id, quantity_source = _validate_charge_line_payload(db, connection, payload)
    row = ConnectionChargeLine(
        connection_id=connection_id,
        line_kind=payload.line_kind,
        label=payload.label.strip(),
        meter_id=meter_id,
        meter_register=payload.meter_register.strip(),
        derived_from_line_id=derived_from_line_id,
        initial_reading=payload.initial_reading,
        unit_name=payload.unit_name,
        price_per_unit=payload.price_per_unit,
        quantity_source=quantity_source,
        quantity_multiplier=payload.quantity_multiplier,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _recalc_from_period(db, connection.apartment_id, payload.effective_from.year, payload.effective_from.month)
    return row


@router.put("/charge-lines/{charge_line_id}", response_model=ConnectionChargeLineOut, dependencies=[Depends(require_write_access)])
def update_charge_line(charge_line_id: int, payload: ConnectionChargeLineUpdate, db: Session = Depends(get_db)):
    row = db.get(ConnectionChargeLine, charge_line_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Charge line not found.")
    connection = db.get(ApartmentServiceConnection, row.connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Service connection not found.")
    meter_id, derived_from_line_id, quantity_source = _validate_charge_line_payload(
        db, connection, payload, current_line_id=charge_line_id
    )
    row.line_kind = payload.line_kind
    row.label = payload.label.strip()
    row.meter_id = meter_id
    row.meter_register = payload.meter_register.strip()
    row.derived_from_line_id = derived_from_line_id
    row.initial_reading = payload.initial_reading
    row.unit_name = payload.unit_name
    row.price_per_unit = payload.price_per_unit
    row.quantity_source = quantity_source
    row.quantity_multiplier = payload.quantity_multiplier
    row.effective_from = payload.effective_from
    row.effective_to = payload.effective_to
    row.is_active = payload.is_active
    db.commit()
    db.refresh(row)
    _recalc_from_period(db, connection.apartment_id, payload.effective_from.year, payload.effective_from.month)
    return row


@router.post("/charge-lines/{charge_line_id}/apply-from-period", response_model=ConnectionChargeLineOut, dependencies=[Depends(require_write_access)])
def apply_charge_line_from_period(
    charge_line_id: int,
    payload: TariffApplyFromPeriod,
    db: Session = Depends(get_db),
):
    source = db.get(ConnectionChargeLine, charge_line_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Charge line not found.")
    connection = db.get(ApartmentServiceConnection, source.connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Service connection not found.")

    effective_from = date(payload.year, payload.month, 1)
    existing = db.scalar(
        select(ConnectionChargeLine).where(
            ConnectionChargeLine.connection_id == source.connection_id,
            ConnectionChargeLine.label == source.label,
            ConnectionChargeLine.line_kind == source.line_kind,
            ConnectionChargeLine.meter_id == source.meter_id,
            ConnectionChargeLine.meter_register == source.meter_register,
            ConnectionChargeLine.effective_from == effective_from,
        )
    )
    if existing is not None:
        existing.price_per_unit = payload.price_per_unit
        existing.unit_name = payload.unit_name
        existing.initial_reading = source.initial_reading
        db.commit()
        db.refresh(existing)
        return existing

    if source.effective_from < effective_from and (source.effective_to is None or source.effective_to >= effective_from):
        source.effective_to = effective_from - timedelta(days=1)

    clone = ConnectionChargeLine(
        connection_id=source.connection_id,
        line_kind=source.line_kind,
        label=source.label,
        meter_id=source.meter_id,
        meter_register=source.meter_register,
        derived_from_line_id=source.derived_from_line_id,
        initial_reading=source.initial_reading,
        unit_name=payload.unit_name,
        price_per_unit=payload.price_per_unit,
        quantity_source=source.quantity_source,
        quantity_multiplier=source.quantity_multiplier,
        effective_from=effective_from,
        effective_to=None,
        is_active=source.is_active,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.delete("/charge-lines/{charge_line_id}", dependencies=[Depends(require_write_access)])
def delete_charge_line(charge_line_id: int, db: Session = Depends(get_db)):
    row = db.get(ConnectionChargeLine, charge_line_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Charge line not found.")
    in_use = db.scalar(
        select(ConnectionChargeLine.id).where(ConnectionChargeLine.derived_from_line_id == charge_line_id).limit(1)
    )
    if in_use is not None:
        raise HTTPException(status_code=409, detail="Charge line is used as a derived source.")
    connection = db.get(ApartmentServiceConnection, row.connection_id)
    recalc_year = row.effective_from.year
    recalc_month = row.effective_from.month
    db.delete(row)
    db.commit()
    if connection is not None:
        _recalc_from_period(db, connection.apartment_id, recalc_year, recalc_month)
    return {"status": "deleted"}


@router.get("/meter-types", response_model=list[MeterTypeOut])
def list_meter_types(db: Session = Depends(get_db)):
    return db.scalars(select(MeterType).order_by(MeterType.sort_order, MeterType.name)).all()


@router.post("/meter-types", response_model=MeterTypeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_meter_type(payload: MeterTypeCreate, db: Session = Depends(get_db)):
    clean_name = payload.name.strip()
    row = MeterType(
        code=(payload.code.strip() if payload.code else _slugify_meter_type_code(clean_name)),
        name=clean_name,
        utility_type=payload.utility_type,
        default_service_name=clean_name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meter type with this code or name already exists.")
    db.refresh(row)
    return row


@router.put("/meter-types/{meter_type_id}", response_model=MeterTypeOut, dependencies=[Depends(require_write_access)])
def update_meter_type(meter_type_id: int, payload: MeterTypeUpdate, db: Session = Depends(get_db)):
    row = db.get(MeterType, meter_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Meter type not found.")
    clean_name = payload.name.strip()
    row.code = payload.code.strip() if payload.code else row.code
    row.name = clean_name
    row.utility_type = payload.utility_type
    row.default_service_name = clean_name
    row.sort_order = payload.sort_order
    row.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meter type with this code or name already exists.")
    db.refresh(row)
    return row


@router.delete("/meter-types/{meter_type_id}", dependencies=[Depends(require_write_access)])
def delete_meter_type(meter_type_id: int, db: Session = Depends(get_db)):
    row = db.get(MeterType, meter_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Meter type not found.")
    in_use = db.scalar(select(Meter.id).where(Meter.meter_type_id == meter_type_id).limit(1))
    if in_use is not None:
        raise HTTPException(status_code=409, detail="Meter type is already used in meters.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    row = Provider(
        name_full=payload.name_full.strip(),
        utility_type=payload.utility_type,
        provider_kind=payload.provider_kind,
        adapter_code=(payload.adapter_code or "manual_stub").strip(),
        is_active=payload.is_active,
        note=payload.note,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Provider with this name already exists.")
    db.refresh(row)
    return row


@router.put("/providers/{provider_id}", response_model=ProviderOut, dependencies=[Depends(require_write_access)])
def update_provider(provider_id: int, payload: ProviderUpdate, db: Session = Depends(get_db)):
    row = db.get(Provider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row.name_full = payload.name_full.strip()
    row.utility_type = payload.utility_type
    row.provider_kind = payload.provider_kind
    row.adapter_code = (payload.adapter_code or "manual_stub").strip()
    row.is_active = payload.is_active
    row.note = payload.note
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Provider with this name already exists.")
    db.refresh(row)
    return row


@router.delete("/providers/{provider_id}", dependencies=[Depends(require_write_access)])
def delete_provider(provider_id: int, db: Session = Depends(get_db)):
    row = db.get(Provider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    in_use = db.scalar(
        select(ApartmentAutomation.id).where(ApartmentAutomation.provider_id == provider_id).limit(1)
    )
    in_use = in_use or db.scalar(
        select(AutomationTemplate.id).where(AutomationTemplate.provider_id == provider_id).limit(1)
    )
    in_use = in_use or db.scalar(
        select(ApartmentServiceConnection.id).where(ApartmentServiceConnection.provider_id == provider_id).limit(1)
    )
    if in_use is not None:
        raise HTTPException(status_code=409, detail="Постачальник вже використовується у підключеннях або автоматизаціях.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.post("/automations/run", response_model=AutomationRowOut, dependencies=[Depends(require_write_access)])
def run_automation_once(automation_id: int, mode: str = "full", db: Session = Depends(get_db)):
    # Local import avoids module cycle (worker imports _recalc_from_period from this module).
    from app.workers.tariff_auto_check import run_meter_submit_for_automation, run_tariff_auto_check_for_automation

    automation = db.get(ApartmentAutomation, automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    apartment = db.get(Apartment, automation.apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")

    run_mode = (mode or "full").strip().lower()
    if run_mode not in {"full", "readings", "tariffs"}:
        raise HTTPException(status_code=400, detail="Invalid automation run mode.")
    try:
        if run_mode in {"full", "tariffs"}:
            run_tariff_auto_check_for_automation(db, automation=automation, now_utc=datetime.now(UTC))
        if run_mode in {"full", "readings"}:
            run_meter_submit_for_automation(db, automation=automation, now_utc=datetime.now(UTC))
    except Exception:
        db.refresh(automation)
        raise
    db.refresh(automation)
    return _automation_row_out(db, automation, apartment, _automation_service_name(db, automation=automation))


@router.post("/automations/run-cycle", response_model=AutomationCycleRunOut, dependencies=[Depends(require_write_access)])
def run_automation_cycle(db: Session = Depends(get_db)):
    from app.workers.tariff_auto_check import run_tariff_auto_checks

    result = run_tariff_auto_checks(db, trigger_mode="manual") or {}
    return AutomationCycleRunOut(
        id=int(result["id"]) if result.get("id") is not None else None,
        trigger_mode=str(result.get("trigger_mode") or "manual"),
        processed_accrual_automations=int(result.get("processed_accrual_automations", 0)),
        processed_submit_automations=int(result.get("processed_submit_automations", 0)),
        processed_legacy_settings=int(result.get("processed_legacy_settings", 0)),
        submitted_readings=int(result.get("submitted_readings", 0)),
        message=str(
            result.get("message")
            or (
                "Плановий цикл виконано: "
                f"accrual={int(result.get('processed_accrual_automations', 0))}, "
                f"submit={int(result.get('processed_submit_automations', 0))}, "
                f"submitted={int(result.get('submitted_readings', 0))}"
            )
        ),
        started_at=result.get("started_at"),
        finished_at=result.get("finished_at"),
    )


@router.get("/automations/cycle-runs", response_model=list[AutomationCycleRunOut])
def automation_cycle_runs(limit: int = 10, trigger_mode: str | None = None, db: Session = Depends(get_db)):
    safe_limit = max(1, min(limit, 50))
    query = select(AutomationCycleRun)
    if (trigger_mode or "").strip():
        query = query.where(AutomationCycleRun.trigger_mode == trigger_mode.strip().lower())
    rows = db.scalars(query.order_by(AutomationCycleRun.started_at.desc(), AutomationCycleRun.id.desc()).limit(safe_limit)).all()
    phase_rows = db.scalars(
        select(AutomationCyclePhaseRun)
        .where(AutomationCyclePhaseRun.cycle_run_id.in_([row.id for row in rows] or [-1]))
        .order_by(AutomationCyclePhaseRun.cycle_run_id.desc(), AutomationCyclePhaseRun.started_at.asc(), AutomationCyclePhaseRun.id.asc())
    ).all()
    phases_by_cycle: dict[int, list[AutomationCyclePhaseRunOut]] = {}
    for phase in phase_rows:
        phases_by_cycle.setdefault(phase.cycle_run_id, []).append(
            AutomationCyclePhaseRunOut(
                id=phase.id,
                phase=phase.phase,
                status=phase.status,
                processed_count=phase.processed_count,
                skipped_count=phase.skipped_count,
                submitted_readings=phase.submitted_readings,
                duration_ms=phase.duration_ms,
                message=phase.message,
                started_at=phase.started_at,
                finished_at=phase.finished_at,
            )
        )
    return [
        AutomationCycleRunOut(
            id=row.id,
            trigger_mode=row.trigger_mode,
            processed_accrual_automations=row.processed_accrual_automations,
            processed_submit_automations=row.processed_submit_automations,
            processed_legacy_settings=row.processed_legacy_settings,
            submitted_readings=row.submitted_readings,
            message=row.message or "Плановий цикл виконано",
            started_at=row.started_at,
            finished_at=row.finished_at,
            phases=phases_by_cycle.get(row.id, []),
        )
        for row in rows
    ]


@router.get("/automations/cycle-runs/{cycle_run_id}", response_model=AutomationCycleRunDetailOut)
def automation_cycle_run_detail(
    cycle_run_id: int,
    apartment_id: int | None = None,
    db: Session = Depends(get_db),
):
    cycle = db.get(AutomationCycleRun, cycle_run_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Automation cycle run not found.")
    phase_rows = db.scalars(
        select(AutomationCyclePhaseRun)
        .where(AutomationCyclePhaseRun.cycle_run_id == cycle_run_id)
        .order_by(AutomationCyclePhaseRun.started_at.asc(), AutomationCyclePhaseRun.id.asc())
    ).all()
    logs_query = (
        select(AutomationRunLog)
        .where(AutomationRunLog.started_at >= cycle.started_at)
        .where(AutomationRunLog.started_at <= (cycle.finished_at or cycle.started_at))
        .order_by(AutomationRunLog.started_at.desc(), AutomationRunLog.id.desc())
    )
    if apartment_id is not None:
        logs_query = logs_query.where(AutomationRunLog.apartment_id == apartment_id)
    logs = db.scalars(logs_query.limit(200)).all()
    apartment_map = {row.id: row.address for row in db.scalars(select(Apartment)).all()}
    return AutomationCycleRunDetailOut(
        id=cycle.id,
        trigger_mode=cycle.trigger_mode,
        message=cycle.message or "Плановий цикл виконано",
        started_at=cycle.started_at,
        finished_at=cycle.finished_at,
        phases=[
            AutomationCyclePhaseRunOut(
                id=phase.id,
                phase=phase.phase,
                status=phase.status,
                processed_count=phase.processed_count,
                skipped_count=phase.skipped_count,
                submitted_readings=phase.submitted_readings,
                duration_ms=phase.duration_ms,
                message=phase.message,
                started_at=phase.started_at,
                finished_at=phase.finished_at,
            )
            for phase in phase_rows
        ],
        logs=[
            AutomationCycleRunLogDetailOut(
                id=log.id,
                apartment_id=log.apartment_id,
                apartment_address=apartment_map.get(log.apartment_id, "—"),
                service_name=log.service_name,
                phase=_infer_cycle_log_phase(log),
                mode=log.mode,
                status=log.status,
                register_name=log.register_name,
                target_year=log.target_year,
                target_month=log.target_month,
                message=log.message,
                started_at=log.started_at,
                finished_at=log.finished_at,
            )
            for log in logs
        ],
    )


@router.get("/automations/run-cycle-preview", response_model=AutomationCyclePreviewOut)
def run_automation_cycle_preview(db: Session = Depends(get_db)):
    items: list[AutomationCyclePreviewItem] = []
    started_at = datetime.now(UTC)
    apartments = {a.id: a for a in db.scalars(select(Apartment)).all()}
    automations = db.scalars(
        select(ApartmentAutomation).order_by(ApartmentAutomation.apartment_id, ApartmentAutomation.id)
    ).all()
    for automation in automations:
        apartment = apartments.get(automation.apartment_id)
        if apartment is None:
            continue
        service_name = automation.template.name if automation.template else "Автоматизація"
        submit_next_at, submit_reason = _build_submit_meta(db, automation=automation, apartment=apartment)
        if automation.is_enabled and automation.accrual_enabled:
            reason_code, reason_text = _preview_reason(
                "accrual_ready" if not automation.accrual_completed_for_period else "accrual_completed",
                "Готово до планового accrual-запуску."
                if not automation.accrual_completed_for_period
                else "Accrual для поточного періоду вже завершено.",
            )
            items.append(
                AutomationCyclePreviewItem(
                    automation_id=automation.id,
                    apartment_id=automation.apartment_id,
                    apartment_address=apartment.address,
                    service_name=service_name,
                    phase="accrual",
                    action="run" if not automation.accrual_completed_for_period else "skip",
                    reason_code=reason_code,
                    reason=reason_text,
                )
            )
        if automation.submit_enabled:
            submit_code = "submit_ready"
            if submit_reason:
                low = submit_reason.casefold()
                if "вимк" in low:
                    submit_code = "submit_disabled"
                elif "бракує credentials" in low or "бракує" in low:
                    submit_code = "submit_missing_credentials"
                elif "поза вікном" in low:
                    submit_code = "submit_outside_window"
                elif "немає показника" in low:
                    submit_code = "submit_missing_reading"
                elif "вже передано" in low or "вже подано" in low:
                    submit_code = "submit_completed"
                elif "готово" in low:
                    submit_code = "submit_ready"
            items.append(
                AutomationCyclePreviewItem(
                    automation_id=automation.id,
                    apartment_id=automation.apartment_id,
                    apartment_address=apartment.address,
                    service_name=service_name,
                    phase="submit",
                    action="run" if (submit_reason or "").startswith("Готово") else "skip",
                    reason_code=submit_code,
                    reason=submit_reason or (f"Наступний submit: {submit_next_at.isoformat()}" if submit_next_at else "Невідомий стан submit."),
                )
            )
    processed_accrual = sum(1 for item in items if item.phase == "accrual" and item.action == "run")
    processed_submit = sum(1 for item in items if item.phase == "submit" and item.action == "run")
    processed_legacy = sum(1 for item in items if item.phase == "legacy" and item.action == "run")
    cycle_row = AutomationCycleRun(
        trigger_mode="dry-run",
        processed_accrual_automations=processed_accrual,
        processed_submit_automations=processed_submit,
        processed_legacy_settings=processed_legacy,
        submitted_readings=0,
        message=f"Dry-run: accrual={processed_accrual}, submit={processed_submit}, legacy={processed_legacy}"[:255],
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    db.add(cycle_row)
    db.flush()
    for phase_name in ("accrual", "submit", "legacy"):
        phase_items = [item for item in items if item.phase == phase_name]
        db.add(
            AutomationCyclePhaseRun(
                cycle_run_id=cycle_row.id,
                phase=phase_name,
                status="completed",
                processed_count=sum(1 for item in phase_items if item.action == "run"),
                skipped_count=sum(1 for item in phase_items if item.action != "run"),
                submitted_readings=0,
                duration_ms=max(int((datetime.now(UTC) - started_at).total_seconds() * 1000), 0),
                message=f"Dry-run {phase_name}: run={sum(1 for item in phase_items if item.action == 'run')}, skip={sum(1 for item in phase_items if item.action != 'run')}"[:255],
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        )
    db.commit()
    return AutomationCyclePreviewOut(
        items=items,
        message=f"Підготовлено {len(items)} записів preview планового циклу.",
    )


def _automation_row_out(db: Session, automation: ApartmentAutomation, apartment: Apartment, service_name: str) -> AutomationRowOut:
    submit_next_at, submit_state_reason = _build_submit_meta(db, automation=automation, apartment=apartment)
    return AutomationRowOut(
        automation_id=automation.id,
        template_id=automation.template_id,
        template_name=automation.template.name if automation.template else None,
        template_code=automation.template.code if automation.template else None,
        apartment_id=automation.apartment_id,
        apartment_code=apartment.code,
        apartment_address=apartment.address,
        service_name=service_name,
        provider_id=automation.provider_id,
        provider_name=automation.provider.name_full if automation.provider else (automation.template.provider.name_full if automation.template and automation.template.provider else None),
        provider_company=automation.provider.name_full if automation.provider else (automation.template.provider.name_full if automation.template and automation.template.provider else None),
        personal_account=automation.personal_account,
        cabinet_url=automation.cabinet_url,
        cabinet_login=automation.cabinet_login,
        cabinet_password=decrypt_text(automation.cabinet_password_encrypted),
        auto_check_enabled=automation.is_enabled and automation.accrual_enabled,
        auto_check_time=automation.accrual_time,
        auto_check_timezone=apartment.timezone or "Europe/Kyiv",
        auto_check_window_day_from=automation.accrual_window_day_from,
        auto_check_window_day_to=automation.accrual_window_day_to,
        auto_check_target_year=automation.auto_check_target_year,
        auto_check_target_month=automation.auto_check_target_month,
        auto_check_completed_for_period=automation.accrual_completed_for_period,
        auto_check_status=automation.auto_check_status,
        auto_check_message=automation.auto_check_message,
        auto_check_last_value_raw=None,
        auto_check_last_value_rounded=None,
        auto_check_last_checked_at=automation.auto_check_last_checked_at,
        auto_check_last_updated_at=automation.auto_check_last_updated_at,
        auto_check_next_at=automation.auto_check_next_at,
        submit_enabled=automation.submit_enabled and automation.is_enabled,
        submit_time=automation.submit_time,
        submit_window_day_from=automation.submit_window_day_from,
        submit_window_day_to=automation.submit_window_day_to,
        submit_target_year=automation.submit_target_year,
        submit_target_month=automation.submit_target_month,
        submit_completed_for_period=automation.submit_completed_for_period,
        submit_next_at=submit_next_at,
        submit_state_reason=submit_state_reason,
    )


def _apartment_automation_out(row: ApartmentAutomation, apartment: Apartment) -> ApartmentAutomationOut:
    submit_next_at, submit_state_reason = _build_submit_meta(None, automation=row, apartment=apartment)
    return ApartmentAutomationOut(
        id=row.id,
        apartment_id=row.apartment_id,
        apartment_address=apartment.address,
        apartment_timezone=apartment.timezone or "Europe/Kyiv",
        template_id=row.template_id,
        template_name=row.template.name if row.template else "—",
        template_code=row.template.code if row.template else "—",
        provider_id=row.provider_id,
        provider_name=row.provider.name_full if row.provider else (row.template.provider.name_full if row.template and row.template.provider else None),
        personal_account=row.personal_account,
        cabinet_url=row.cabinet_url,
        cabinet_login=row.cabinet_login,
        cabinet_password=decrypt_text(row.cabinet_password_encrypted),
        is_enabled=row.is_enabled,
        accrual_enabled=row.accrual_enabled,
        accrual_time=row.accrual_time,
        accrual_window_day_from=row.accrual_window_day_from,
        accrual_window_day_to=row.accrual_window_day_to,
        submit_enabled=row.submit_enabled,
        submit_time=row.submit_time,
        submit_window_day_from=row.submit_window_day_from,
        submit_window_day_to=row.submit_window_day_to,
        submit_target_year=row.submit_target_year,
        submit_target_month=row.submit_target_month,
        submit_completed_for_period=row.submit_completed_for_period,
        submit_next_at=submit_next_at,
        submit_state_reason=submit_state_reason,
        auto_check_status=row.auto_check_status,
        auto_check_message=row.auto_check_message,
        auto_check_last_checked_at=row.auto_check_last_checked_at,
        auto_check_last_updated_at=row.auto_check_last_updated_at,
        auto_check_next_at=row.auto_check_next_at,
    )


def _create_automation_log(
    db: Session,
    *,
    automation_id: int | None,
    apartment_id: int,
    service_name: str,
    register_name: str | None = None,
    target_year: int | None = None,
    target_month: int | None = None,
    mode: str,
) -> AutomationRunLog:
    row = AutomationRunLog(
        automation_id=automation_id,
        apartment_id=apartment_id,
        service_name=service_name,
        register_name=register_name,
        target_year=target_year,
        target_month=target_month,
        mode=mode,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


def _finish_automation_log(db: Session, row: AutomationRunLog, status: str, message: str | None) -> None:
    row.status = status or "unknown"
    row.message = (message or "")[:255] if message else None
    row.finished_at = datetime.now(UTC)


def _is_day_in_window(day: int, day_from: int, day_to: int) -> bool:
    if day_from <= day_to:
        return day_from <= day <= day_to
    return day >= day_from or day <= day_to


def _target_period_for_window(local_now: datetime, day_from: int, day_to: int) -> tuple[int, int]:
    if day_from > day_to:
        if local_now.day >= day_from:
            return local_now.year, local_now.month
        return _prev_month(local_now.year, local_now.month)
    return local_now.year, local_now.month


def _resolve_hhmm(value: str | None) -> tuple[int, int]:
    raw = (value or "").strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", raw):
        return 9, 0
    hh, mm = raw.split(":")
    return int(hh), int(mm)


def _next_window_run_at(local_now: datetime, hh: int, mm: int, day_from: int, day_to: int) -> datetime:
    planned_today = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if _is_day_in_window(local_now.day, day_from, day_to) and local_now < planned_today:
        return planned_today
    candidate = local_now + timedelta(days=1)
    for _ in range(62):
        if _is_day_in_window(candidate.day, day_from, day_to):
            return candidate.replace(hour=hh, minute=mm, second=0, microsecond=0)
        candidate += timedelta(days=1)
    return planned_today + timedelta(days=1)


def _connection_active_on(connection: ApartmentServiceConnection, target_date: date) -> bool:
    if connection.started_at and connection.started_at > target_date:
        return False
    if connection.ended_at and connection.ended_at < target_date:
        return False
    return (connection.status or "active").strip().lower() != "inactive"


def _charge_line_active_on(line: ConnectionChargeLine, target_date: date) -> bool:
    if not line.is_active:
        return False
    if line.effective_from and line.effective_from > target_date:
        return False
    if line.effective_to and line.effective_to < target_date:
        return False
    return True


def _automation_connections(
    db: Session,
    *,
    apartment_id: int,
    automation_id: int | None = None,
    provider_id: int | None = None,
    target_date: date | None = None,
) -> list[ApartmentServiceConnection]:
    query = select(ApartmentServiceConnection).where(ApartmentServiceConnection.apartment_id == apartment_id)
    if automation_id is not None:
        query = query.where(ApartmentServiceConnection.automation_id == automation_id)
    elif provider_id is not None:
        query = query.where(ApartmentServiceConnection.provider_id == provider_id)
    rows = db.scalars(query.order_by(ApartmentServiceConnection.id.asc())).all()
    if target_date is None:
        return rows
    return [row for row in rows if _connection_active_on(row, target_date)]


def _automation_service_name(
    db: Session,
    *,
    automation: ApartmentAutomation,
    target_date: date | None = None,
) -> str:
    connections = _automation_connections(
        db,
        apartment_id=automation.apartment_id,
        automation_id=automation.id,
        target_date=target_date,
    )
    service_names = sorted(
        {
            (connection.service_catalog.name or "").strip()
            for connection in connections
            if connection.service_catalog and (connection.service_catalog.name or "").strip()
        },
        key=lambda value: value.lower(),
    )
    if service_names:
        return ", ".join(service_names)
    if automation.template and (automation.template.name or "").strip():
        return automation.template.name.strip()
    if automation.provider and (automation.provider.name_full or "").strip():
        return automation.provider.name_full.strip()
    return "Автоматизація"


def _provider_meter_bindings(
    db: Session,
    *,
    apartment_id: int,
    provider_id: int | None,
    year: int,
    month: int,
) -> list[tuple[ApartmentServiceConnection, ConnectionChargeLine]]:
    if provider_id is None:
        return []
    target_date = date(year, month, 1)
    bindings: list[tuple[ApartmentServiceConnection, ConnectionChargeLine]] = []
    for connection in _automation_connections(
        db,
        apartment_id=apartment_id,
        provider_id=provider_id,
        target_date=target_date,
    ):
        charge_lines = db.scalars(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == connection.id)
            .where(ConnectionChargeLine.meter_id.is_not(None))
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        ).all()
        for line in charge_lines:
            if line.meter_id is None or not _charge_line_active_on(line, target_date):
                continue
            bindings.append((connection, line))
    return bindings


def _has_submit_reading_for_period(
    db: Session,
    *,
    apartment_id: int,
    provider_id: int | None,
    year: int,
    month: int,
) -> bool:
    if provider_id is None:
        return False
    for _, line in _provider_meter_bindings(
        db,
        apartment_id=apartment_id,
        provider_id=provider_id,
        year=year,
        month=month,
    ):
        if line.meter_id is None:
            continue
        reading = db.scalar(
            select(MeterReading.id)
            .where(MeterReading.meter_id == line.meter_id)
            .where(MeterReading.register_name == (line.meter_register or "total"))
            .where(MeterReading.year == year)
            .where(MeterReading.month == month)
            .limit(1)
        )
        if reading is not None:
            return True
    return False


def _resolve_submit_meter_bindings(
    db: Session,
    *,
    apartment_id: int,
    service_names: list[str] | set[str],
    year: int,
    month: int,
) -> dict[str, tuple[int, str]]:
    wanted = [name for name in service_names if (name or "").strip()]
    if not wanted:
        return {}
    bindings: dict[str, tuple[int, str]] = {}
    target_date = date(year, month, 1)
    connections = db.scalars(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .where(ApartmentServiceConnection.started_at <= target_date)
        .where((ApartmentServiceConnection.ended_at.is_(None)) | (ApartmentServiceConnection.ended_at >= target_date))
        .where(ApartmentServiceConnection.status == "active")
        .order_by(ApartmentServiceConnection.id.asc())
    ).all()
    wanted_set = {name.strip() for name in wanted}
    for connection in connections:
        if connection.service_catalog is None or connection.service_catalog.name not in wanted_set:
            continue
        charge_lines = db.scalars(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == connection.id)
            .where(ConnectionChargeLine.meter_id.is_not(None))
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        ).all()
        for line in charge_lines:
            if line.meter_id is None or not _charge_line_active_on(line, target_date):
                continue
            bindings.setdefault(connection.service_catalog.name, (line.meter_id, line.meter_register or "total"))
            break
    return bindings


def _build_submit_meta(
    db: Session | None,
    *,
    automation: ApartmentAutomation,
    apartment: Apartment,
) -> tuple[datetime | None, str | None]:
    if not automation.is_enabled or not automation.submit_enabled:
        return None, "Подача показників вимкнена."
    if not (automation.cabinet_url or "").strip() or not (automation.cabinet_login or "").strip() or not decrypt_text(automation.cabinet_password_encrypted):
        return None, "Бракує credentials кабінету."
    timezone_name = apartment.timezone or "Europe/Kyiv"
    try:
        from zoneinfo import ZoneInfo

        local_now = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        local_now = datetime.now()
    day_from = automation.submit_window_day_from or 28
    day_to = automation.submit_window_day_to or 3
    hh, mm = _resolve_hhmm(automation.submit_time)
    next_submit_local = _next_window_run_at(local_now, hh, mm, day_from, day_to)
    target_year, target_month = _target_period_for_window(local_now, day_from, day_to)
    if automation.submit_completed_for_period and automation.submit_target_year == target_year and automation.submit_target_month == target_month:
        return next_submit_local.astimezone(UTC), "Показник за поточний період уже передано."
    if not _is_day_in_window(local_now.day, day_from, day_to):
        return next_submit_local.astimezone(UTC), "Поточна дата поза вікном подачі."
    if db is None:
        return next_submit_local.astimezone(UTC), "Стан показника буде уточнено після наступної перевірки."
    has_reading = _has_submit_reading_for_period(
        db,
        apartment_id=automation.apartment_id,
        provider_id=automation.provider_id,
        year=target_year,
        month=target_month,
    )
    if not has_reading:
        return next_submit_local.astimezone(UTC), f"Немає показника в БД за {target_month:02d}.{target_year}."
    return next_submit_local.astimezone(UTC), "Готово до подачі при наступному submit-запуску."


@router.get("/automations/meter-submit/evaluate", response_model=MeterSubmitEvaluateOut)
def evaluate_meter_submit(
    apartment_id: int,
    meter_id: int,
    register_name: str,
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    register_name = (register_name or "total").strip() or "total"
    target_date = date(year, month, 1)
    matching_connections: list[ApartmentServiceConnection] = []
    for connection in _automation_connections(db, apartment_id=apartment_id, target_date=target_date):
        charge_lines = db.scalars(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == connection.id)
            .where(ConnectionChargeLine.meter_id == meter_id)
            .where(ConnectionChargeLine.meter_register == register_name)
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        ).all()
        if any(_charge_line_active_on(line, target_date) for line in charge_lines):
            matching_connections.append(connection)
    if not matching_connections:
        meter = db.get(Meter, meter_id)
        if meter is None or meter.apartment_id != apartment_id:
            return MeterSubmitEvaluateOut(can_submit=False, reason="Лічильник не знайдено для цього об'єкта.")
        return MeterSubmitEvaluateOut(
            can_submit=False,
            reason="Для цього показника немає підключеної послуги з прив'язкою до лічильника.",
        )
    automation_ids = {connection.automation_id for connection in matching_connections if connection.automation_id is not None}
    provider_ids = {connection.provider_id for connection in matching_connections if connection.provider_id is not None}
    if not automation_ids and not provider_ids:
        return MeterSubmitEvaluateOut(can_submit=False, reason="Для тарифу не вказано постачальника з automation.")

    automations = db.scalars(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .where(ApartmentAutomation.is_enabled == True)  # noqa: E712
        .where(ApartmentAutomation.submit_enabled == True)  # noqa: E712
        .order_by(ApartmentAutomation.id.desc())
    ).all()
    automations = [
        automation
        for automation in automations
        if automation.id in automation_ids or (automation.provider_id is not None and automation.provider_id in provider_ids)
    ]
    if not automations:
        return MeterSubmitEvaluateOut(can_submit=False, reason="Для постачальника не підключено automation подачі показників.")

    tz = apartment.timezone or "Europe/Kyiv"
    local_now = datetime.now()
    try:
        from zoneinfo import ZoneInfo

        local_now = datetime.now(ZoneInfo(tz))
    except Exception:
        pass

    for automation in automations:
        if not _is_day_in_window(local_now.day, automation.submit_window_day_from, automation.submit_window_day_to):
            continue
        target_year, target_month = _target_period_for_window(
            local_now,
            automation.submit_window_day_from,
            automation.submit_window_day_to,
        )
        if year != target_year or month != target_month:
            continue
        if automation.submit_target_year != target_year or automation.submit_target_month != target_month:
            automation.submit_target_year = target_year
            automation.submit_target_month = target_month
            automation.submit_completed_for_period = False
            db.add(automation)
            db.commit()
            db.refresh(automation)
        if automation.submit_completed_for_period:
            return MeterSubmitEvaluateOut(
                can_submit=False,
                reason="Показник для поточного періоду вже передано раніше.",
                automation_id=automation.id,
                template_name=automation.template.name if automation.template else None,
                target_year=target_year,
                target_month=target_month,
            )
        return MeterSubmitEvaluateOut(
            can_submit=True,
            reason="Показник відповідає поточному періоду та вікну подачі.",
            automation_id=automation.id,
            template_name=automation.template.name if automation.template else None,
            target_year=target_year,
            target_month=target_month,
        )

    return MeterSubmitEvaluateOut(
        can_submit=False,
        reason="Показник не входить у поточне вікно подачі або це не поточний період.",
    )


@router.post("/automations/meter-submit/dispatch", response_model=MeterSubmitDispatchOut, dependencies=[Depends(require_write_access)])
def dispatch_meter_submit(payload: MeterSubmitDispatchRequest, db: Session = Depends(get_db)):
    # Local import avoids module cycle.
    from app.workers.tariff_auto_check import run_meter_submit_for_automation

    check = evaluate_meter_submit(
        apartment_id=payload.apartment_id,
        meter_id=payload.meter_id,
        register_name=payload.register_name,
        year=payload.year,
        month=payload.month,
        db=db,
    )
    if not check.can_submit:
        return MeterSubmitDispatchOut(dispatched=False, message=check.reason)
    if check.automation_id is None:
        return MeterSubmitDispatchOut(dispatched=False, message="Automation не знайдено.")

    automation = db.get(ApartmentAutomation, check.automation_id)
    if automation is None:
        return MeterSubmitDispatchOut(dispatched=False, message="Automation недоступна для відправки.")
    try:
        dispatched = run_meter_submit_for_automation(db, automation=automation, now_utc=datetime.now(UTC))
    except Exception as error:
        return MeterSubmitDispatchOut(dispatched=False, message=f"Помилка запуску: {error}")
    db.refresh(automation)
    if dispatched:
        return MeterSubmitDispatchOut(dispatched=True, message="Automation подачі показника запущена.")
    return MeterSubmitDispatchOut(
        dispatched=False,
        message=automation.auto_check_message or "Automation не виконала подачу показника.",
    )


@router.get("/dashboard/apartments/{apartment_id}/missing-services", response_model=list[MissingServiceOut])
def missing_services(apartment_id: int, year: int, month: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    target_period = date(year, month, 1)
    connections = db.scalars(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .where(ApartmentServiceConnection.started_at <= target_period)
        .where((ApartmentServiceConnection.ended_at.is_(None)) | (ApartmentServiceConnection.ended_at >= target_period))
        .where(ApartmentServiceConnection.status == "active")
    ).all()
    invoice = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == apartment_id, Invoice.year == year, Invoice.month == month)
        )
    )
    used = {item.service_name for item in invoice.items} if invoice else set()
    rows: list[MissingServiceOut] = []
    for connection in connections:
        if connection.service_catalog is None:
            continue
        active_lines = [
            line
            for line in connection.charge_lines
            if line.is_active and line.effective_from <= target_period and (line.effective_to is None or line.effective_to >= target_period)
        ]
        if not active_lines:
            continue
        service_name = connection.service_catalog.name
        if service_name in used:
            continue
        first_line = sorted(active_lines, key=lambda line: (line.effective_from, line.id))[0]
        charge_mode = ChargeMode.metered if first_line.line_kind == ChargeLineKind.meter_register else ChargeMode.fixed
        rows.append(MissingServiceOut(service_name=service_name, charge_mode=charge_mode, unit_name=first_line.unit_name))
    return sorted(rows, key=lambda x: x.service_name.lower())


@router.post("/owner-charges", response_model=OwnerChargeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_owner_charge(
    payload: OwnerChargeCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    row = OwnerCharge(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    _log_billing_change(
        db,
        apartment_id=row.apartment_id,
        year=row.year,
        month=row.month,
        actor_username=user.username,
        action="owner_charge_created",
        entity_type="owner_charge",
        entity_id=row.id,
        service_name=row.category,
        details={"kind": row.kind.value, "amount": str(row.amount), "description": row.description},
    )
    db.commit()
    return row


@router.put("/owner-charges/{owner_charge_id}", response_model=OwnerChargeOut, dependencies=[Depends(require_write_access)])
def update_owner_charge(
    owner_charge_id: int,
    payload: OwnerChargeUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    row = db.get(OwnerCharge, owner_charge_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Owner charge not found.")
    old_amount = Decimal(row.amount)
    old_year = row.year
    old_month = row.month
    old_kind = row.kind
    old_category = row.category
    old_description = row.description
    row.year = payload.year
    row.month = payload.month
    row.kind = payload.kind
    row.category = payload.category
    row.description = payload.description
    row.amount = payload.amount
    row.currency = payload.currency
    row.event_date = payload.event_date
    db.commit()
    db.refresh(row)
    _log_billing_change(
        db,
        apartment_id=row.apartment_id,
        year=row.year,
        month=row.month,
        actor_username=user.username,
        action="owner_charge_updated",
        entity_type="owner_charge",
        entity_id=row.id,
        service_name=row.category,
        details={
            "old_period": f"{old_year}-{old_month:02d}",
            "new_period": f"{row.year}-{row.month:02d}",
            "old_kind": old_kind.value,
            "new_kind": row.kind.value,
            "old_category": old_category,
            "new_category": row.category,
            "old_description": old_description,
            "new_description": row.description,
            "old_amount": str(old_amount),
            "new_amount": str(row.amount),
        },
    )
    db.commit()
    return row


@router.delete("/owner-charges/{owner_charge_id}", dependencies=[Depends(require_write_access)])
def delete_owner_charge(
    owner_charge_id: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    row = db.get(OwnerCharge, owner_charge_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Owner charge not found.")
    apartment_id = row.apartment_id
    year = row.year
    month = row.month
    kind = row.kind
    category = row.category
    amount = Decimal(row.amount)
    db.delete(row)
    db.commit()
    _log_billing_change(
        db,
        apartment_id=apartment_id,
        year=year,
        month=month,
        actor_username=user.username,
        action="owner_charge_deleted",
        entity_type="owner_charge",
        entity_id=owner_charge_id,
        service_name=category,
        details={"kind": kind.value, "amount": str(amount)},
    )
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/owner-charges", response_model=list[OwnerChargeOut])
def list_owner_charges(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows = db.scalars(
        select(OwnerCharge).where(OwnerCharge.apartment_id == apartment_id).order_by(OwnerCharge.year.desc(), OwnerCharge.month.desc())
    ).all()
    return rows


@router.post("/maintenance", response_model=MaintenanceRecordOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_maintenance_record(payload: MaintenanceRecordCreate, db: Session = Depends(get_db)):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    row = MaintenanceRecord(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/maintenance/{maintenance_id}", response_model=MaintenanceRecordOut, dependencies=[Depends(require_write_access)])
def update_maintenance_record(maintenance_id: int, payload: MaintenanceRecordUpdate, db: Session = Depends(get_db)):
    row = db.get(MaintenanceRecord, maintenance_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    row.maintenance_type = payload.maintenance_type
    row.title = payload.title
    row.description = payload.description
    row.contractor = payload.contractor
    row.amount = payload.amount
    row.currency = payload.currency
    row.scheduled_for = payload.scheduled_for
    row.performed_at = payload.performed_at
    row.next_service_at = payload.next_service_at
    row.note = payload.note
    db.commit()
    db.refresh(row)
    return row


@router.delete("/maintenance/{maintenance_id}", dependencies=[Depends(require_write_access)])
def delete_maintenance_record(maintenance_id: int, db: Session = Depends(get_db)):
    row = db.get(MaintenanceRecord, maintenance_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/maintenance", response_model=list[MaintenanceRecordOut])
def list_maintenance_records(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows = db.scalars(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.apartment_id == apartment_id)
        .order_by(MaintenanceRecord.performed_at.desc(), MaintenanceRecord.scheduled_for.desc())
    ).all()
    return rows


@router.put("/apartments/{apartment_id}/tariffs/settings", response_model=ApartmentTariffRowOut, dependencies=[Depends(require_write_access)])
def upsert_apartment_tariff_setting(apartment_id: int, payload: TariffSettingUpsert, db: Session = Depends(get_db)):
    _legacy_api_disabled("PUT /admin/apartments/{apartment_id}/tariffs/settings")
    raise AssertionError("unreachable")
