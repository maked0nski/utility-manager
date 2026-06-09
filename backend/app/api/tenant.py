from datetime import UTC, datetime
from decimal import Decimal
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_user
from app.core.auth import create_token, hash_password, parse_token, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models import Apartment, Invoice, Meter, MeterReading, Tenancy, Tenant, TenantPhone, UtilityPayment, UtilityType
from app.schemas import (
    MeterOut,
    ReadingCreate,
    ReadingOut,
    TenantChangePasswordPayload,
    TenantDashboard,
    TenantHistory,
    TenantLoginPayload,
    TenantMeOut,
    TenantPasswordResetPayload,
    TenantPasswordResetResult,
    TenantProfileUpdate,
    TenantRefreshPayload,
    TenantSessionOut,
)
from app.services.billing import _resolve_previous_reading_by_register

router = APIRouter()


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must include at least one digit.")


def _resolve_current_tenancy(db: Session, tenant_id: int):
    tenancy = db.scalar(
        select(Tenancy)
        .where(Tenancy.tenant_id == tenant_id)
        .order_by(Tenancy.start_date.desc())
        .limit(1)
    )
    return tenancy


def _meter_display_name(meter: Meter | None) -> str:
    if meter is None:
        return "Лічильник"
    if meter.meter_type and (meter.meter_type.name or "").strip():
        return meter.meter_type.name.strip()
    return {
        UtilityType.electricity: "Електролічильник",
        UtilityType.water: "Лічильник води",
        UtilityType.gas: "Газовий лічильник",
        UtilityType.heating: "Лічильник опалення",
        UtilityType.sewage: "Лічильник водовідведення",
        UtilityType.internet: "Інтернет-лічильник",
        UtilityType.other: "Лічильник",
    }.get(meter.utility_type, "Лічильник")


def _meter_out(meter: Meter) -> MeterOut:
    return MeterOut(
        id=meter.id,
        apartment_id=meter.apartment_id,
        meter_type_id=meter.meter_type_id,
        meter_type_name=meter.meter_type.name if meter.meter_type else None,
        display_name=_meter_display_name(meter),
        utility_type=meter.utility_type,
        serial_number=meter.serial_number,
        initial_reading=Decimal(meter.initial_reading),
        installed_at=meter.installed_at,
        retired_at=meter.retired_at,
        replaced_by_meter_id=meter.replaced_by_meter_id,
        is_active=meter.is_active,
    )


def _build_dashboard(db: Session, tenant: Tenant) -> TenantDashboard:
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
    latest_payment = db.scalar(
        select(UtilityPayment)
        .where(and_(UtilityPayment.tenant_id == tenant.id, UtilityPayment.apartment_id == apartment.id))
        .order_by(UtilityPayment.paid_at.desc(), UtilityPayment.id.desc())
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
        latest_payment_amount=(Decimal(latest_payment.amount) if latest_payment else None),
        latest_payment_date=(latest_payment.paid_at if latest_payment else None),
    )


@router.post("/login", response_model=TenantSessionOut)
def tenant_login(payload: TenantLoginPayload, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.email == payload.email.strip().lower()))
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not tenant.portal_enabled or not tenant.password_hash:
        raise HTTPException(status_code=403, detail="Tenant portal is disabled.")
    if not verify_password(payload.password, tenant.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    return TenantSessionOut(
        access_token=create_token(
            f"tenant:{tenant.id}",
            "tenant",
            ttl_seconds=settings.tenant_access_token_ttl_seconds,
            token_type="access",
            session_version=tenant.session_version,
        ),
        refresh_token=create_token(
            f"tenant:{tenant.id}",
            "tenant",
            ttl_seconds=settings.tenant_refresh_token_ttl_seconds,
            token_type="refresh",
            session_version=tenant.session_version,
        ),
        expires_in=settings.tenant_access_token_ttl_seconds,
    )


@router.post("/refresh", response_model=TenantSessionOut)
def tenant_refresh(payload: TenantRefreshPayload, db: Session = Depends(get_db)):
    try:
        token_payload = parse_token(payload.refresh_token.strip())
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if token_payload.get("role") != "tenant":
        raise HTTPException(status_code=401, detail="Tenant token required.")
    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required.")

    subject = str(token_payload.get("sub") or "")
    if not subject.startswith("tenant:"):
        raise HTTPException(status_code=401, detail="Invalid tenant token subject.")
    try:
        tenant_id = int(subject.split(":", 1)[1])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid tenant token subject.") from exc

    tenant = db.get(Tenant, tenant_id)
    if tenant is None or not tenant.portal_enabled:
        raise HTTPException(status_code=403, detail="Tenant portal is disabled.")
    token_session_version = int(token_payload.get("session_version") or 1)
    if token_session_version != int(tenant.session_version or 1):
        raise HTTPException(status_code=401, detail="Tenant session is no longer valid.")

    return TenantSessionOut(
        access_token=create_token(
            f"tenant:{tenant.id}",
            "tenant",
            ttl_seconds=settings.tenant_access_token_ttl_seconds,
            token_type="access",
            session_version=tenant.session_version,
        ),
        refresh_token=create_token(
            f"tenant:{tenant.id}",
            "tenant",
            ttl_seconds=settings.tenant_refresh_token_ttl_seconds,
            token_type="refresh",
            session_version=tenant.session_version,
        ),
        expires_in=settings.tenant_access_token_ttl_seconds,
    )


def _reset_tenant_password(payload: TenantPasswordResetPayload, db: Session) -> TenantPasswordResetResult:
    email = payload.email.strip().lower()
    access_code = payload.access_code.strip()
    tenant = db.scalar(select(Tenant).where(Tenant.email == email))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    if not tenant.portal_enabled:
        raise HTTPException(status_code=403, detail="Tenant portal is disabled.")
    if tenant.access_code != access_code:
        raise HTTPException(status_code=403, detail="Invalid access code.")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match.")
    _validate_password_strength(payload.new_password)
    tenant.password_hash = hash_password(payload.new_password)
    tenant.session_version = int(tenant.session_version or 1) + 1
    db.commit()
    return TenantPasswordResetResult(status="password_reset", session_revoked=True)


@router.post("/forgot-password", response_model=TenantPasswordResetResult)
def tenant_forgot_password(payload: TenantPasswordResetPayload, db: Session = Depends(get_db)):
    return _reset_tenant_password(payload, db)


@router.post("/password-reset", response_model=TenantPasswordResetResult)
def tenant_password_reset(payload: TenantPasswordResetPayload, db: Session = Depends(get_db)):
    return _reset_tenant_password(payload, db)


@router.get("/me", response_model=TenantMeOut)
def tenant_me(current_tenant: Tenant = Depends(get_current_tenant_user)):
    return TenantMeOut(
        id=current_tenant.id,
        full_name=current_tenant.full_name,
        email=current_tenant.email,
        phone=current_tenant.phone,
        phones=[row.phone for row in current_tenant.phones],
        portal_enabled=current_tenant.portal_enabled,
        can_submit_meter_readings=current_tenant.can_submit_meter_readings,
    )


@router.put("/me/profile", response_model=TenantMeOut)
def update_tenant_profile(
    payload: TenantProfileUpdate,
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    next_email = (payload.email or "").strip().lower() or None
    next_primary_phone = (payload.primary_phone or "").strip() or None
    normalized_phones = [x.strip() for x in (payload.phones or []) if x and x.strip()]
    if next_email and next_email != (current_tenant.email or "").lower():
        existing = db.scalar(select(Tenant).where(Tenant.email == next_email).where(Tenant.id != current_tenant.id))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already exists.")
    current_tenant.email = next_email
    current_tenant.phone = next_primary_phone
    for row in list(current_tenant.phones):
        db.delete(row)
    for phone in normalized_phones:
        db.add(TenantPhone(tenant_id=current_tenant.id, phone=phone))
    current_tenant.session_version = int(current_tenant.session_version or 1) + 1
    db.commit()
    db.refresh(current_tenant)
    return TenantMeOut(
        id=current_tenant.id,
        full_name=current_tenant.full_name,
        email=current_tenant.email,
        phone=current_tenant.phone,
        phones=[row.phone for row in current_tenant.phones],
        portal_enabled=current_tenant.portal_enabled,
        can_submit_meter_readings=current_tenant.can_submit_meter_readings,
    )


@router.put("/me/password")
def update_tenant_password(
    payload: TenantChangePasswordPayload,
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    if not current_tenant.password_hash:
        raise HTTPException(status_code=400, detail="Password is not set.")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match.")
    _validate_password_strength(payload.new_password)
    current_tenant.password_hash = hash_password(payload.new_password)
    current_tenant.session_version = int(current_tenant.session_version or 1) + 1
    db.commit()
    return {"status": "password_changed", "session_revoked": True}


@router.post("/me/logout-all")
def tenant_logout_all(
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    current_tenant.session_version = int(current_tenant.session_version or 1) + 1
    db.commit()
    return {"status": "logged_out_all_sessions"}


@router.get("/me/dashboard", response_model=TenantDashboard)
def tenant_dashboard_me(
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    return _build_dashboard(db, current_tenant)


@router.get("/me/history", response_model=TenantHistory)
def tenant_history_me(
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.tenant_id == current_tenant.id)
        .order_by(Invoice.year.desc(), Invoice.month.desc())
    ).all()
    return TenantHistory(invoices=invoices)


@router.get("/me/meters", response_model=list[MeterOut])
def tenant_meters_me(
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    tenancy = _resolve_current_tenancy(db, current_tenant.id)
    if tenancy is None:
        raise HTTPException(status_code=404, detail="Tenant is not assigned to any apartment.")
    meters = db.scalars(
        select(Meter)
        .where(Meter.apartment_id == tenancy.apartment_id)
        .order_by(Meter.is_active.desc(), Meter.id.asc())
    ).all()
    return [_meter_out(meter) for meter in meters]


@router.post("/me/readings", response_model=ReadingOut, status_code=status.HTTP_201_CREATED)
def submit_tenant_reading(
    payload: ReadingCreate,
    current_tenant: Tenant = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    if not current_tenant.can_submit_meter_readings:
        raise HTTPException(status_code=403, detail="Tenant cannot submit meter readings.")
    tenancy = _resolve_current_tenancy(db, current_tenant.id)
    if tenancy is None:
        raise HTTPException(status_code=404, detail="Tenant is not assigned to any apartment.")
    meter = db.get(Meter, payload.meter_id)
    if meter is None or meter.apartment_id != tenancy.apartment_id:
        raise HTTPException(status_code=404, detail="Meter not found for tenant apartment.")
    if meter.is_active is False:
        raise HTTPException(status_code=409, detail="Meter is archived.")
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
    row = db.scalar(
        select(MeterReading).where(
            and_(
                MeterReading.meter_id == payload.meter_id,
                MeterReading.register_name == payload.register_name,
                MeterReading.year == payload.year,
                MeterReading.month == payload.month,
            )
        )
    )
    if row is None:
        row = MeterReading(
            meter_id=payload.meter_id,
            register_name=payload.register_name,
            year=payload.year,
            month=payload.month,
            value=payload.value,
            created_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.value = payload.value
    db.commit()
    db.refresh(row)
    return row


@router.get("/dashboard/{access_code}", response_model=TenantDashboard)
def dashboard(access_code: str, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.access_code == access_code))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return _build_dashboard(db, tenant)


@router.get("/history/{access_code}", response_model=TenantHistory)
def history(access_code: str, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.access_code == access_code))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    invoices = db.scalars(
        select(Invoice).where(Invoice.tenant_id == tenant.id).order_by(Invoice.year.desc(), Invoice.month.desc())
    ).all()
    return TenantHistory(invoices=invoices)
