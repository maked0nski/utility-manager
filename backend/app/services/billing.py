from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import (
    Apartment,
    ApartmentService,
    ChargeMode,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Meter,
    MeterReading,
    Tariff,
    Tenancy,
    UnitType,
)

TWOPLACES = Decimal("0.01")


def _period_key(year: int, month: int) -> int:
    return year * 100 + month


def _resolve_active_tenant(db: Session, apartment_id: int, year: int, month: int) -> int:
    period_key = _period_key(year, month)
    tenancies = db.scalars(select(Tenancy).where(Tenancy.apartment_id == apartment_id)).all()
    for tenancy in tenancies:
        start_key = tenancy.start_date.year * 100 + tenancy.start_date.month
        end_key = 999999 if tenancy.end_date is None else tenancy.end_date.year * 100 + tenancy.end_date.month
        if start_key <= period_key <= end_key:
            return tenancy.tenant_id
    raise ValueError("No active tenant for this apartment and period.")


def _resolve_tariffs_for_apartment(db: Session, apartment_id: int, year: int, month: int) -> list[Tariff]:
    period_date = date(year, month, 1)
    services = db.scalars(select(ApartmentService).where(ApartmentService.apartment_id == apartment_id)).all()
    service_map = {s.service_name: s for s in services}
    tariffs = db.scalars(
        select(Tariff).where(Tariff.apartment_id == apartment_id).where(Tariff.effective_from <= period_date)
    ).all()
    latest_by_service: dict[str, Tariff] = {}
    for tariff in tariffs:
        service = service_map.get(tariff.service_name)
        if service is not None:
            if service.active_from > period_date:
                continue
            if service.inactive_from is not None and service.inactive_from <= period_date:
                continue
        current = latest_by_service.get(tariff.service_name)
        if current is None or tariff.effective_from > current.effective_from:
            latest_by_service[tariff.service_name] = tariff
    return list(latest_by_service.values())


def _resolve_previous_reading(db: Session, meter_id: int, year: int, month: int, initial: Decimal) -> Decimal:
    return _resolve_previous_reading_by_register(db, meter_id, "total", year, month, initial)


def _resolve_previous_reading_by_register(
    db: Session, meter_id: int, register_name: str, year: int, month: int, initial: Decimal
) -> Decimal:
    key = _period_key(year, month)
    readings = db.scalars(
        select(MeterReading)
        .where(MeterReading.meter_id == meter_id)
        .where(MeterReading.register_name == register_name)
    ).all()
    previous = [r for r in readings if _period_key(r.year, r.month) < key]
    if not previous:
        return initial
    last = sorted(previous, key=lambda r: (_period_key(r.year, r.month), r.id), reverse=True)[0]
    return Decimal(last.value)


def generate_invoice(db: Session, apartment_id: int, year: int, month: int) -> Invoice:
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise ValueError("Apartment not found.")

    existing = db.scalar(
        select(Invoice).where(
            and_(Invoice.apartment_id == apartment_id, Invoice.year == year, Invoice.month == month)
        )
    )
    if existing is not None:
        return existing

    tenant_id = _resolve_active_tenant(db, apartment_id, year, month)
    meters = db.scalars(select(Meter).where(Meter.apartment_id == apartment_id)).all()
    meter_by_service = {meter.service_name: meter for meter in meters}
    tariffs = _resolve_tariffs_for_apartment(db, apartment_id, year, month)
    if not tariffs:
        raise ValueError("No tariffs available for this period.")

    invoice = Invoice(
        apartment_id=apartment_id,
        tenant_id=tenant_id,
        year=year,
        month=month,
        status=InvoiceStatus.unpaid,
        total_amount=Decimal("0.00"),
        carry_over_debt=Decimal("0.00"),
        utility_payment_received=Decimal("0.00"),
        closing_balance=Decimal("0.00"),
    )
    db.add(invoice)
    db.flush()

    total = Decimal("0.00")
    consumed_by_service: dict[str, Decimal] = {}
    pending_source: list[Tariff] = []

    def _resolve_meter(tariff: Tariff) -> Meter | None:
        if tariff.meter_id:
            meter = db.get(Meter, tariff.meter_id)
            if meter is not None and meter.apartment_id == apartment_id:
                return meter
        return meter_by_service.get(tariff.service_name)

    for tariff in tariffs:
        if tariff.charge_mode == ChargeMode.fixed:
            consumption = Decimal("1")
            amount = Decimal(tariff.price_per_unit).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        else:
            if tariff.source_service_name:
                pending_source.append(tariff)
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

            previous_value = _resolve_previous_reading_by_register(
                db, meter.id, register_name, year, month, Decimal(meter.initial_reading)
            )
            consumption = Decimal(current.value) - previous_value
            if consumption < 0:
                raise ValueError(
                    f"Reading regression for meter_id={meter.id}: "
                    f"{current.value} < previous={previous_value}"
                )
            amount = (consumption * Decimal(tariff.price_per_unit)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        total += amount

        item = InvoiceItem(
            invoice_id=invoice.id,
            service_name=tariff.service_name,
            utility_type=tariff.utility_type,
            unit_name=UnitType(tariff.unit_name),
            consumption=consumption,
            unit_price=tariff.price_per_unit,
            amount=amount,
        )
        db.add(item)
        consumed_by_service[tariff.service_name] = consumption

    for tariff in pending_source:
        source_consumption = consumed_by_service.get(tariff.source_service_name or "")
        if source_consumption is None:
            continue
        consumption = Decimal(source_consumption).quantize(Decimal("0.001"))
        amount = (consumption * Decimal(tariff.price_per_unit)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        total += amount
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                service_name=tariff.service_name,
                utility_type=tariff.utility_type,
                unit_name=UnitType(tariff.unit_name),
                consumption=consumption,
                unit_price=tariff.price_per_unit,
                amount=amount,
            )
        )

    prev_invoice = db.scalar(
        select(Invoice)
        .where(Invoice.apartment_id == apartment_id)
        .where((Invoice.year * 100 + Invoice.month) < _period_key(year, month))
        .order_by(Invoice.year.desc(), Invoice.month.desc())
    )
    carry_over = Decimal(prev_invoice.closing_balance) if prev_invoice else Decimal("0.00")
    invoice.carry_over_debt = carry_over.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    invoice.total_amount = total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    invoice.closing_balance = (invoice.carry_over_debt + invoice.total_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    db.commit()
    db.refresh(invoice)
    return invoice
