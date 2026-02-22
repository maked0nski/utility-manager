from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Apartment, Invoice, Tenancy, Tenant
from app.schemas import TenantDashboard, TenantHistory

router = APIRouter()


def _resolve_current_tenancy(db: Session, tenant_id: int):
    tenancy = db.scalar(
        select(Tenancy)
        .where(Tenancy.tenant_id == tenant_id)
        .order_by(Tenancy.start_date.desc())
        .limit(1)
    )
    return tenancy


@router.get("/dashboard/{access_code}", response_model=TenantDashboard)
def dashboard(access_code: str, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.access_code == access_code))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    tenancy = _resolve_current_tenancy(db, tenant.id)
    if tenancy is None:
        raise HTTPException(status_code=404, detail="Tenant is not assigned to any apartment.")

    apartment = db.get(Apartment, tenancy.apartment_id)
    current_invoice = db.scalar(
        select(Invoice)
        .where(and_(Invoice.tenant_id == tenant.id, Invoice.apartment_id == apartment.id))
        .order_by(Invoice.year.desc(), Invoice.month.desc())
        .limit(1)
    )
    unpaid_total = Decimal(current_invoice.closing_balance) if current_invoice else Decimal("0.00")
    return TenantDashboard(
        tenant_id=tenant.id,
        tenant_name=tenant.full_name,
        apartment_code=apartment.code,
        apartment_address=apartment.address,
        current_debt=unpaid_total,
        current_invoice=current_invoice,
    )


@router.get("/history/{access_code}", response_model=TenantHistory)
def history(access_code: str, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.access_code == access_code))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    invoices = db.scalars(
        select(Invoice).where(Invoice.tenant_id == tenant.id).order_by(Invoice.year.desc(), Invoice.month.desc())
    ).all()
    return TenantHistory(invoices=invoices)
