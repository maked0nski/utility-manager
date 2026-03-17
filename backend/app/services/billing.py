from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Apartment,
    ApartmentServiceConnection,
    ChargeLineKind,
    ConnectionChargeLine,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Meter,
    MeterReading,
    QuantitySource,
    Tenancy,
    UtilityType,
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


def _resolve_previous_reading(db: Session, meter_id: int, year: int, month: int, initial: Decimal) -> Decimal:
    return _resolve_previous_reading_by_register(db, meter_id, "total", year, month, initial)


def _resolve_previous_reading_by_register(
    db: Session, meter_id: int, register_name: str, year: int, month: int, initial: Decimal
) -> Decimal:
    period_start = date(year, month, 1)
    active_line = db.scalar(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.meter_id == meter_id)
        .where(ConnectionChargeLine.meter_register == register_name)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.is_active.is_(True))
        .where(ConnectionChargeLine.effective_from <= period_start)
        .where(
            or_(
                ConnectionChargeLine.effective_to.is_(None),
                ConnectionChargeLine.effective_to >= period_start,
            )
        )
        .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
    )
    if active_line is not None and active_line.initial_reading is not None:
        initial = Decimal(active_line.initial_reading)
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


def _register_meta(db: Session, meter: Meter | None, year: int, month: int, register_name: str) -> tuple[str | None, str | None, list[str]]:
    if meter is None or meter.utility_type != UtilityType.electricity:
        return None, None, []
    period_start = date(year, month, 1)
    lines = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.meter_id == meter.id)
        .where(ConnectionChargeLine.line_kind == ChargeLineKind.meter_register)
        .where(ConnectionChargeLine.is_active.is_(True))
        .where(ConnectionChargeLine.effective_from <= period_start)
        .where(
            or_(
                ConnectionChargeLine.effective_to.is_(None),
                ConnectionChargeLine.effective_to >= period_start,
            )
        )
        .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
    ).all()
    label_map = {
        "total": "Загальний",
        "day": "Денний",
        "night": "Нічний",
        "peak": "Піковий",
        "semi_peak": "Напівпіковий",
        "off_peak": "Нічний",
    }
    if not lines:
        return None, label_map.get(register_name, register_name), []
    registers = []
    for line in lines:
        current_register = (line.meter_register or "total").strip() or "total"
        if current_register not in registers:
            registers.append(current_register)
    if registers == ["total"]:
        plan_mode = "single"
    elif set(registers) == {"day", "night"}:
        plan_mode = "day_night"
        registers = ["day", "night"]
    elif set(registers) == {"peak", "semi_peak", "off_peak"}:
        plan_mode = "tri_zone"
        registers = ["peak", "semi_peak", "off_peak"]
    else:
        plan_mode = None
    return plan_mode, label_map.get(register_name, register_name), registers


def _line_quantity(apartment: Apartment, quantity_source: QuantitySource, multiplier: Decimal) -> Decimal:
    base = Decimal("1.000")
    if quantity_source == QuantitySource.registered_residents:
        base = Decimal(apartment.registered_residents or 0)
    elif quantity_source == QuantitySource.area_m2:
        base = Decimal(apartment.area_m2 or 0)
    return (base * Decimal(multiplier)).quantize(Decimal("0.001"))


def _resolve_active_source_line(
    db: Session, source_line: ConnectionChargeLine, period_start: date
) -> ConnectionChargeLine | None:
    return db.scalar(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == source_line.connection_id)
        .where(ConnectionChargeLine.line_kind == source_line.line_kind)
        .where(ConnectionChargeLine.meter_register == (source_line.meter_register or "total"))
        .where(ConnectionChargeLine.is_active.is_(True))
        .where(ConnectionChargeLine.effective_from <= period_start)
        .where(
            or_(
                ConnectionChargeLine.effective_to.is_(None),
                ConnectionChargeLine.effective_to >= period_start,
            )
        )
        .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
    )


def _register_meta_from_lines(
    meter: Meter | None,
    register_name: str,
    lines: list[ConnectionChargeLine],
) -> tuple[str | None, str | None, list[str]]:
    if meter is None or meter.utility_type != UtilityType.electricity:
        return None, None, []
    label_map = {
        "total": "Загальний",
        "day": "Денний",
        "night": "Нічний",
        "peak": "Піковий",
        "semi_peak": "Напівпіковий",
        "off_peak": "Нічний",
    }
    registers: list[str] = []
    for line in lines:
        current_register = (line.meter_register or "total").strip() or "total"
        if current_register not in registers:
            registers.append(current_register)
    if not registers:
        return None, label_map.get(register_name, register_name), []
    if registers == ["total"]:
        plan_mode = "single"
    elif set(registers) == {"day", "night"}:
        plan_mode = "day_night"
        registers = ["day", "night"]
    elif set(registers) == {"peak", "semi_peak", "off_peak"}:
        plan_mode = "tri_zone"
        registers = ["peak", "semi_peak", "off_peak"]
    else:
        plan_mode = None
    return plan_mode, label_map.get(register_name, register_name), registers


def build_connection_charge_rows(db: Session, apartment_id: int, year: int, month: int) -> list[dict[str, object]]:
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        return []
    period_start = date(year, month, 1)
    connections = db.scalars(
        select(ApartmentServiceConnection)
        .options(
            selectinload(ApartmentServiceConnection.service_catalog),
            selectinload(ApartmentServiceConnection.charge_lines).selectinload(ConnectionChargeLine.meter),
        )
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .where(ApartmentServiceConnection.started_at <= period_start)
        .where((ApartmentServiceConnection.ended_at.is_(None)) | (ApartmentServiceConnection.ended_at >= period_start))
        .where(ApartmentServiceConnection.status == "active")
        .order_by(ApartmentServiceConnection.started_at, ApartmentServiceConnection.id)
    ).all()
    if not connections:
        return []

    active_lines_by_connection: dict[int, list[ConnectionChargeLine]] = {}
    meter_ids: set[int] = set()
    active_meter_lines_by_meter: dict[int, list[ConnectionChargeLine]] = {}
    active_line_ids: set[int] = set()
    for connection in connections:
        lines = [
            line
            for line in connection.charge_lines
            if line.is_active and line.effective_from <= period_start and (line.effective_to is None or line.effective_to >= period_start)
        ]
        lines.sort(key=lambda line: (line.effective_from, line.id))
        active_lines_by_connection[connection.id] = lines
        for line in lines:
            active_line_ids.add(line.id)
            if line.line_kind == ChargeLineKind.meter_register and line.meter_id:
                meter_ids.add(line.meter_id)
                active_meter_lines_by_meter.setdefault(line.meter_id, []).append(line)

    readings_by_key: dict[tuple[int, str], list[MeterReading]] = {}
    if meter_ids:
        reading_rows = db.scalars(
            select(MeterReading)
            .where(MeterReading.meter_id.in_(meter_ids))
            .order_by(MeterReading.year, MeterReading.month, MeterReading.id)
        ).all()
        for reading in reading_rows:
            key = (reading.meter_id, reading.register_name)
            readings_by_key.setdefault(key, []).append(reading)

    rows: list[dict[str, object]] = []
    rendered_by_line_id: dict[int, dict[str, object]] = {}
    pending_derived: list[tuple[ApartmentServiceConnection, ConnectionChargeLine, bool]] = []

    for connection in connections:
        service_catalog = connection.service_catalog
        if service_catalog is None or not service_catalog.is_active:
            continue
        active_lines = active_lines_by_connection.get(connection.id, [])
        if not active_lines:
            continue
        multi_line = len(active_lines) > 1
        group_key = f"connection:{connection.id}" if multi_line else None
        group_label = service_catalog.name if multi_line else None

        for line in active_lines:
            if line.line_kind == ChargeLineKind.derived:
                pending_derived.append((connection, line, multi_line))
                continue

            meter = line.meter
            display_service_name = service_catalog.name if not multi_line else f"{service_catalog.name} • {line.label}"
            line_label = line.label if multi_line else None
            quantity: Decimal | None = None
            previous: Decimal | None = None
            current: Decimal | None = None
            can_edit_previous = False

            if line.line_kind == ChargeLineKind.fixed:
                quantity = _line_quantity(apartment, line.quantity_source, Decimal(line.quantity_multiplier))
            elif line.line_kind == ChargeLineKind.meter_register and meter is not None:
                register_name = line.meter_register or "total"
                readings = readings_by_key.get((meter.id, register_name), [])
                current_row = next((r for r in readings if r.year == year and r.month == month), None)
                line_initial = Decimal(line.initial_reading) if line.initial_reading is not None else Decimal(meter.initial_reading)
                previous_candidates = [r for r in readings if _period_key(r.year, r.month) < _period_key(year, month)]
                previous = Decimal(previous_candidates[-1].value) if previous_candidates else line_initial
                current = Decimal(current_row.value) if current_row else None
                can_edit_previous = len(previous_candidates) == 0
                if current is not None:
                    quantity = (current - previous).quantize(Decimal("0.001"))
                else:
                    quantity = None

            amount = (
                (Decimal(quantity) * Decimal(line.price_per_unit)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                if quantity is not None
                else Decimal("0.00")
            )
            meter_plan_mode, meter_register_label, meter_expected_registers = _register_meta_from_lines(
                meter,
                line.meter_register or "total",
                active_meter_lines_by_meter.get(meter.id if meter else 0, []),
            )
            payload: dict[str, object] = {
                "meter_id": meter.id if meter else None,
                "source_line_id": None,
                "service_name": display_service_name,
                "service_group_key": group_key,
                "service_group_label": group_label,
                "service_line_label": line_label,
                "meter_register": line.meter_register or "total",
                "meter_register_label": meter_register_label,
                "meter_plan_mode": meter_plan_mode,
                "meter_expected_registers": meter_expected_registers,
                "previous_reading": previous,
                "current_reading": current,
                "difference": quantity,
                "unit_name": line.unit_name,
                "unit_price": Decimal(line.price_per_unit),
                "amount": amount,
                "can_edit_previous": can_edit_previous,
                "utility_type": meter.utility_type if meter else (service_catalog.allowed_meter_utility_type or service_catalog.default_provider_utility_type),
                "line_id": line.id,
            }
            rows.append(payload)
            rendered_by_line_id[line.id] = payload

    for connection, line, multi_line in pending_derived:
        service_catalog = connection.service_catalog
        if service_catalog is None:
            continue
        source_payload = rendered_by_line_id.get(line.derived_from_line_id or 0)
        if source_payload is None and line.derived_from_line_id:
            source_line = db.get(ConnectionChargeLine, line.derived_from_line_id)
            if source_line is not None:
                is_source_active = (
                    source_line.is_active
                    and source_line.effective_from <= period_start
                    and (source_line.effective_to is None or source_line.effective_to >= period_start)
                )
                active_source_line = source_line if is_source_active else _resolve_active_source_line(db, source_line, period_start)
                if active_source_line is not None:
                    source_payload = rendered_by_line_id.get(active_source_line.id)
        display_service_name = service_catalog.name if not multi_line else f"{service_catalog.name} • {line.label}"
        line_label = line.label if multi_line else None
        quantity = None
        previous = None
        current = None
        meter_register = line.meter_register or "total"
        meter_register_label = None
        meter_plan_mode = None
        meter_expected_registers: list[str] = []
        if source_payload and source_payload.get("difference") is not None:
            quantity = Decimal(source_payload["difference"]).quantize(Decimal("0.001"))
            previous = source_payload.get("previous_reading")
            current = source_payload.get("current_reading")
            meter_register = str(source_payload.get("meter_register") or meter_register)
            meter_register_label = source_payload.get("meter_register_label")
            meter_plan_mode = source_payload.get("meter_plan_mode")
            meter_expected_registers = list(source_payload.get("meter_expected_registers") or [])
        amount = (
            (Decimal(quantity) * Decimal(line.price_per_unit)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            if quantity is not None
            else Decimal("0.00")
        )
        payload = {
            "meter_id": None,
            "source_line_id": line.derived_from_line_id,
            "service_name": display_service_name,
            "service_group_key": f"connection:{connection.id}" if multi_line else None,
            "service_group_label": service_catalog.name if multi_line else None,
            "service_line_label": line_label,
            "meter_register": meter_register,
            "meter_register_label": meter_register_label,
            "meter_plan_mode": meter_plan_mode,
            "meter_expected_registers": meter_expected_registers,
            "previous_reading": previous,
            "current_reading": current,
            "difference": quantity,
            "unit_name": line.unit_name,
            "unit_price": Decimal(line.price_per_unit),
            "amount": amount,
            "can_edit_previous": False,
            "utility_type": service_catalog.allowed_meter_utility_type or service_catalog.default_provider_utility_type,
            "line_id": line.id,
        }
        rows.append(payload)
        rendered_by_line_id[line.id] = payload

    return rows


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

    connection_rows = build_connection_charge_rows(db, apartment_id, year, month)
    if not connection_rows:
        raise ValueError("No active service connections available for this period.")

    for row in connection_rows:
        consumption = Decimal(row["difference"]) if row["difference"] is not None else Decimal("0.000")
        amount = Decimal(row["amount"]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        total += amount
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
