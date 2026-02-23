from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.auth import hash_password
from app.models import AdminUser

TEST_DB_PATH = Path("test_utility_manager.db")
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


def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    # Ensure idempotent test runs even if a previous DB file exists.
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


def test_v1_admin_and_tenant_flow():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    unique_code = f"A-{uuid4().hex[:8].upper()}"
    apartment = client.post(
        "/admin/apartments",
        json={"code": unique_code, "address": "Ivasiuka 12, apt 24"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant_access_code = f"TENANT-{uuid4().hex[:8].upper()}"
    tenant = client.post(
        "/admin/tenants",
        json={"full_name": "Ivan Petrenko", "phone": "+380501112233", "access_code": tenant_access_code},
        headers=headers,
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    tenancy = client.post(
        "/admin/tenancies",
        json={"apartment_id": apartment_id, "tenant_id": tenant_id, "start_date": "2026-01-01"},
        headers=headers,
    )
    assert tenancy.status_code == 201

    meter = client.post(
        "/admin/meters",
        json={
            "apartment_id": apartment_id,
            "service_name": "Електроенергія День",
            "utility_type": "electricity",
            "serial_number": "EM-001",
            "initial_reading": "1000",
            "installed_at": "2025-12-01",
        },
        headers=headers,
    )
    assert meter.status_code == 201
    meter_id = meter.json()["id"]

    tariff = client.post(
        "/admin/tariffs",
        json={
            "apartment_id": apartment_id,
            "service_name": "Електроенергія День",
            "charge_mode": "metered",
            "utility_type": "electricity",
            "price_per_unit": "4.5",
            "unit_name": "kWh",
            "effective_from": "2026-01-01",
        },
        headers=headers,
    )
    assert tariff.status_code == 201

    reading = client.post(
        "/admin/readings",
        json={"meter_id": meter_id, "year": 2026, "month": 1, "value": "1120"},
        headers=headers,
    )
    assert reading.status_code == 201

    invoice = client.post(
        "/admin/billing/generate",
        json={"apartment_id": apartment_id, "year": 2026, "month": 1},
        headers=headers,
    )
    assert invoice.status_code == 200
    assert invoice.json()["total_amount"] == "540.00"

    dashboard = client.get(f"/tenant/dashboard/{tenant_access_code}")
    assert dashboard.status_code == 200
    assert dashboard.json()["current_debt"] == "540.00"

    history = client.get(f"/tenant/history/{tenant_access_code}")
    assert history.status_code == 200
    assert len(history.json()["invoices"]) == 1


def test_apartment_delete_cleans_related_data():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Test delete address"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant_access_code = f"TENANT-{uuid4().hex[:8].upper()}"
    tenant = client.post(
        "/admin/tenants",
        json={"full_name": "Delete Candidate", "phone": "+380500000000", "access_code": tenant_access_code},
        headers=headers,
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    tenancy = client.post(
        "/admin/tenancies",
        json={"apartment_id": apartment_id, "tenant_id": tenant_id, "start_date": "2026-02-01"},
        headers=headers,
    )
    assert tenancy.status_code == 201

    tariff = client.post(
        "/admin/tariffs",
        json={
            "apartment_id": apartment_id,
            "service_name": "Квартплата",
            "charge_mode": "fixed",
            "utility_type": None,
            "price_per_unit": "100.00",
            "unit_name": "month",
            "effective_from": "2026-02-01",
        },
        headers=headers,
    )
    assert tariff.status_code == 201

    remove = client.delete(f"/admin/apartments/{apartment_id}", headers=headers)
    assert remove.status_code == 200
    assert remove.json()["status"] == "deleted"

    apartment_after = client.get("/admin/apartments", headers=headers)
    assert apartment_after.status_code == 200
    assert all(row["id"] != apartment_id for row in apartment_after.json())

    tenant_list = client.get("/admin/tenants", headers=headers)
    assert tenant_list.status_code == 200
    assert all(row["id"] != tenant_id for row in tenant_list.json())


def test_meter_update_and_delete_flow():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Meter settings address"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    meter = client.post(
        "/admin/meters",
        json={
            "apartment_id": apartment_id,
            "service_name": "Вода",
            "utility_type": "water",
            "serial_number": "W-001",
            "initial_reading": "12.5",
            "installed_at": "2026-01-01",
        },
        headers=headers,
    )
    assert meter.status_code == 201
    meter_id = meter.json()["id"]

    updated = client.put(
        f"/admin/meters/{meter_id}",
        json={
            "service_name": "Холодна вода",
            "utility_type": "water",
            "serial_number": "W-002",
            "initial_reading": "13.0",
            "installed_at": "2026-01-05",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["service_name"] == "Холодна вода"
    assert updated.json()["serial_number"] == "W-002"

    listed = client.get(f"/admin/apartments/{apartment_id}/meters", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == meter_id

    removed = client.delete(f"/admin/meters/{meter_id}", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["status"] == "deleted"

    listed_after = client.get(f"/admin/apartments/{apartment_id}/meters", headers=headers)
    assert listed_after.status_code == 200
    assert listed_after.json() == []


def test_meter_delete_conflict_when_bound_to_tariff():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Meter bound conflict address"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    meter = client.post(
        "/admin/meters",
        json={
            "apartment_id": apartment_id,
            "service_name": "Електроенергія день",
            "utility_type": "electricity",
            "serial_number": "E-409",
            "initial_reading": "0",
            "installed_at": "2026-01-01",
        },
        headers=headers,
    )
    assert meter.status_code == 201
    meter_id = meter.json()["id"]

    tariff = client.post(
        "/admin/tariffs",
        json={
            "apartment_id": apartment_id,
            "service_name": "Електроенергія день",
            "charge_mode": "metered",
            "utility_type": "electricity",
            "price_per_unit": "4.5",
            "unit_name": "kWh",
            "meter_id": meter_id,
            "meter_register": "total",
            "effective_from": "2026-01-01",
        },
        headers=headers,
    )
    assert tariff.status_code == 201

    remove = client.delete(f"/admin/meters/{meter_id}", headers=headers)
    assert remove.status_code == 409
    assert "used in tariffs" in remove.json()["detail"]
