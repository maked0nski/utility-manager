from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import parse_token
from app.db.session import get_db
from app.models import AdminUser, Role


def get_current_admin_user(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = parse_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    username = payload.get("sub")
    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Admin user not found or disabled.")
    token_role = payload.get("role")
    if token_role != user.role.value:
        raise HTTPException(status_code=401, detail="Token role mismatch.")
    return user


def require_admin(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail="Admin role required.")
    return user


def require_write_access(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
    if user.role not in (Role.admin, Role.operator):
        raise HTTPException(status_code=403, detail="Write access required.")
    return user


def require_authenticated_admin(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
    return user
