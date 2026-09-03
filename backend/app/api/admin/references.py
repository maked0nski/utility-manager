# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_write_access
from app.db.session import get_db
from app.models import ApartmentAutomation, ApartmentServiceConnection, AutomationTemplate, Meter, MeterType, Provider, ServiceCatalog
from app.schemas import MeterTypeCreate, MeterTypeOut, MeterTypeUpdate, ProviderCreate, ProviderOut, ProviderUpdate, ServiceCatalogCreate, ServiceCatalogOut, ServiceCatalogUpdate
from ._shared import _slugify_meter_type_code

router = APIRouter()


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)):
    return db.scalars(select(Provider).order_by(Provider.name_full)).all()

@router.get("/service-catalog", response_model=list[ServiceCatalogOut])
def list_service_catalog(db: Session = Depends(get_db)):
    return db.scalars(select(ServiceCatalog).order_by(ServiceCatalog.display_order, ServiceCatalog.name)).all()

@router.post("/service-catalog", response_model=ServiceCatalogOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_service_catalog_item(payload: ServiceCatalogCreate, db: Session = Depends(get_db)):
    if payload.derived_from_service_id and db.get(ServiceCatalog, payload.derived_from_service_id) is None:
        raise HTTPException(status_code=404, detail="Derived source service not found.")
    row = ServiceCatalog(
        code=payload.code.strip(),
        name=payload.name.strip(),
        calculation_kind=payload.calculation_kind,
        unit_name=payload.unit_name,
        requires_meter=payload.requires_meter,
        allowed_meter_utility_type=payload.allowed_meter_utility_type,
        default_provider_utility_type=payload.default_provider_utility_type,
        derived_from_service_id=payload.derived_from_service_id,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service with this code or name already exists.")
    db.refresh(row)
    return row

@router.put("/service-catalog/{service_catalog_id}", response_model=ServiceCatalogOut, dependencies=[Depends(require_write_access)])
def update_service_catalog_item(service_catalog_id: int, payload: ServiceCatalogUpdate, db: Session = Depends(get_db)):
    row = db.get(ServiceCatalog, service_catalog_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Service catalog item not found.")
    if payload.derived_from_service_id == service_catalog_id:
        raise HTTPException(status_code=422, detail="Service cannot derive from itself.")
    if payload.derived_from_service_id and db.get(ServiceCatalog, payload.derived_from_service_id) is None:
        raise HTTPException(status_code=404, detail="Derived source service not found.")
    row.code = payload.code.strip()
    row.name = payload.name.strip()
    row.calculation_kind = payload.calculation_kind
    row.unit_name = payload.unit_name
    row.requires_meter = payload.requires_meter
    row.allowed_meter_utility_type = payload.allowed_meter_utility_type
    row.default_provider_utility_type = payload.default_provider_utility_type
    row.derived_from_service_id = payload.derived_from_service_id
    row.display_order = payload.display_order
    row.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service with this code or name already exists.")
    db.refresh(row)
    return row

@router.delete("/service-catalog/{service_catalog_id}", dependencies=[Depends(require_write_access)])
def delete_service_catalog_item(service_catalog_id: int, db: Session = Depends(get_db)):
    row = db.get(ServiceCatalog, service_catalog_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Service catalog item not found.")
    in_use = db.scalar(
        select(ApartmentServiceConnection.id).where(ApartmentServiceConnection.service_catalog_id == service_catalog_id).limit(1)
    )
    in_use = in_use or db.scalar(
        select(ServiceCatalog.id).where(ServiceCatalog.derived_from_service_id == service_catalog_id).limit(1)
    )
    if in_use is not None:
        raise HTTPException(
            status_code=409,
            detail="Послуга вже підключена до об'єкта або використовується як джерело для іншої послуги. "
            "Видалення заблоковано, щоб не зачепити попередні розрахунки — вимкніть \"Активна послуга\" в редагуванні, "
            "щоб прибрати її з нових підключень.",
        )
    db.delete(row)
    db.commit()
    return {"status": "deleted"}

@router.get("/meter-types", response_model=list[MeterTypeOut])
def list_meter_types(db: Session = Depends(get_db)):
    return db.scalars(select(MeterType).order_by(MeterType.sort_order, MeterType.name)).all()

@router.post("/meter-types", response_model=MeterTypeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_meter_type(payload: MeterTypeCreate, db: Session = Depends(get_db)):
    clean_name = payload.name.strip()
    row = MeterType(
        code=(payload.code.strip() if payload.code else _slugify_meter_type_code(clean_name)),
        name=clean_name,
        utility_type=payload.utility_type,
        default_service_name=clean_name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meter type with this code or name already exists.")
    db.refresh(row)
    return row

@router.put("/meter-types/{meter_type_id}", response_model=MeterTypeOut, dependencies=[Depends(require_write_access)])
def update_meter_type(meter_type_id: int, payload: MeterTypeUpdate, db: Session = Depends(get_db)):
    row = db.get(MeterType, meter_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Meter type not found.")
    clean_name = payload.name.strip()
    row.code = payload.code.strip() if payload.code else row.code
    row.name = clean_name
    row.utility_type = payload.utility_type
    row.default_service_name = clean_name
    row.sort_order = payload.sort_order
    row.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meter type with this code or name already exists.")
    db.refresh(row)
    return row

@router.delete("/meter-types/{meter_type_id}", dependencies=[Depends(require_write_access)])
def delete_meter_type(meter_type_id: int, db: Session = Depends(get_db)):
    row = db.get(MeterType, meter_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Meter type not found.")
    in_use = db.scalar(select(Meter.id).where(Meter.meter_type_id == meter_type_id).limit(1))
    if in_use is not None:
        raise HTTPException(
            status_code=409,
            detail="Тип лічильника вже використовується в одному з лічильників. "
            "Видалення заблоковано, щоб не зачепити попередні розрахунки — вимкніть \"Активний тип\" в редагуванні, "
            "щоб прибрати його з нових лічильників.",
        )
    db.delete(row)
    db.commit()
    return {"status": "deleted"}

@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    row = Provider(
        name_full=payload.name_full.strip(),
        utility_type=payload.utility_type,
        provider_kind=payload.provider_kind,
        adapter_code=(payload.adapter_code or "manual_stub").strip(),
        is_active=payload.is_active,
        note=payload.note,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Provider with this name already exists.")
    db.refresh(row)
    return row

@router.put("/providers/{provider_id}", response_model=ProviderOut, dependencies=[Depends(require_write_access)])
def update_provider(provider_id: int, payload: ProviderUpdate, db: Session = Depends(get_db)):
    row = db.get(Provider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row.name_full = payload.name_full.strip()
    row.utility_type = payload.utility_type
    row.provider_kind = payload.provider_kind
    row.adapter_code = (payload.adapter_code or "manual_stub").strip()
    row.is_active = payload.is_active
    row.note = payload.note
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Provider with this name already exists.")
    db.refresh(row)
    return row

@router.delete("/providers/{provider_id}", dependencies=[Depends(require_write_access)])
def delete_provider(provider_id: int, db: Session = Depends(get_db)):
    row = db.get(Provider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    in_use = db.scalar(
        select(ApartmentAutomation.id).where(ApartmentAutomation.provider_id == provider_id).limit(1)
    )
    in_use = in_use or db.scalar(
        select(AutomationTemplate.id).where(AutomationTemplate.provider_id == provider_id).limit(1)
    )
    in_use = in_use or db.scalar(
        select(ApartmentServiceConnection.id).where(ApartmentServiceConnection.provider_id == provider_id).limit(1)
    )
    if in_use is not None:
        raise HTTPException(
            status_code=409,
            detail="Постачальник вже використовується у підключеннях або автоматизаціях. "
            "Видалення заблоковано, щоб не зачепити попередні розрахунки — вимкніть \"Активний постачальник\" в редагуванні, "
            "щоб прибрати його з нових підключень.",
        )
    db.delete(row)
    db.commit()
    return {"status": "deleted"}
