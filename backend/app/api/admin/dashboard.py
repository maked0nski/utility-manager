# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import date
from calendar import monthrange
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import Apartment, ApartmentServiceConnection, BillingMonthSnapshot, BillingStatement, ChargeLineKind, ChargeMode, Invoice, RentLedger, Tenant, UtilityPayment
from app.schemas import ApartmentDetailOut, ApartmentOverviewOut, BalanceExplainOut, BillingPeriodSummaryOut, LiveBalanceSummaryOut, MissingServiceOut, RentMonthOut
from ._shared import _active_tenancy, _actual_current_utility_balance, _build_month_snapshot, _build_period_rows, _confirmed_previous_utility_debt, _default_period, _effective_utility_period, _is_month_locked, _payments_received_between, _snapshot_out, _statement_out, _tenant_out

router = APIRouter()


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
    snapshot = db.scalar(
        select(BillingMonthSnapshot).where(
            BillingMonthSnapshot.apartment_id == apartment_id,
            BillingMonthSnapshot.year == year,
            BillingMonthSnapshot.month == month,
        )
    )
    calc_locked = _is_month_locked(db, apartment_id, year, month)
    if snapshot is None and calc_locked:
        snapshot = _build_month_snapshot(db, apartment_id, year, month)
        db.commit()
        db.refresh(snapshot)
    statement_rows = db.scalars(
        select(BillingStatement)
        .where(BillingStatement.apartment_id == apartment_id)
        .where(BillingStatement.year == year)
        .where(BillingStatement.month == month)
        .order_by(BillingStatement.version.desc(), BillingStatement.id.desc())
    ).all()
    statement_outs = [item for item in (_statement_out(row) for row in statement_rows) if item is not None]

    month_charges_from_rows = sum((Decimal(r.amount) for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))
    current_balance_from_rows = (confirmed_previous_debt + month_charges_from_rows - month_payments).quantize(Decimal("0.01"))
    report_payments_to_date, report_payment_row = _payments_received_between(
        db,
        apartment_id=apartment_id,
        start_date=date(year, month, 1),
        end_date=report_generated_at,
    )
    report_balance = (confirmed_previous_debt + month_charges_from_rows - report_payments_to_date).quantize(Decimal("0.01"))
    latest_payment_row = db.scalar(
        select(UtilityPayment)
        .where(UtilityPayment.apartment_id == apartment_id)
        .order_by(UtilityPayment.paid_at.desc(), UtilityPayment.id.desc())
    )

    rent = db.scalar(select(RentLedger).where(and_(RentLedger.apartment_id == apartment_id, RentLedger.year == year, RentLedger.month == month)))
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
        cabinet_markup_percent=apartment.cabinet_markup_percent,
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
        live_balance_summary=LiveBalanceSummaryOut(
            current_balance=actual_current_balance,
            latest_payment_amount=Decimal(latest_payment_row.amount).quantize(Decimal("0.01")) if latest_payment_row else None,
            latest_payment_date=latest_payment_row.paid_at if latest_payment_row else None,
            latest_payment_note=latest_payment_row.note if latest_payment_row else None,
        ),
        billing_period_summary=BillingPeriodSummaryOut(
            month_snapshot=_snapshot_out(snapshot),
            current_statement=statement_outs[0] if statement_outs else None,
            statements=statement_outs,
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
