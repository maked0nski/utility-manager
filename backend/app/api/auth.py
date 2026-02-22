import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_authenticated_admin
from app.core.auth import create_token, hash_password, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models import AdminUser, Role

router = APIRouter()
PASSWORD_ROTATION_DAYS = 90


class LoginPayload(BaseModel):
    username: str
    password: str


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: Role
    is_active: bool


class AdminUserCreatePayload(BaseModel):
    username: str
    password: str
    role: Role = Role.operator


class AdminUserRolePayload(BaseModel):
    role: Role
    is_active: bool = True


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must include at least one digit.")


@router.post("/admin/login")
def admin_login(payload: LoginPayload, db: Session = Depends(get_db)):
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    return {"access_token": create_token(user.username, user.role.value), "token_type": "bearer"}


@router.get("/admin/bootstrap-info")
def admin_bootstrap_info(db: Session = Depends(get_db)):
    user = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
    using_default = bool(
        user is not None
        and verify_password(settings.admin_password, user.password_hash)
        and user.username == settings.admin_username
    )
    password_rotation_recommended = bool(
        user is not None
        and user.password_changed_at is not None
        and datetime.now(UTC) - user.password_changed_at > timedelta(days=PASSWORD_ROTATION_DAYS)
        and not using_default
    )
    return {
        "username": settings.admin_username if using_default else None,
        "password": settings.admin_password if using_default else None,
        "must_change_password": using_default,
        "password_rotation_recommended": password_rotation_recommended,
    }


@router.post("/admin/change-password")
def admin_change_password(
    payload: ChangePasswordPayload,
    current_user: AdminUser = Depends(require_authenticated_admin),
    db: Session = Depends(get_db),
):
    _validate_password_strength(payload.new_password)
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.password_changed_at = datetime.now(UTC)
    db.commit()
    return {"status": "password_changed"}


@router.get("/admin/users", response_model=list[AdminUserOut])
def list_admin_users(_: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdminUser).order_by(AdminUser.username)).all()
    return [AdminUserOut(id=x.id, username=x.username, role=x.role, is_active=x.is_active) for x in rows]


@router.post("/admin/users", response_model=AdminUserOut)
def create_admin_user(payload: AdminUserCreatePayload, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    _validate_password_strength(payload.password)
    user = AdminUser(username=payload.username.strip(), password_hash=hash_password(payload.password), role=payload.role, is_active=True)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists.")
    db.refresh(user)
    return AdminUserOut(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


@router.put("/admin/users/{user_id}", response_model=AdminUserOut)
def update_admin_user_role(
    user_id: int,
    payload: AdminUserRolePayload,
    current_user: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Admin user not found.")
    if user.username == current_user.username and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot disable yourself.")
    user.role = payload.role
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return AdminUserOut(id=user.id, username=user.username, role=user.role, is_active=user.is_active)
