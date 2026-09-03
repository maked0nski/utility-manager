# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_admin_user, require_write_access
from app.db.session import get_db
from app.services.billing import generate_invoice
from app.models import AdminUser, Apartment, BillingChangeLog, BillingLock, BillingMonthSnapshot, BillingStatement, BillingStatementStatus, Invoice
from app.schemas import BillingChangeLogOut, BillingGenerateRequest, BillingLockRequest, BillingMonthReopenRequest, BillingMonthReopenResultOut, BillingMonthSnapshotOut, BillingPeriodActionResultOut, BillingRecalculateRequest, BillingStatementOut, BillingStatementPrepareRequest, BillingStatementSendRequest, InvoiceOut
import json
from ._shared import _build_month_snapshot, _future_locked_periods, _log_billing_change, _mark_snapshot_reopened, _period_label, _prepare_billing_statement, _recalc_from_period, _snapshot_out, _statement_out

router = APIRouter()


@router.post("/billing/generate", response_model=InvoiceOut, dependencies=[Depends(require_write_access)])
def generate_billing(payload: BillingGenerateRequest, db: Session = Depends(get_db)):
    try:
        return generate_invoice(db, payload.apartment_id, payload.year, payload.month)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@router.post("/billing/recalculate", response_model=BillingPeriodActionResultOut, dependencies=[Depends(require_write_access)])
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
    recalculated_periods = _recalc_from_period(db, payload.apartment_id, payload.year, payload.month)
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="month_recalculated",
        entity_type="invoice",
        details={"recalculated_periods": [_period_label(year, month) for year, month in recalculated_periods]},
    )
    db.commit()
    return {
        "status": "recalculated",
        "recalculated_count": len(recalculated_periods),
        "recalculated_periods": [
            {
                "year": year,
                "month": month,
                "label": _period_label(year, month),
                "reason": f"Перераховано від {_period_label(payload.year, payload.month)}",
            }
            for year, month in recalculated_periods
        ],
    }

@router.post("/billing/lock", response_model=BillingPeriodActionResultOut, dependencies=[Depends(require_write_access)])
def lock_billing_month(
    payload: BillingLockRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
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
    snapshot = _build_month_snapshot(
        db,
        payload.apartment_id,
        payload.year,
        payload.month,
        confirmed_by=user.username,
    )
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
    recalculated_periods = _recalc_from_period(db, payload.apartment_id, payload.year, payload.month)
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="month_locked",
        entity_type="billing_lock",
        details={
            "snapshot_id": snapshot.id if snapshot.id else None,
            "opening_balance": str(snapshot.opening_balance),
            "month_total": str(snapshot.month_total),
            "payments_in_month": str(snapshot.payments_in_month),
            "closing_balance": str(snapshot.closing_balance),
            "recalculated_periods": [_period_label(year, month) for year, month in recalculated_periods],
        },
    )
    db.commit()
    return {
        "status": "locked",
        "recalculated_count": len(recalculated_periods),
        "recalculated_periods": [
            {
                "year": year,
                "month": month,
                "label": _period_label(year, month),
                "reason": f"Підтверджено і перераховано від {_period_label(payload.year, payload.month)}",
            }
            for year, month in recalculated_periods
        ],
    }

@router.post("/billing/unlock", response_model=BillingMonthReopenResultOut, dependencies=[Depends(require_write_access)])
def unlock_billing_month(
    payload: BillingMonthReopenRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")

    affected_periods: list[dict[str, int | str]] = []
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
    snapshot = db.scalar(
        select(BillingMonthSnapshot).where(
            BillingMonthSnapshot.apartment_id == payload.apartment_id,
            BillingMonthSnapshot.year == payload.year,
            BillingMonthSnapshot.month == payload.month,
        )
    )
    _mark_snapshot_reopened(snapshot, reopened_by=user.username, reason=payload.reason)
    affected_periods.append(
        {
            "year": payload.year,
            "month": payload.month,
            "label": _period_label(payload.year, payload.month),
            "reason": payload.reason,
        }
    )
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="month_unlocked",
        entity_type="billing_lock",
        details={"reason": payload.reason, "snapshot_id": snapshot.id if snapshot else None},
    )

    future_locks = _future_locked_periods(db, payload.apartment_id, payload.year, payload.month)
    if future_locks:
        auto_reason = (
            f"Автоматично розблоковано після зміни періоду {_period_label(payload.year, payload.month)}"
        )
        snapshot_map = {
            (row.year, row.month): row
            for row in db.scalars(
                select(BillingMonthSnapshot).where(BillingMonthSnapshot.apartment_id == payload.apartment_id)
            ).all()
        }
        for future_lock in future_locks:
            db.delete(future_lock)
            future_snapshot = snapshot_map.get((future_lock.year, future_lock.month))
            _mark_snapshot_reopened(future_snapshot, reopened_by=user.username, reason=auto_reason)
            affected_periods.append(
                {
                    "year": future_lock.year,
                    "month": future_lock.month,
                    "label": _period_label(future_lock.year, future_lock.month),
                    "reason": auto_reason,
                }
            )
            _log_billing_change(
                db,
                apartment_id=payload.apartment_id,
                year=future_lock.year,
                month=future_lock.month,
                actor_username=user.username,
                action="month_unlocked_cascade",
                entity_type="billing_lock",
                details={
                    "reason": auto_reason,
                    "trigger_period": _period_label(payload.year, payload.month),
                    "snapshot_id": future_snapshot.id if future_snapshot else None,
                },
            )
    db.commit()
    return {
        "status": "unlocked",
        "reopened_periods": affected_periods,
        "reopened_count": len(affected_periods),
    }

@router.get("/billing/month-snapshots", response_model=BillingMonthSnapshotOut | None)
def get_billing_month_snapshot(
    apartment_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    snapshot = db.scalar(
        select(BillingMonthSnapshot).where(
            BillingMonthSnapshot.apartment_id == apartment_id,
            BillingMonthSnapshot.year == year,
            BillingMonthSnapshot.month == month,
        )
    )
    return _snapshot_out(snapshot)

@router.get("/billing/statements", response_model=list[BillingStatementOut])
def list_billing_statements(
    apartment_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    statements = db.scalars(
        select(BillingStatement)
        .where(BillingStatement.apartment_id == apartment_id)
        .where(BillingStatement.year == year)
        .where(BillingStatement.month == month)
        .order_by(BillingStatement.version.desc(), BillingStatement.id.desc())
    ).all()
    return [_statement_out(row) for row in statements if _statement_out(row) is not None]

@router.post("/billing/statements/prepare", response_model=BillingStatementOut, dependencies=[Depends(require_write_access)])
def prepare_billing_statement(
    payload: BillingStatementPrepareRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    if db.get(Apartment, payload.apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    statement = _prepare_billing_statement(
        db,
        payload.apartment_id,
        payload.year,
        payload.month,
        generated_by=user.username,
        generated_at=payload.generated_at,
        note=payload.note,
    )
    _log_billing_change(
        db,
        apartment_id=payload.apartment_id,
        year=payload.year,
        month=payload.month,
        actor_username=user.username,
        action="statement_prepared",
        entity_type="billing_statement",
        entity_id=statement.id,
        details={
            "version": statement.version,
            "generated_at": statement.generated_at.isoformat(),
            "balance_due_on_generated_at": str(statement.balance_due_on_generated_at),
        },
    )
    db.commit()
    db.refresh(statement)
    return _statement_out(statement)

@router.post("/billing/statements/{statement_id}/send", response_model=BillingStatementOut, dependencies=[Depends(require_write_access)])
def send_billing_statement(
    statement_id: int,
    payload: BillingStatementSendRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    statement = db.get(BillingStatement, statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Billing statement not found.")
    statement.status = BillingStatementStatus.sent
    statement.sent_at = datetime.now(UTC)
    statement.sent_channel = payload.sent_channel
    statement.sent_to = payload.sent_to
    statement.note = payload.note if payload.note is not None else statement.note
    _log_billing_change(
        db,
        apartment_id=statement.apartment_id,
        year=statement.year,
        month=statement.month,
        actor_username=user.username,
        action="statement_sent",
        entity_type="billing_statement",
        entity_id=statement.id,
        details={
            "version": statement.version,
            "sent_channel": statement.sent_channel,
            "sent_to": statement.sent_to,
        },
    )
    db.commit()
    db.refresh(statement)
    return _statement_out(statement)

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
