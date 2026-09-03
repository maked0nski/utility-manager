# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_write_access
from app.core.config import settings
from app.db.session import get_db
from app.models import Apartment, ApartmentEquipment, BillingChangeLog, BillingLock, Invoice, MaintenanceRecord, Meter, OwnerCharge, ProviderImportBatch, ProviderImportRow, RentLedger, ServiceLedgerEntry, Tenancy, Tenant, UtilityPayment
from app.schemas import ApartmentCreate, ApartmentEquipmentCreate, ApartmentEquipmentOut, ApartmentEquipmentUpdate, ApartmentOut
from ._shared import _apply_apartment_profile, _compose_full_apartment_address, _generate_apartment_code

router = APIRouter()


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
    full_address = _compose_full_apartment_address(payload)
    apartment = Apartment(code=code or _generate_apartment_code(db, full_address or "APT"), address=full_address)
    _apply_apartment_profile(apartment, payload)
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
    _apply_apartment_profile(apartment, payload)
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
    tenant_ids.update(
        tenant_id
        for tenant_id in db.scalars(select(UtilityPayment.tenant_id).where(UtilityPayment.apartment_id == apartment_id)).all()
        if tenant_id is not None
    )
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
    for row in db.scalars(select(OwnerCharge).where(OwnerCharge.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(ApartmentEquipment).where(ApartmentEquipment.apartment_id == apartment_id)).all():
        db.delete(row)
    for row in db.scalars(select(ServiceLedgerEntry).where(ServiceLedgerEntry.apartment_id == apartment_id)).all():
        db.delete(row)
    for batch in db.scalars(select(ProviderImportBatch).where(ProviderImportBatch.apartment_id == apartment_id)).all():
        for import_row in db.scalars(select(ProviderImportRow).where(ProviderImportRow.batch_id == batch.id)).all():
            db.delete(import_row)
        db.delete(batch)
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

@router.get("/apartments/{apartment_id}/equipment", response_model=list[ApartmentEquipmentOut])
def list_apartment_equipment(apartment_id: int, db: Session = Depends(get_db)):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    return db.scalars(
        select(ApartmentEquipment)
        .where(ApartmentEquipment.apartment_id == apartment_id)
        .order_by(ApartmentEquipment.name, ApartmentEquipment.id)
    ).all()

@router.post(
    "/apartments/{apartment_id}/equipment",
    response_model=ApartmentEquipmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def create_apartment_equipment(
    apartment_id: int,
    payload: ApartmentEquipmentCreate,
    db: Session = Depends(get_db),
):
    if db.get(Apartment, apartment_id) is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    row = ApartmentEquipment(apartment_id=apartment_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@router.put(
    "/apartments/{apartment_id}/equipment/{equipment_id}",
    response_model=ApartmentEquipmentOut,
    dependencies=[Depends(require_write_access)],
)
def update_apartment_equipment(
    apartment_id: int,
    equipment_id: int,
    payload: ApartmentEquipmentUpdate,
    db: Session = Depends(get_db),
):
    row = db.get(ApartmentEquipment, equipment_id)
    if row is None or row.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Equipment not found.")
    data = payload.model_dump()
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row

@router.delete(
    "/apartments/{apartment_id}/equipment/{equipment_id}",
    dependencies=[Depends(require_write_access)],
)
def delete_apartment_equipment(
    apartment_id: int,
    equipment_id: int,
    db: Session = Depends(get_db),
):
    row = db.get(ApartmentEquipment, equipment_id)
    if row is None or row.apartment_id != apartment_id:
        raise HTTPException(status_code=404, detail="Equipment not found.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}
