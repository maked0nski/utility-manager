from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, require_authenticated_admin, require_write_access
from app.core.config import settings
from app.core.security import decrypt_text, encrypt_text
from app.db.session import get_db
from app.models import (
    AdminUser,
    Apartment,
    ApartmentService,
    ApartmentTariffSetting,
    BillingChangeLog,
    BillingLock,
    ChargeMode,
    ContractExtensionType,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Meter,
    MeterReading,
    MaintenanceRecord,
    OwnerCharge,
    OwnerChargeKind,
    RentLedger,
    RentCurrency,
    RentalContract,
    ServiceLedgerEntry,
    Tariff,
    Tenancy,
    Tenant,
    TenantContact,
    TenantPhone,
    UnitType,
    UtilityPayment,
)
from app.schemas import (
    ApartmentCreate,
    ApartmentDetailOut,
    ApartmentOverviewOut,
    ApartmentOut,
    ApartmentTariffRowOut,
    BalanceExplainOut,
    BillingChangeLogOut,
    BillingGenerateRequest,
    BillingLockRequest,
    BillingRecalculateRequest,
    CalculationRowOut,
    MaintenanceRecordCreate,
    MaintenanceRecordOut,
    MaintenanceRecordUpdate,
    MeterPeriodRowOut,
    MeterInitialReadingUpdate,
    MissingServiceOut,
    InvoiceOut,
    MeterCreate,
    MeterUpdate,
    MeterOut,
    OwnerChargeCreate,
    OwnerChargeOut,
    OwnerChargeUpdate,
    ReadingCreate,
    ReadingOut,
    RentMonthOut,
    RentRecordUpsert,
    TariffCreate,
    TariffOut,
    TariffSettingUpsert,
    TariffApplyFromPeriod,
    TariffBindingUpdate,
    TariffUpdate,
    ServiceActivationUpdate,
    ServiceLedgerRowOut,
    ServiceLedgerUpsert,
    TenancyOut,
    TenantBasicOut,
    TenantCreate,
    TenantOut,
    TenantUpdate,
    TenancyCreate,
    UtilityPaymentCreate,
)
from app.services.billing import generate_invoice

router = APIRouter(dependencies=[Depends(require_authenticated_admin)])

STORAGE_ROOT = Path("storage")
TENANT_PHOTO_DIR = STORAGE_ROOT / "tenant_photos"
CONTRACT_SCAN_DIR = STORAGE_ROOT / "contracts"
TENANT_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
CONTRACT_SCAN_DIR.mkdir(parents=True, exist_ok=True)


def _month_key(year: int, month: int) -> int:
    return year * 100 + month


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


def _prev_month(y: int, m: int) -> tuple[int, int]:
    if m == 1:
        return y - 1, 12
    return y, m - 1


def _next_month(y: int, m: int) -> tuple[int, int]:
    if m == 12:
        return y + 1, 1
    return y, m + 1


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
    locks = db.scalars(select(BillingLock).where(BillingLock.apartment_id == apartment_id)).all()
    locked_keys = {(row.year, row.month) for row in locks}
    invoices = db.scalars(select(Invoice).where(Invoice.apartment_id == apartment_id)).all()
    invoice_map = {(inv.year, inv.month): inv for inv in invoices}
    payments = db.scalars(select(UtilityPayment).where(UtilityPayment.apartment_id == apartment_id)).all()
    payment_map: dict[tuple[int, int], Decimal] = {}
    for p in payments:
        key = (p.year, p.month)
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
        if (y, m) in locked_keys:
            carry = current
        y, m = _next_month(y, m)

    return Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")


def _active_tenancy(db: Session, apartment_id: int, on_date: date) -> Tenancy | None:
    tenancies = db.scalars(select(Tenancy).where(Tenancy.apartment_id == apartment_id)).all()
    for tenancy in tenancies:
        if tenancy.start_date <= on_date and (tenancy.end_date is None or tenancy.end_date >= on_date):
            return tenancy
    return None


def _ensure_apartment_service(db: Session, apartment_id: int, service_name: str, active_from: date) -> ApartmentService:
    row = db.scalar(
        select(ApartmentService).where(
            and_(
                ApartmentService.apartment_id == apartment_id,
                ApartmentService.service_name == service_name,
            )
        )
    )
    if row is None:
        row = ApartmentService(
            apartment_id=apartment_id,
            service_name=service_name,
            active_from=active_from,
        )
        db.add(row)
        db.flush()
    elif active_from < row.active_from:
        row.active_from = active_from
    return row


def _service_active_for_period(service: ApartmentService | None, year: int, month: int) -> bool:
    if service is None:
        return True
    period_start = date(year, month, 1)
    if service.active_from > period_start:
        return False
    if service.inactive_from is not None and service.inactive_from <= period_start:
        return False
    return True


def _resolve_tariff(db: Session, apartment_id: int, service_name: str, year: int, month: int) -> Tariff | None:
    return db.scalar(
        select(Tariff)
        .where(Tariff.apartment_id == apartment_id)
        .where(Tariff.service_name == service_name)
        .where(Tariff.effective_from <= date(year, month, 1))
        .order_by(Tariff.effective_from.desc())
    )


def _prev_reading(
    db: Session,
    meter_id: int,
    register_name: str,
    year: int,
    month: int,
    initial: Decimal,
) -> Decimal:
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
    rows: list[CalculationRowOut] = []
    meter_by_service = {m.service_name: m for m in db.scalars(select(Meter).where(Meter.apartment_id == apartment_id)).all()}
    active_services = db.scalars(select(ApartmentService).where(ApartmentService.apartment_id == apartment_id)).all()
    active_map = {s.service_name: s for s in active_services}
    period_start = date(year, month, 1)
    tariffs = db.scalars(
        select(Tariff)
        .where(Tariff.apartment_id == apartment_id)
        .where(Tariff.effective_from <= period_start)
        .order_by(Tariff.service_name, Tariff.effective_from.desc())
    ).all()
    latest_tariff_by_service: dict[str, Tariff] = {}
    for tariff in tariffs:
        if not _service_active_for_period(active_map.get(tariff.service_name), year, month):
            continue
        latest_tariff_by_service.setdefault(tariff.service_name, tariff)

    item_map = {item.service_name: item for item in (invoice.items if invoice else [])}
    rendered: dict[str, CalculationRowOut] = {}
    pending_source: list[tuple[str, Tariff]] = []

    def _resolve_meter(t: Tariff) -> Meter | None:
        if t.meter_id:
            meter = db.get(Meter, t.meter_id)
            if meter is not None and meter.apartment_id == apartment_id:
                return meter
        return meter_by_service.get(t.service_name)

    for service_name, tariff in sorted(latest_tariff_by_service.items(), key=lambda x: x[0].lower()):
        if tariff.charge_mode == ChargeMode.metered and tariff.source_service_name:
            pending_source.append((service_name, tariff))
            continue

        meter = _resolve_meter(tariff)
        register_name = tariff.meter_register or "total"
        previous = None
        current = None
        can_edit_previous = False
        if meter:
            previous = _prev_reading(db, meter.id, register_name, year, month, Decimal(meter.initial_reading))
            curr = db.scalar(
                select(MeterReading).where(
                    and_(
                        MeterReading.meter_id == meter.id,
                        MeterReading.register_name == register_name,
                        MeterReading.year == year,
                        MeterReading.month == month,
                    )
                )
            )
            current = Decimal(curr.value) if curr else None
            previous_real_rows = db.scalars(
                select(MeterReading)
                .where(MeterReading.meter_id == meter.id)
                .where(MeterReading.register_name == register_name)
                .where((MeterReading.year * 100 + MeterReading.month) < _month_key(year, month))
            ).all()
            can_edit_previous = len(previous_real_rows) == 0

        item = item_map.get(service_name)
        if item is not None:
            difference = item.consumption
            unit_price = item.unit_price
            amount = item.amount
        else:
            if tariff.charge_mode == ChargeMode.fixed:
                difference = Decimal("1.000")
                unit_price = Decimal(tariff.price_per_unit)
                amount = Decimal(tariff.price_per_unit).quantize(Decimal("0.01"))
            else:
                if current is None or previous is None:
                    difference = None
                    amount = Decimal("0.00")
                else:
                    difference = (current - previous).quantize(Decimal("0.001"))
                    amount = (difference * Decimal(tariff.price_per_unit)).quantize(Decimal("0.01"))
                unit_price = Decimal(tariff.price_per_unit)

        row = CalculationRowOut(
            meter_id=meter.id if meter else None,
            service_name=service_name,
            meter_register=register_name,
            previous_reading=previous,
            current_reading=current,
            difference=difference,
            unit_name=tariff.unit_name,
            unit_price=unit_price,
            amount=amount,
            can_edit_previous=can_edit_previous,
        )
        rows.append(row)
        rendered[service_name] = row

    for service_name, tariff in pending_source:
        item = item_map.get(service_name)
        source_row = rendered.get(tariff.source_service_name or "")
        if item is not None:
            difference = item.consumption
            unit_price = item.unit_price
            amount = item.amount
        else:
            if source_row is None or source_row.difference is None:
                difference = None
                amount = Decimal("0.00")
            else:
                difference = Decimal(source_row.difference).quantize(Decimal("0.001"))
                amount = (difference * Decimal(tariff.price_per_unit)).quantize(Decimal("0.01"))
            unit_price = Decimal(tariff.price_per_unit)
        row = CalculationRowOut(
            meter_id=None,
            service_name=service_name,
            meter_register=tariff.meter_register or "total",
            previous_reading=None,
            current_reading=None,
            difference=difference,
            unit_name=tariff.unit_name,
            unit_price=unit_price,
            amount=amount,
            can_edit_previous=False,
        )
        rows.append(row)
        rendered[service_name] = row

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
                service_name=f"Відшкодування: {reimbursement.category}",
                meter_register="total",
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
    meters = db.scalars(select(Meter).where(Meter.apartment_id == apartment_id)).all()
    meter_by_service = {m.service_name: m for m in meters}

    period_start = date(year, month, 1)
    tariffs = db.scalars(
        select(Tariff).where(Tariff.apartment_id == apartment_id).where(Tariff.effective_from <= period_start)
    ).all()
    services = db.scalars(select(ApartmentService).where(ApartmentService.apartment_id == apartment_id)).all()
    service_map = {s.service_name: s for s in services}
    latest: dict[str, Tariff] = {}
    for t in tariffs:
        if not _service_active_for_period(service_map.get(t.service_name), year, month):
            continue
        cur = latest.get(t.service_name)
        if cur is None or t.effective_from > cur.effective_from:
            latest[t.service_name] = t

    total = Decimal("0.00")
    consumed_by_service: dict[str, Decimal] = {}
    pending_source: list[tuple[str, Tariff]] = []

    def _resolve_meter(t: Tariff) -> Meter | None:
        if t.meter_id:
            meter = db.get(Meter, t.meter_id)
            if meter is not None and meter.apartment_id == apartment_id:
                return meter
        return meter_by_service.get(t.service_name)

    for service_name, tariff in latest.items():
        if tariff.charge_mode == ChargeMode.fixed:
            cons = Decimal("1.000")
            amount = Decimal(tariff.price_per_unit).quantize(Decimal("0.01"))
        else:
            if tariff.source_service_name:
                pending_source.append((service_name, tariff))
                continue
            meter = _resolve_meter(tariff)
            if meter is None:
                continue
            register_name = tariff.meter_register or "total"
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
            if current is None:
                continue
            prev = _prev_reading(db, meter.id, register_name, year, month, Decimal(meter.initial_reading))
            cons = Decimal(current.value) - prev
            if cons < 0:
                raise HTTPException(status_code=400, detail=f"Negative consumption for meter {meter.id}.")
            amount = (cons * Decimal(tariff.price_per_unit)).quantize(Decimal("0.01"))

        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                service_name=service_name,
                utility_type=tariff.utility_type,
                unit_name=UnitType(tariff.unit_name),
                consumption=cons,
                unit_price=tariff.price_per_unit,
                amount=amount,
            )
        )
        total += amount
        consumed_by_service[service_name] = cons

    for service_name, tariff in pending_source:
        source_cons = consumed_by_service.get(tariff.source_service_name or "")
        if source_cons is None:
            continue
        cons = Decimal(source_cons).quantize(Decimal("0.001"))
        amount = (cons * Decimal(tariff.price_per_unit)).quantize(Decimal("0.01"))
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                service_name=service_name,
                utility_type=tariff.utility_type,
                unit_name=UnitType(tariff.unit_name),
                consumption=cons,
                unit_price=tariff.price_per_unit,
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
    start_key = _month_key(start_year, start_month)
    carry = Decimal("0.00")
    for inv in invoices:
        key = _month_key(inv.year, inv.month)
        if key < start_key:
            carry = Decimal(inv.closing_balance)
            continue
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
    return TenantOut(
        id=tenant.id,
        full_name=tenant.full_name,
        phone=tenant.phone,
        access_code=tenant.access_code,
        bank_statement_name=tenant.bank_statement_name,
        rent_amount=tenant.rent_amount,
        rent_currency=tenant.rent_currency,
        photo_url=f"/admin/storage/{tenant.photo_path}" if tenant.photo_path else None,
        passport_number=tenant.passport_number,
        passport_issued_by=tenant.passport_issued_by,
        passport_issue_date=tenant.passport_issue_date,
        passport_expiry_date=tenant.passport_expiry_date,
        phones=[p.phone for p in tenant.phones],
        contacts=tenant.contacts,
    )


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
    apartment = Apartment(code=code or _generate_apartment_code(db, payload.address), address=payload.address)
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
    apartment.address = payload.address
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
    tenant_ids.update(db.scalars(select(UtilityPayment.tenant_id).where(UtilityPayment.apartment_id == apartment_id)).all())
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
    for row in db.scalars(select(Tariff).where(Tariff.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(ApartmentTariffSetting).where(ApartmentTariffSetting.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(ApartmentService).where(ApartmentService.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(OwnerCharge).where(OwnerCharge.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.apartment_id == apartment_id)).all():
        db.delete(row)
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


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    tenant = Tenant(full_name=payload.full_name, phone=payload.phone, access_code=payload.access_code)
    db.add(tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant access code already exists.")
    db.refresh(tenant)
    return _tenant_out(tenant)


@router.get("/tenants", response_model=list[TenantBasicOut])
def list_tenants(db: Session = Depends(get_db)):
    return db.scalars(select(Tenant).order_by(Tenant.full_name)).all()


@router.put("/tenants/{tenant_id}", response_model=TenantOut, dependencies=[Depends(require_write_access)])
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    tenant.full_name = payload.full_name
    tenant.phone = payload.primary_phone
    tenant.bank_statement_name = payload.bank_statement_name
    tenant.rent_amount = payload.rent_amount
    tenant.rent_currency = payload.rent_currency
    tenant.passport_number = payload.passport_number
    tenant.passport_issued_by = payload.passport_issued_by
    tenant.passport_issue_date = payload.passport_issue_date
    tenant.passport_expiry_date = payload.passport_expiry_date

    for row in list(tenant.phones):
        db.delete(row)
    for row in list(tenant.contacts):
        db.delete(row)
    for phone in payload.phones:
        if phone.strip():
            db.add(TenantPhone(tenant_id=tenant.id, phone=phone.strip()))
    for c in payload.contacts:
        db.add(TenantContact(tenant_id=tenant.id, name=c.name, relation=c.relation, phone=c.phone, note=c.note))

    db.commit()
    db.refresh(tenant)
    return _tenant_out(tenant)


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
    meter = Meter(**payload.model_dump())
    db.add(meter)
    db.commit()
    db.refresh(meter)
    return meter


@router.put("/meters/{meter_id}", response_model=MeterOut, dependencies=[Depends(require_write_access)])
def update_meter(meter_id: int, payload: MeterUpdate, db: Session = Depends(get_db)):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    meter.service_name = payload.service_name
    meter.utility_type = payload.utility_type
    meter.serial_number = payload.serial_number
    meter.initial_reading = payload.initial_reading
    meter.installed_at = payload.installed_at
    db.commit()
    db.refresh(meter)
    return meter


@router.delete("/meters/{meter_id}", dependencies=[Depends(require_write_access)])
def delete_meter(meter_id: int, db: Session = Depends(get_db)):
    meter = db.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
    bound_tariff = db.scalar(select(Tariff).where(Tariff.meter_id == meter_id).limit(1))
    if bound_tariff is not None:
        raise HTTPException(
            status_code=409,
            detail="Meter is used in tariffs. Rebind or delete related tariffs first.",
        )
    db.delete(meter)
    db.commit()
    return {"status": "deleted"}


@router.get("/apartments/{apartment_id}/meters", response_model=list[MeterOut])
def list_meters(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    return db.scalars(select(Meter).where(Meter.apartment_id == apartment_id).order_by(Meter.service_name)).all()


@router.get("/apartments/{apartment_id}/meter-period", response_model=list[MeterPeriodRowOut])
def meter_period(apartment_id: int, year: int, month: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows: list[MeterPeriodRowOut] = []
    meters = db.scalars(select(Meter).where(Meter.apartment_id == apartment_id).order_by(Meter.service_name)).all()
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
                service_name=meter.service_name,
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
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    if payload.charge_mode == ChargeMode.metered and payload.utility_type is None:
        raise HTTPException(status_code=400, detail="utility_type is required for metered tariffs.")
    if payload.charge_mode == ChargeMode.metered and payload.source_service_name and payload.meter_id:
        raise HTTPException(status_code=400, detail="Use either meter_id or source_service_name for metered tariff.")
    if payload.source_service_name and payload.source_service_name == payload.service_name:
        raise HTTPException(status_code=400, detail="source_service_name must differ from service_name.")
    bound_meter: Meter | None = None
    if payload.charge_mode == ChargeMode.metered:
        if payload.source_service_name:
            bound_meter = None
        elif payload.meter_id is not None:
            bound_meter = db.get(Meter, payload.meter_id)
            if bound_meter is None or bound_meter.apartment_id != payload.apartment_id:
                raise HTTPException(status_code=404, detail="Meter not found for this apartment.")
        else:
            bound_meter = db.scalar(
                select(Meter).where(
                    and_(
                        Meter.apartment_id == payload.apartment_id,
                        Meter.service_name == payload.service_name,
                    )
                )
            )
            if bound_meter is None:
                if payload.initial_meter_reading is None:
                    raise HTTPException(status_code=400, detail="initial_meter_reading is required for new metered service.")
                bound_meter = Meter(
                    apartment_id=payload.apartment_id,
                    service_name=payload.service_name,
                    utility_type=payload.utility_type,
                    serial_number=payload.meter_serial_number,
                    initial_reading=payload.initial_meter_reading,
                    installed_at=payload.effective_from,
                )
                db.add(bound_meter)
                db.flush()
    tariff_data = payload.model_dump(exclude={"initial_meter_reading", "meter_serial_number"})
    if payload.charge_mode == ChargeMode.metered and payload.source_service_name is None and bound_meter is not None:
        tariff_data["meter_id"] = bound_meter.id
    tariff = Tariff(**tariff_data)
    db.add(tariff)
    _ensure_apartment_service(db, payload.apartment_id, payload.service_name, payload.effective_from)
    db.commit()
    _recalc_from_period(db, payload.apartment_id, payload.effective_from.year, payload.effective_from.month)
    db.refresh(tariff)
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.effective_from.year,
        month=payload.effective_from.month,
        actor_username=user.username,
        action="tariff_created",
        entity_type="tariff",
        entity_id=tariff.id,
        service_name=tariff.service_name,
        details={
            "price_per_unit": str(tariff.price_per_unit),
            "unit_name": tariff.unit_name.value,
            "charge_mode": tariff.charge_mode.value,
        },
    )
    db.commit()
    return tariff


@router.put("/tariffs/{tariff_id}", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def update_tariff(
    tariff_id: int,
    payload: TariffUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff not found.")
    recalc_apartment_id = tariff.apartment_id
    recalc_year = tariff.effective_from.year
    recalc_month = tariff.effective_from.month
    old_price = Decimal(tariff.price_per_unit)
    old_unit = tariff.unit_name
    tariff.price_per_unit = payload.price_per_unit
    tariff.unit_name = payload.unit_name
    db.commit()
    _recalc_from_period(db, recalc_apartment_id, recalc_year, recalc_month)
    db.refresh(tariff)
    _log_billing_change(
        db,
        apartment_id=recalc_apartment_id,
        year=recalc_year,
        month=recalc_month,
        actor_username=user.username,
        action="tariff_updated",
        entity_type="tariff",
        entity_id=tariff.id,
        service_name=tariff.service_name,
        details={
            "old_price_per_unit": str(old_price),
            "new_price_per_unit": str(tariff.price_per_unit),
            "old_unit_name": old_unit.value,
            "new_unit_name": tariff.unit_name.value,
        },
    )
    db.commit()
    return tariff


@router.put("/tariffs/{tariff_id}/binding", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def update_tariff_binding(
    tariff_id: int,
    payload: TariffBindingUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff not found.")
    if tariff.charge_mode != ChargeMode.metered:
        raise HTTPException(status_code=400, detail="Binding can be changed only for metered tariffs.")
    if payload.meter_id is not None and payload.source_service_name:
        raise HTTPException(status_code=400, detail="Use either meter_id or source_service_name.")
    if payload.source_service_name == tariff.service_name:
        raise HTTPException(status_code=400, detail="source_service_name must differ from service_name.")
    if payload.meter_id is not None:
        meter = db.get(Meter, payload.meter_id)
        if meter is None or meter.apartment_id != tariff.apartment_id:
            raise HTTPException(status_code=404, detail="Meter not found for this apartment.")
    old_meter_id = tariff.meter_id
    old_register = tariff.meter_register
    old_source = tariff.source_service_name
    tariff.meter_id = payload.meter_id
    tariff.meter_register = payload.meter_register or "total"
    tariff.source_service_name = payload.source_service_name
    db.commit()
    _recalc_from_period(db, tariff.apartment_id, tariff.effective_from.year, tariff.effective_from.month)
    db.refresh(tariff)
    _log_billing_change(
        db,
        apartment_id=tariff.apartment_id,
        year=tariff.effective_from.year,
        month=tariff.effective_from.month,
        actor_username=user.username,
        action="tariff_updated",
        entity_type="tariff",
        entity_id=tariff.id,
        service_name=tariff.service_name,
        details={
            "old_meter_id": old_meter_id,
            "new_meter_id": tariff.meter_id,
            "old_meter_register": old_register,
            "new_meter_register": tariff.meter_register,
            "old_source_service_name": old_source,
            "new_source_service_name": tariff.source_service_name,
        },
    )
    db.commit()
    return tariff


@router.post("/tariffs/{tariff_id}/apply-from-period", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def apply_tariff_from_period(
    tariff_id: int,
    payload: TariffApplyFromPeriod,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    source = db.get(Tariff, tariff_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Tariff not found.")
    effective_from = date(payload.year, payload.month, 1)
    target = db.scalar(
        select(Tariff).where(
            and_(
                Tariff.apartment_id == source.apartment_id,
                Tariff.service_name == source.service_name,
                Tariff.effective_from == effective_from,
            )
        )
    )
    if target is None:
        target = Tariff(
            apartment_id=source.apartment_id,
            service_name=source.service_name,
            charge_mode=source.charge_mode,
            utility_type=source.utility_type,
            unit_name=payload.unit_name,
            price_per_unit=payload.price_per_unit,
            meter_id=source.meter_id,
            meter_register=source.meter_register,
            source_service_name=source.source_service_name,
            effective_from=effective_from,
        )
        db.add(target)
    else:
        target.price_per_unit = payload.price_per_unit
        target.unit_name = payload.unit_name
    _ensure_apartment_service(db, source.apartment_id, source.service_name, effective_from)
    db.commit()
    _recalc_from_period(db, source.apartment_id, payload.year, payload.month)
    db.refresh(target)
    _log_billing_change(
        db,
        apartment_id=source.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="tariff_applied_from_period",
        entity_type="tariff",
        entity_id=target.id,
        service_name=source.service_name,
        details={
            "price_per_unit": str(target.price_per_unit),
            "unit_name": target.unit_name.value,
            "effective_from": target.effective_from.isoformat(),
        },
    )
    db.commit()
    return target


@router.put("/apartments/{apartment_id}/services/{service_name}/activation", dependencies=[Depends(require_write_access)])
def update_service_activation(
    apartment_id: int,
    service_name: str,
    payload: ServiceActivationUpdate,
    db: Session = Depends(get_db),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    row = db.scalar(
        select(ApartmentService).where(
            and_(
                ApartmentService.apartment_id == apartment_id,
                ApartmentService.service_name == service_name,
            )
        )
    )
    if row is None:
        tariff = db.scalar(
            select(Tariff)
            .where(Tariff.apartment_id == apartment_id)
            .where(Tariff.service_name == service_name)
            .order_by(Tariff.effective_from.asc())
        )
        if tariff is None:
            raise HTTPException(status_code=404, detail="Service not found.")
        row = ApartmentService(
            apartment_id=apartment_id,
            service_name=service_name,
            active_from=tariff.effective_from,
        )
        db.add(row)
        db.flush()
    row.inactive_from = payload.inactive_from
    db.commit()
    start = row.active_from if payload.inactive_from is None else min(row.active_from, payload.inactive_from)
    _recalc_from_period(db, apartment_id, start.year, start.month)
    return {"status": "updated"}


@router.delete("/tariffs/{tariff_id}", dependencies=[Depends(require_write_access)])
def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(get_current_admin_user)
):
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff not found.")
    recalc_apartment_id = tariff.apartment_id
    recalc_year = tariff.effective_from.year
    recalc_month = tariff.effective_from.month
    service_name = tariff.service_name
    old_price = Decimal(tariff.price_per_unit)
    old_unit = tariff.unit_name
    db.delete(tariff)
    db.commit()
    _recalc_from_period(db, recalc_apartment_id, recalc_year, recalc_month)
    _log_billing_change(
        db,
        apartment_id=recalc_apartment_id,
        year=recalc_year,
        month=recalc_month,
        actor_username=user.username,
        action="tariff_deleted",
        entity_type="tariff",
        entity_id=tariff_id,
        service_name=service_name,
        details={"old_price_per_unit": str(old_price), "old_unit_name": old_unit.value},
    )
    db.commit()
    return {"status": "deleted"}


@router.post("/readings", response_model=ReadingOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def add_or_update_reading(
    payload: ReadingCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    meter = db.get(Meter, payload.meter_id)
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found.")
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
            service_name=meter.service_name,
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
        service_name=meter.service_name,
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
        service_name=meter.service_name,
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
    invoice = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == payload.apartment_id, Invoice.year == payload.year, Invoice.month == payload.month)
        )
    )
    if invoice is None:
        try:
            generate_invoice(db, payload.apartment_id, payload.year, payload.month)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"Cannot save payment: {error}")
        invoice = db.scalar(
            select(Invoice).where(
                and_(Invoice.apartment_id == payload.apartment_id, Invoice.year == payload.year, Invoice.month == payload.month)
            )
        )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    tenancy = _active_tenancy(db, payload.apartment_id, payload.paid_at)
    tenant_id = tenancy.tenant_id if tenancy is not None else invoice.tenant_id
    existing_rows = db.scalars(
        select(UtilityPayment).where(
            and_(
                UtilityPayment.apartment_id == payload.apartment_id,
                UtilityPayment.year == payload.year,
                UtilityPayment.month == payload.month,
            )
        )
    ).all()
    old_amount = Decimal("0.00")
    old_paid_at = None
    old_note = None
    if existing_rows:
        keep = existing_rows[0]
        old_amount = Decimal(keep.amount)
        old_paid_at = keep.paid_at
        old_note = keep.note
        keep.tenant_id = tenant_id
        keep.invoice_id = invoice.id
        keep.amount = payload.amount
        keep.paid_at = payload.paid_at
        keep.note = payload.note
        keep.confirmed = True
        for row in existing_rows[1:]:
            db.delete(row)
    else:
        db.add(
            UtilityPayment(
                apartment_id=payload.apartment_id,
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                year=payload.year,
                month=payload.month,
                amount=payload.amount,
                paid_at=payload.paid_at,
                note=payload.note,
                confirmed=True,
            )
        )
    invoice.utility_payment_received = Decimal(payload.amount).quantize(Decimal("0.01"))
    invoice.closing_balance = (
        Decimal(invoice.carry_over_debt) + Decimal(invoice.total_amount) - Decimal(invoice.utility_payment_received)
    ).quantize(Decimal("0.01"))
    invoice.status = InvoiceStatus.paid if invoice.closing_balance <= 0 else InvoiceStatus.unpaid
    db.commit()
    _recalc_from_period(db, payload.apartment_id, payload.year, payload.month)
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="utility_payment_saved",
        entity_type="utility_payment",
        entity_id=existing_rows[0].id if existing_rows else None,
        details={
            "old_amount": str(old_amount),
            "new_amount": str(payload.amount),
            "old_paid_at": old_paid_at.isoformat() if old_paid_at else None,
            "new_paid_at": payload.paid_at.isoformat(),
            "old_note": old_note,
            "new_note": payload.note,
        },
    )
    db.commit()
    return {"status": "saved"}


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
    _ensure_apartment_service(db, apartment_id, normalized_service_name, date(payload.year, payload.month, 1))
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
        latest_invoice = db.scalar(select(Invoice).where(Invoice.apartment_id == a.id).order_by(Invoice.year.desc(), Invoice.month.desc()))
        if latest_invoice:
            _, _, _, utility_balance = _effective_utility_period(db, a.id, latest_invoice.year, latest_invoice.month)
        else:
            utility_balance = Decimal("0.00")
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
    month_payment_row = db.scalar(
        select(UtilityPayment)
        .where(
            and_(
                UtilityPayment.apartment_id == apartment_id,
                UtilityPayment.year == year,
                UtilityPayment.month == month,
            )
        )
        .order_by(UtilityPayment.id.desc())
    )

    rows = _build_period_rows(db, apartment_id, year, month, invoice)

    month_charges_from_rows = sum((Decimal(r.amount) for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))
    current_balance_from_rows = (prev_debt + month_charges_from_rows - month_payments).quantize(Decimal("0.01"))

    rent = db.scalar(select(RentLedger).where(and_(RentLedger.apartment_id == apartment_id, RentLedger.year == year, RentLedger.month == month)))
    calc_locked = _is_month_locked(db, apartment_id, year, month)
    return ApartmentDetailOut(
        apartment_id=apartment.id,
        code=apartment.code,
        address=apartment.address,
        tenant=_tenant_out(tenant),
        year=year,
        month=month,
        utility_balance=BalanceExplainOut(
            previous_month_debt=prev_debt,
            month_charges=month_charges_from_rows,
            month_payments=month_payments,
            month_payment_date=month_payment_row.paid_at if month_payment_row else None,
            month_payment_note=month_payment_row.note if month_payment_row else None,
            current_balance=current_balance_from_rows,
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
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    if year is None or month is None:
        year, month = _default_period()
    target_period = date(year, month, 1)
    tariffs = db.scalars(select(Tariff).where(Tariff.apartment_id == apartment_id).order_by(Tariff.service_name, Tariff.effective_from.desc())).all()
    latest: dict[str, Tariff] = {}
    for tariff in tariffs:
        if tariff.effective_from > target_period:
            continue
        latest.setdefault(tariff.service_name, tariff)
    settings = db.scalars(select(ApartmentTariffSetting).where(ApartmentTariffSetting.apartment_id == apartment_id)).all()
    settings_map = {s.service_name: s for s in settings}
    services = db.scalars(select(ApartmentService).where(ApartmentService.apartment_id == apartment_id)).all()
    service_map = {s.service_name: s for s in services}
    rows: list[ApartmentTariffRowOut] = []
    for service_name, tariff in latest.items():
        setting = settings_map.get(service_name)
        rows.append(
            ApartmentTariffRowOut(
                tariff_id=tariff.id,
                service_name=service_name,
                charge_mode=tariff.charge_mode,
                utility_type=tariff.utility_type,
                unit_name=tariff.unit_name,
                price_per_unit=tariff.price_per_unit,
                meter_id=tariff.meter_id,
                meter_register=tariff.meter_register,
                source_service_name=tariff.source_service_name,
                active_from=service_map.get(service_name).active_from if service_map.get(service_name) else None,
                inactive_from=service_map.get(service_name).inactive_from if service_map.get(service_name) else None,
                is_active_for_period=_service_active_for_period(service_map.get(service_name), year, month),
                provider_company=setting.provider_company if setting else None,
                personal_account=setting.personal_account if setting else None,
                cabinet_url=setting.cabinet_url if setting else None,
                cabinet_login=setting.cabinet_login if setting else None,
                cabinet_password=decrypt_text(setting.cabinet_password_encrypted) if setting else None,
                last_tariff_check_at=setting.last_tariff_check_at if setting else None,
            )
        )
    return sorted(rows, key=lambda x: x.service_name.lower())


@router.get("/dashboard/apartments/{apartment_id}/missing-services", response_model=list[MissingServiceOut])
def missing_services(apartment_id: int, year: int, month: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    target_period = date(year, month, 1)
    tariffs = db.scalars(
        select(Tariff).where(Tariff.apartment_id == apartment_id).where(Tariff.effective_from <= target_period)
    ).all()
    latest_by_service: dict[str, Tariff] = {}
    for tariff in tariffs:
        current = latest_by_service.get(tariff.service_name)
        if current is None or tariff.effective_from > current.effective_from:
            latest_by_service[tariff.service_name] = tariff

    invoice = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == apartment_id, Invoice.year == year, Invoice.month == month)
        )
    )
    used = {item.service_name for item in invoice.items} if invoice else set()
    services = db.scalars(select(ApartmentService).where(ApartmentService.apartment_id == apartment_id)).all()
    service_map = {s.service_name: s for s in services}
    rows: list[MissingServiceOut] = []
    for service_name, tariff in latest_by_service.items():
        if not _service_active_for_period(service_map.get(service_name), year, month):
            continue
        if service_name in used:
            continue
        rows.append(MissingServiceOut(service_name=service_name, charge_mode=tariff.charge_mode, unit_name=tariff.unit_name))
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
    tariff = db.scalar(
        select(Tariff)
        .where(Tariff.apartment_id == apartment_id)
        .where(Tariff.service_name == payload.service_name)
        .order_by(Tariff.effective_from.desc())
    )
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff service not found.")
    _ensure_apartment_service(db, apartment_id, payload.service_name, tariff.effective_from)
    setting = db.scalar(
        select(ApartmentTariffSetting).where(
            and_(ApartmentTariffSetting.apartment_id == apartment_id, ApartmentTariffSetting.service_name == payload.service_name)
        )
    )
    if setting is None:
        setting = ApartmentTariffSetting(apartment_id=apartment_id, service_name=payload.service_name)
        db.add(setting)
    setting.provider_company = payload.provider_company
    setting.personal_account = payload.personal_account
    setting.cabinet_url = payload.cabinet_url
    setting.cabinet_login = payload.cabinet_login
    setting.cabinet_password_encrypted = encrypt_text(payload.cabinet_password)
    setting.last_tariff_check_at = payload.last_tariff_check_at or datetime.now(UTC)
    db.commit()
    db.refresh(setting)
    return ApartmentTariffRowOut(
        tariff_id=tariff.id,
        service_name=tariff.service_name,
        charge_mode=tariff.charge_mode,
        utility_type=tariff.utility_type,
        unit_name=tariff.unit_name,
        price_per_unit=tariff.price_per_unit,
        meter_id=tariff.meter_id,
        meter_register=tariff.meter_register,
        source_service_name=tariff.source_service_name,
        provider_company=setting.provider_company,
        personal_account=setting.personal_account,
        cabinet_url=setting.cabinet_url,
        cabinet_login=setting.cabinet_login,
        cabinet_password=decrypt_text(setting.cabinet_password_encrypted),
        last_tariff_check_at=setting.last_tariff_check_at,
    )
