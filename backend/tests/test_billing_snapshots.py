from pathlib import Path
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.auth import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import (
    AdminUser,
    ApartmentServiceConnection,
    BillingLock,
    BillingMonthSnapshot,
    ChargeLineKind,
    ConnectionChargeLine,
    QuantitySource,
    ServiceCalculationKind,
    ServiceCatalog,
    UnitType,
)

TEST_DB_PATH = Path("test_billing_snapshots.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _reset_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(AdminUser(username="admin", password_hash=hash_password("admin123")))
    db.commit()
    db.close()


def teardown_module():
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def _login_headers():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_apartment_with_tenancy(headers, address: str) -> int:
    apartment = client.post("/admin/apartments", json={"address": address}, headers=headers)
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant = client.post(
        "/admin/tenants",
        json={"full_name": "Tenant Billing", "phone": "+380501111111", "access_code": f"TENANT-{address[:6]}"},
        headers=headers,
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    tenancy = client.post(
        "/admin/tenancies",
        json={"apartment_id": apartment_id, "tenant_id": tenant_id, "start_date": "2024-09-01"},
        headers=headers,
    )
    assert tenancy.status_code == 201
    return apartment_id


def _seed_fixed_service_connection(apartment_id: int) -> None:
    db = TestingSessionLocal()
    try:
        service = ServiceCatalog(
            code=f"fixed_test_{apartment_id}",
            name=f"Фіксована послуга {apartment_id}",
            calculation_kind=ServiceCalculationKind.fixed,
            unit_name=UnitType.month,
            requires_meter=False,
            display_order=1,
            is_active=True,
        )
        db.add(service)
        db.flush()

        connection = ApartmentServiceConnection(
            apartment_id=apartment_id,
            service_catalog_id=service.id,
            started_at=date(2024, 9, 1),
            status="active",
        )
        db.add(connection)
        db.flush()

        db.add(
            ConnectionChargeLine(
                connection_id=connection.id,
                line_kind=ChargeLineKind.fixed,
                label="Тестова фіксована лінія",
                unit_name=UnitType.month,
                price_per_unit=Decimal("100.00"),
                quantity_source=QuantitySource.fixed_1,
                quantity_multiplier=Decimal("1.000"),
                effective_from=date(2024, 9, 1),
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()


def test_unlock_cascades_future_confirmed_periods():
    _reset_db()
    headers = _login_headers()

    apartment_id = _seed_apartment_with_tenancy(headers, "Cascade Billing Test")
    _seed_fixed_service_connection(apartment_id)

    for month in (9, 10, 11):
        lock_response = client.post(
            "/admin/billing/lock",
            json={"apartment_id": apartment_id, "year": 2024, "month": month},
            headers=headers,
        )
        assert lock_response.status_code == 200

    unlock_response = client.post(
        "/admin/billing/unlock",
        json={
            "apartment_id": apartment_id,
            "year": 2024,
            "month": 9,
            "reason": "Потрібно виправити історичні дані",
        },
        headers=headers,
    )
    assert unlock_response.status_code == 200
    body = unlock_response.json()
    assert body["status"] == "unlocked"
    assert body["reopened_count"] == 3
    assert [item["label"] for item in body["reopened_periods"]] == ["09.2024", "10.2024", "11.2024"]

    db = TestingSessionLocal()
    try:
        remaining_locks = db.scalars(
            select(BillingLock).where(BillingLock.apartment_id == apartment_id).order_by(BillingLock.month.asc())
        ).all()
        assert remaining_locks == []

        snapshots = db.scalars(
            select(BillingMonthSnapshot)
            .where(BillingMonthSnapshot.apartment_id == apartment_id)
            .order_by(BillingMonthSnapshot.month.asc())
        ).all()
        assert len(snapshots) == 3
        assert all(row.status == "reopened" for row in snapshots)
        assert snapshots[0].reopen_reason == "Потрібно виправити історичні дані"
        assert snapshots[1].reopen_reason == "Автоматично розблоковано після зміни періоду 09.2024"
        assert snapshots[2].reopen_reason == "Автоматично розблоковано після зміни періоду 09.2024"
    finally:
        db.close()


def test_recalculate_starts_from_selected_period_only():
    _reset_db()
    headers = _login_headers()

    apartment_id = _seed_apartment_with_tenancy(headers, "Recalc Range Test")
    _seed_fixed_service_connection(apartment_id)

    for month in (9, 10, 11):
        generated = client.post(
            "/admin/billing/generate",
            json={"apartment_id": apartment_id, "year": 2024, "month": month},
            headers=headers,
        )
        assert generated.status_code == 200

    recalc_response = client.post(
        "/admin/billing/recalculate",
        json={"apartment_id": apartment_id, "year": 2024, "month": 10},
        headers=headers,
    )
    assert recalc_response.status_code == 200
    body = recalc_response.json()
    assert body["status"] == "recalculated"
    assert body["recalculated_count"] == 2
    assert [item["label"] for item in body["recalculated_periods"]] == ["10.2024", "11.2024"]
