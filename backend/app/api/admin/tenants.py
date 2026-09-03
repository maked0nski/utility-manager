# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_write_access
from app.core.auth import hash_password
from app.db.session import get_db
from app.models import Apartment, ContractExtensionType, Invoice, RentLedger, RentalContract, Tenancy, Tenant, TenantContact, TenantPhone, UtilityPayment
from app.schemas import TenancyCreate, TenancyOut, TenantCreate, TenantOut, TenantUpdate
from ._shared import CONTRACT_SCAN_DIR, TENANT_PHOTO_DIR, _tenant_out, _validate_tenant_password_strength

router = APIRouter()


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    tenant = Tenant(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        password_hash=None,
        portal_enabled=False,
        can_submit_meter_readings=False,
        access_code=payload.access_code,
    )
    db.add(tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant access code or email already exists.")
    db.refresh(tenant)
    return _tenant_out(tenant)

@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    tenants = db.scalars(select(Tenant).order_by(Tenant.full_name)).all()
    return [_tenant_out(tenant) for tenant in tenants]

@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return _tenant_out(tenant)

@router.put("/tenants/{tenant_id}", response_model=TenantOut, dependencies=[Depends(require_write_access)])
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    tenant.full_name = payload.full_name
    tenant.phone = payload.primary_phone
    tenant.email = payload.email
    tenant.bank_statement_name = payload.bank_statement_name
    tenant.rent_amount = payload.rent_amount
    tenant.rent_currency = payload.rent_currency
    tenant.passport_number = payload.passport_number
    tenant.passport_issued_by = payload.passport_issued_by
    tenant.passport_issue_date = payload.passport_issue_date
    tenant.passport_expiry_date = payload.passport_expiry_date
    if payload.portal_enabled is not None:
        tenant.portal_enabled = payload.portal_enabled
    if payload.can_submit_meter_readings is not None:
        tenant.can_submit_meter_readings = payload.can_submit_meter_readings
    if payload.portal_password:
        _validate_tenant_password_strength(payload.portal_password)
        tenant.password_hash = hash_password(payload.portal_password)

    for row in list(tenant.phones):
        db.delete(row)
    for row in list(tenant.contacts):
        db.delete(row)
    for phone in payload.phones:
        if phone.strip():
            db.add(TenantPhone(tenant_id=tenant.id, phone=phone.strip()))
    for c in payload.contacts:
        db.add(TenantContact(tenant_id=tenant.id, name=c.name, relation=c.relation, phone=c.phone, note=c.note))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant email already exists.")
    db.refresh(tenant)
    return _tenant_out(tenant)

@router.delete("/tenants/{tenant_id}", dependencies=[Depends(require_write_access)])
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    has_links = (
        db.scalar(select(Tenancy.id).where(Tenancy.tenant_id == tenant_id).limit(1)) is not None
        or db.scalar(select(Invoice.id).where(Invoice.tenant_id == tenant_id).limit(1)) is not None
        or db.scalar(select(UtilityPayment.id).where(UtilityPayment.tenant_id == tenant_id).limit(1)) is not None
        or db.scalar(select(RentLedger.id).where(RentLedger.tenant_id == tenant_id).limit(1)) is not None
    )
    if has_links:
        raise HTTPException(
            status_code=409,
            detail="Tenant has linked records. Finish tenancy and keep history instead of deleting.",
        )
    db.delete(tenant)
    db.commit()
    return {"status": "deleted"}

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
