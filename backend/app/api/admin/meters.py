# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_admin_user, require_write_access
from app.db.session import get_db
from app.services.billing import _resolve_previous_reading_by_register
from app.models import AdminUser, Apartment, ConnectionChargeLine, Meter, MeterReading, UtilityType
from app.schemas import MeterCreate, MeterExpectedRegisterItem, MeterExpectedRegistersOut, MeterInitialReadingUpdate, MeterOut, MeterPeriodRowOut, MeterReplaceRequest, MeterUpdate, ReadingCreate, ReadingOut
from ._shared import ELECTRICITY_REGISTER_LABELS, ELECTRICITY_REGISTER_ORDER, _active_meter_charge_lines, _electricity_plan_mode_from_registers, _get_meter_type_or_404, _log_billing_change, _meter_display_name, _meter_out, _prev_reading, _recalc_from_period

router = APIRouter()


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
