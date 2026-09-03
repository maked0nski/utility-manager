# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_admin_user, require_write_access
from app.db.session import get_db
from app.models import AdminUser
from app.schemas import ServiceActivationUpdate, TariffApplyFromPeriod, TariffBindingUpdate, TariffCreate, TariffOut, TariffUpdate
from ._shared import _legacy_api_disabled

router = APIRouter()


@router.post("/tariffs", response_model=TariffOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_tariff(
    payload: TariffCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")

@router.put("/tariffs/{tariff_id}", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def update_tariff(
    tariff_id: int,
    payload: TariffUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")

@router.put("/tariffs/{tariff_id}/binding", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def update_tariff_binding(
    tariff_id: int,
    payload: TariffBindingUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")

@router.post("/tariffs/{tariff_id}/apply-from-period", response_model=TariffOut, dependencies=[Depends(require_write_access)])
def apply_tariff_from_period(
    tariff_id: int,
    payload: TariffApplyFromPeriod,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_admin_user),
):
    _legacy_api_disabled("Legacy tariff API")

@router.put("/apartments/{apartment_id}/services/{service_name}/activation", dependencies=[Depends(require_write_access)])
def update_service_activation(
    apartment_id: int,
    service_name: str,
    payload: ServiceActivationUpdate,
    db: Session = Depends(get_db),
):
    _legacy_api_disabled("Legacy service activation API")

@router.delete("/tariffs/{tariff_id}", dependencies=[Depends(require_write_access)])
def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(get_current_admin_user)
):
    _legacy_api_disabled("Legacy tariff API")
