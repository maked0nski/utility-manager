# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import UTC, date, datetime
from calendar import monthrange
from decimal import Decimal
import json
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_admin
from app.models import (
    Apartment,
    ApartmentServiceConnection,
    AutomationRunLog,
    BillingChangeLog,
    BillingLock,
    BillingMonthSnapshot,
    BillingStatement,
    BillingStatementStatus,
    ChargeLineKind,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    ConnectionChargeLine,
    Meter,
    MeterType,
    MeterReading,
    OwnerCharge,
    OwnerChargeKind,
    RentCurrency,
    ServiceLedgerEntry,
    Tenancy,
    Tenant,
    UnitType,
    UtilityPayment,
    UtilityType,
)
from app.schemas import (
    ApartmentCreate,
    ApartmentServiceConnectionOut,
    BillingMonthSnapshotOut,
    BillingStatementOut,
    CalculationRowOut,
    ConnectionChargeLineOut,
    MeterOut,
    TenantOut,
)
from app.services.billing import build_connection_charge_rows

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
                cabinet_price_per_unit=line.cabinet_price_per_unit,
                cabinet_checked_at=line.cabinet_checked_at,
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
    apartment.cabinet_markup_percent = payload.cabinet_markup_percent
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


def _recalc_from_period(db: Session, apartment_id: int, start_year: int, start_month: int) -> list[tuple[int, int]]:
    invoices = _invoice_periods_from(db, apartment_id, start_year, start_month)
    if not invoices:
        return []

    previous_invoice = db.scalar(
        select(Invoice)
        .where(Invoice.apartment_id == apartment_id)
        .where(
            or_(
                Invoice.year < start_year,
                and_(Invoice.year == start_year, Invoice.month < start_month),
            )
        )
        .order_by(Invoice.year.desc(), Invoice.month.desc(), Invoice.id.desc())
        .limit(1)
    )
    carry = Decimal(previous_invoice.closing_balance).quantize(Decimal("0.01")) if previous_invoice else Decimal("0.00")
    recalculated_periods: list[tuple[int, int]] = []
    for inv in invoices:
        _sync_invoice_payment_totals(db, apartment_id, inv.year, inv.month)
        _recalc_invoice(db, inv, carry)
        carry = Decimal(inv.closing_balance)
        recalculated_periods.append((inv.year, inv.month))
    db.commit()
    return recalculated_periods


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


def _month_start_end(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _period_label(year: int, month: int) -> str:
    return f"{month:02d}.{year}"


def _future_locked_periods(
    db: Session,
    apartment_id: int,
    year: int,
    month: int,
) -> list[BillingLock]:
    target_key = _month_key(year, month)
    locks = db.scalars(
        select(BillingLock)
        .where(BillingLock.apartment_id == apartment_id)
        .order_by(BillingLock.year.asc(), BillingLock.month.asc(), BillingLock.id.asc())
    ).all()
    return [row for row in locks if _month_key(row.year, row.month) > target_key]


def _invoice_periods_from(
    db: Session,
    apartment_id: int,
    start_year: int,
    start_month: int,
) -> list[Invoice]:
    start_key = _month_key(start_year, start_month)
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.apartment_id == apartment_id)
        .order_by(Invoice.year.asc(), Invoice.month.asc(), Invoice.id.asc())
    ).all()
    return [invoice for invoice in invoices if _month_key(invoice.year, invoice.month) >= start_key]


def _mark_snapshot_reopened(
    snapshot: BillingMonthSnapshot | None,
    *,
    reopened_by: str,
    reason: str,
) -> None:
    if snapshot is None:
        return
    snapshot.status = "reopened"
    snapshot.reopened_at = datetime.now(UTC)
    snapshot.reopened_by = reopened_by
    snapshot.reopen_reason = reason


def _serialize_calc_row(row: CalculationRowOut) -> dict:
    payload = row.model_dump()
    for key, value in list(payload.items()):
        if isinstance(value, Decimal):
            payload[key] = str(value)
    return payload


def _deserialize_calc_rows(rows_json: str | None) -> list[CalculationRowOut]:
    if not rows_json:
        return []
    try:
        raw = json.loads(rows_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    rows: list[CalculationRowOut] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(CalculationRowOut(**item))
        except Exception:
            continue
    return rows


def _snapshot_out(snapshot: BillingMonthSnapshot | None) -> BillingMonthSnapshotOut | None:
    if snapshot is None:
        return None
    return BillingMonthSnapshotOut(
        id=snapshot.id,
        apartment_id=snapshot.apartment_id,
        year=snapshot.year,
        month=snapshot.month,
        status=snapshot.status,
        opening_balance=Decimal(snapshot.opening_balance),
        utility_accrual=Decimal(snapshot.utility_accrual),
        compensation_total=Decimal(snapshot.compensation_total),
        month_total=Decimal(snapshot.month_total),
        payments_in_month=Decimal(snapshot.payments_in_month),
        closing_balance=Decimal(snapshot.closing_balance),
        confirmed_at=snapshot.confirmed_at,
        confirmed_by=snapshot.confirmed_by,
        reopened_at=snapshot.reopened_at,
        reopened_by=snapshot.reopened_by,
        reopen_reason=snapshot.reopen_reason,
        rows=_deserialize_calc_rows(snapshot.rows_json),
    )


def _statement_out(statement: BillingStatement | None) -> BillingStatementOut | None:
    if statement is None:
        return None
    payload_rows = []
    if statement.payload_json:
        try:
            parsed = json.loads(statement.payload_json)
            payload_rows = parsed.get("rows", []) if isinstance(parsed, dict) else []
        except json.JSONDecodeError:
            payload_rows = []
    rows: list[CalculationRowOut] = []
    for item in payload_rows:
        if isinstance(item, dict):
            try:
                rows.append(CalculationRowOut(**item))
            except Exception:
                continue
    return BillingStatementOut(
        id=statement.id,
        apartment_id=statement.apartment_id,
        snapshot_id=statement.snapshot_id,
        year=statement.year,
        month=statement.month,
        version=statement.version,
        status=statement.status,
        generated_at=statement.generated_at,
        generated_by=statement.generated_by,
        sent_at=statement.sent_at,
        sent_channel=statement.sent_channel,
        sent_to=statement.sent_to,
        month_closing_balance_snapshot=Decimal(statement.month_closing_balance_snapshot),
        payments_after_month_to_generated_at=Decimal(statement.payments_after_month_to_generated_at),
        balance_due_on_generated_at=Decimal(statement.balance_due_on_generated_at),
        note=statement.note,
        rows=rows,
    )


def _build_month_snapshot(
    db: Session,
    apartment_id: int,
    year: int,
    month: int,
    *,
    confirmed_by: str | None = None,
) -> BillingMonthSnapshot:
    snapshot = db.scalar(
        select(BillingMonthSnapshot).where(
            BillingMonthSnapshot.apartment_id == apartment_id,
            BillingMonthSnapshot.year == year,
            BillingMonthSnapshot.month == month,
        )
    )
    invoice = db.scalar(select(Invoice).where(and_(Invoice.apartment_id == apartment_id, Invoice.year == year, Invoice.month == month)))
    rows = _build_period_rows(db, apartment_id, year, month, invoice)
    opening_balance = _confirmed_previous_utility_debt(db, apartment_id, year, month)
    utility_accrual = sum(
        (Decimal(row.amount) for row in rows if not row.service_name.startswith("Відшкодування:")),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    compensation_total = (
        sum(
            (abs(Decimal(row.amount)) for row in rows if row.service_name.startswith("Відшкодування:")),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
    )
    month_total = (utility_accrual - compensation_total).quantize(Decimal("0.01"))
    payments_in_month = _payments_sum_by_received_month(db, apartment_id, year, month)
    closing_balance = (opening_balance + month_total - payments_in_month).quantize(Decimal("0.01"))
    rows_json = json.dumps([_serialize_calc_row(row) for row in rows], ensure_ascii=False)

    if snapshot is None:
        snapshot = BillingMonthSnapshot(
            apartment_id=apartment_id,
            year=year,
            month=month,
        )
        db.add(snapshot)

    snapshot.status = "confirmed"
    snapshot.opening_balance = opening_balance
    snapshot.utility_accrual = utility_accrual
    snapshot.compensation_total = compensation_total
    snapshot.month_total = month_total
    snapshot.payments_in_month = payments_in_month
    snapshot.closing_balance = closing_balance
    snapshot.rows_json = rows_json
    snapshot.confirmed_at = datetime.now(UTC)
    snapshot.confirmed_by = confirmed_by
    snapshot.reopened_at = None
    snapshot.reopened_by = None
    snapshot.reopen_reason = None
    return snapshot


def _payments_after_month_until(
    db: Session,
    apartment_id: int,
    year: int,
    month: int,
    generated_at: datetime,
) -> tuple[Decimal, UtilityPayment | None]:
    _, month_end = _month_start_end(year, month)
    rows = db.scalars(
        select(UtilityPayment)
        .where(UtilityPayment.apartment_id == apartment_id)
        .where(UtilityPayment.paid_at > month_end)
        .where(UtilityPayment.paid_at <= generated_at.date())
        .order_by(UtilityPayment.paid_at.asc(), UtilityPayment.id.asc())
    ).all()
    total = sum((Decimal(row.amount) for row in rows), Decimal("0.00")).quantize(Decimal("0.01"))
    latest = rows[-1] if rows else None
    return total, latest


def _prepare_billing_statement(
    db: Session,
    apartment_id: int,
    year: int,
    month: int,
    *,
    generated_by: str | None = None,
    generated_at: datetime | None = None,
    note: str | None = None,
) -> BillingStatement:
    snapshot = db.scalar(
        select(BillingMonthSnapshot).where(
            BillingMonthSnapshot.apartment_id == apartment_id,
            BillingMonthSnapshot.year == year,
            BillingMonthSnapshot.month == month,
        )
    )
    if snapshot is None and _is_month_locked(db, apartment_id, year, month):
        snapshot = _build_month_snapshot(
            db,
            apartment_id,
            year,
            month,
            confirmed_by=generated_by,
        )
        db.flush()
    if snapshot is None or snapshot.status != "confirmed":
        raise HTTPException(status_code=409, detail="Місяць ще не підтверджено.")
    generated_at = generated_at or datetime.now(UTC)
    payments_after, _ = _payments_after_month_until(db, apartment_id, year, month, generated_at)
    latest_version = db.scalar(
        select(BillingStatement.version)
        .where(BillingStatement.snapshot_id == snapshot.id)
        .order_by(BillingStatement.version.desc())
        .limit(1)
    )
    next_version = (latest_version or 0) + 1
    statement = BillingStatement(
        apartment_id=apartment_id,
        snapshot_id=snapshot.id,
        year=year,
        month=month,
        version=next_version,
        status=BillingStatementStatus.prepared,
        generated_at=generated_at,
        generated_by=generated_by,
        month_closing_balance_snapshot=Decimal(snapshot.closing_balance),
        payments_after_month_to_generated_at=payments_after,
        balance_due_on_generated_at=(Decimal(snapshot.closing_balance) - payments_after).quantize(Decimal("0.01")),
        payload_json=json.dumps({"rows": [_serialize_calc_row(row) for row in _deserialize_calc_rows(snapshot.rows_json)]}, ensure_ascii=False),
        note=note,
    )
    db.add(statement)
    return statement


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


