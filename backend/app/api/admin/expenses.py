# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_admin_user, require_write_access
from app.db.session import get_db
from app.models import AdminUser, Apartment, MaintenanceRecord, OwnerCharge
from app.schemas import MaintenanceRecordCreate, MaintenanceRecordOut, MaintenanceRecordUpdate, OwnerChargeCreate, OwnerChargeOut, OwnerChargeUpdate
from ._shared import _log_billing_change

router = APIRouter()


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
