# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_admin_user, require_write_access
from app.db.session import get_db
from app.models import AdminUser, Apartment, ApartmentAutomation, ApartmentServiceConnection, ChargeLineKind, ConnectionChargeLine, Meter, MeterReading, Provider, QuantitySource, ServiceCatalog, UnitType, UtilityType
from app.schemas import ApartmentServiceConnectionCreate, ApartmentServiceConnectionOut, ApartmentServiceConnectionUpdate, ApartmentTariffRowOut, ConnectionChargeLineCreate, ConnectionChargeLineOut, ConnectionChargeLineUpdate, ElectricityPlanHistoryOut, ElectricityPlanUpsert, TariffApplyFromPeriod, TariffSettingUpsert
from ._shared import ELECTRICITY_REGISTER_ORDER, _clean_optional_text, _electricity_plan_mode_from_registers, _legacy_api_disabled, _log_billing_change, _meter_display_name, _period_key, _recalc_from_period, _service_connection_out

router = APIRouter()


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
                unit_name=UnitType.kwh,
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
            target.unit_name = UnitType.kwh
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

@router.get("/apartments/{apartment_id}/tariffs", response_model=list[ApartmentTariffRowOut])
def apartment_tariffs(apartment_id: int, year: int | None = None, month: int | None = None, db: Session = Depends(get_db)):
    _legacy_api_disabled("Legacy tariff list API")
    raise AssertionError("unreachable")

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

    already_covers_period = (
        source.price_per_unit == payload.price_per_unit
        and source.unit_name == payload.unit_name
        and source.effective_from <= effective_from
        and (source.effective_to is None or source.effective_to >= effective_from)
    )
    if already_covers_period:
        # Nothing actually changed - the source line already covers this period at this
        # price, so cloning a new dated row would just be redundant history. This is the
        # server-side backstop for callers that re-submit the same price every month.
        return source

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

@router.put("/apartments/{apartment_id}/tariffs/settings", response_model=ApartmentTariffRowOut, dependencies=[Depends(require_write_access)])
def upsert_apartment_tariff_setting(apartment_id: int, payload: TariffSettingUpsert, db: Session = Depends(get_db)):
    _legacy_api_disabled("PUT /admin/apartments/{apartment_id}/tariffs/settings")
    raise AssertionError("unreachable")
