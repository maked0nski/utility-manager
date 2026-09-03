# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import UTC, date, datetime
from calendar import monthrange
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select, text
from sqlalchemy.orm import Session
from app.api.deps import get_current_admin_user, require_write_access
from app.db.session import get_db
from app.services.billing import generate_invoice
from app.models import AdminUser, Apartment, Invoice, RentLedger, ServiceLedgerEntry, Tenant, UtilityPayment
from app.schemas import RentRecordUpsert, ServiceLedgerRowOut, ServiceLedgerUpsert, UtilityPaymentCreate, UtilityPaymentOut, UtilityPaymentUpdate
from ._shared import _active_tenancy, _log_billing_change, _month_key, _period_from_date, _recalc_from_period, _recalc_service_ledger_from_period, _sync_invoice_payment_totals

router = APIRouter()


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
