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


def _tenant_update_payload(**overrides):
    payload = {
        "full_name": "Tenant",
        "primary_phone": "+380500000001",
        "email": "tenant@example.com",
        "phones": [],
        "contacts": [],
        "bank_statement_name": None,
        "rent_amount": None,
        "rent_currency": "UAH",
        "passport_number": None,
        "passport_issued_by": None,
        "passport_issue_date": None,
        "passport_expiry_date": None,
        "portal_enabled": True,
        "can_submit_meter_readings": True,
        "portal_password": None,
    }
    payload.update(overrides)
    return payload


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


def test_service_ledger_history_recalculates_balances_from_changed_month():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Ledger address"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]
    service_name = "kvartplata"

    jan = client.put(
        f"/admin/apartments/{apartment_id}/service-ledger/{service_name}",
        json={
            "year": 2026,
            "month": 1,
            "accrued": "334.50",
            "paid": "100.00",
            "adjustment": "0.00",
            "benefit": "0.00",
            "subsidy": "0.00",
        },
        headers=headers,
    )
    assert jan.status_code == 200
    assert jan.json()["opening_balance"] == "0.00"
    assert jan.json()["closing_balance"] == "234.50"

    feb = client.put(
        f"/admin/apartments/{apartment_id}/service-ledger/{service_name}",
        json={
            "year": 2026,
            "month": 2,
            "accrued": "656.48",
            "paid": "0.00",
            "adjustment": "0.00",
            "benefit": "0.00",
            "subsidy": "0.00",
        },
        headers=headers,
    )
    assert feb.status_code == 200
    assert feb.json()["opening_balance"] == "234.50"
    assert feb.json()["closing_balance"] == "890.98"

    jan_update = client.put(
        f"/admin/apartments/{apartment_id}/service-ledger/{service_name}",
        json={
            "year": 2026,
            "month": 1,
            "accrued": "334.50",
            "paid": "200.00",
            "adjustment": "0.00",
            "benefit": "0.00",
            "subsidy": "0.00",
        },
        headers=headers,
    )
    assert jan_update.status_code == 200
    assert jan_update.json()["closing_balance"] == "134.50"

    history = client.get(
        f"/admin/apartments/{apartment_id}/service-ledger/{service_name}/history?limit=12",
        headers=headers,
    )
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 2
    # Desc order: February first.
    assert rows[0]["year"] == 2026 and rows[0]["month"] == 2
    assert rows[0]["opening_balance"] == "134.50"
    assert rows[0]["closing_balance"] == "790.98"
    assert rows[1]["year"] == 2026 and rows[1]["month"] == 1


def test_apartment_passport_and_equipment_crud():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={
            "code": f"A-{uuid4().hex[:8].upper()}",
            "address": "Passport address",
            "area_m2": "66.50",
            "latitude": "48.9226",
            "longitude": "24.7111",
            "location_note": "Під'їзд 2",
            "object_notes": "Котел встановлено, перевірка щороку",
        },
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]
    assert apartment.json()["area_m2"] == "66.50"

    update = client.put(
        f"/admin/apartments/{apartment_id}",
        json={
            "address": "Passport address updated",
            "area_m2": "67.00",
            "latitude": "48.9227",
            "longitude": "24.7112",
            "location_note": "Під'їзд 1",
            "object_notes": "Оновлено",
        },
        headers=headers,
    )
    assert update.status_code == 200
    assert update.json()["area_m2"] == "67.00"
    assert update.json()["location_note"] == "Під'їзд 1"

    equipment = client.post(
        f"/admin/apartments/{apartment_id}/equipment",
        json={
            "name": "Котел",
            "category": "heating",
            "model_name": "Bosch 6000",
            "serial_number": "B-123",
            "installed_at": "2025-10-01",
            "manual_url": "https://example.com/manual",
            "service_interval_days": 365,
            "last_service_at": "2026-01-20",
            "next_service_at": "2027-01-20",
            "note": "Планова перевірка",
            "is_active": True,
        },
        headers=headers,
    )
    assert equipment.status_code == 201
    equipment_id = equipment.json()["id"]
    assert equipment.json()["name"] == "Котел"

    listed = client.get(f"/admin/apartments/{apartment_id}/equipment", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == equipment_id

    equipment_update = client.put(
        f"/admin/apartments/{apartment_id}/equipment/{equipment_id}",
        json={
            "name": "Котел",
            "category": "heating",
            "model_name": "Bosch 7000",
            "serial_number": "B-123",
            "installed_at": "2025-10-01",
            "manual_url": "https://example.com/manual-v2",
            "service_interval_days": 365,
            "last_service_at": "2026-02-01",
            "next_service_at": "2027-02-01",
            "note": "Оновлена планова перевірка",
            "is_active": True,
        },
        headers=headers,
    )
    assert equipment_update.status_code == 200
    assert equipment_update.json()["model_name"] == "Bosch 7000"

    equipment_delete = client.delete(
        f"/admin/apartments/{apartment_id}/equipment/{equipment_id}",
        headers=headers,
    )
    assert equipment_delete.status_code == 200
    assert equipment_delete.json()["status"] == "deleted"


def test_meter_replacement_creates_new_meter_and_keeps_history():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Meter replace address"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant = client.post(
        "/admin/tenants",
        json={"full_name": "Replace Tenant", "phone": "+380501111111", "access_code": f"T-{uuid4().hex[:8].upper()}"},
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
            "service_name": "Електроенергія",
            "utility_type": "electricity",
            "serial_number": "E-OLD",
            "initial_reading": "1000",
            "installed_at": "2026-01-01",
        },
        headers=headers,
    )
    assert meter.status_code == 201
    old_meter_id = meter.json()["id"]

    tariff = client.post(
        "/admin/tariffs",
        json={
            "apartment_id": apartment_id,
            "service_name": "Електроенергія",
            "charge_mode": "metered",
            "utility_type": "electricity",
            "price_per_unit": "4.50",
            "unit_name": "kWh",
            "meter_id": old_meter_id,
            "meter_register": "total",
            "effective_from": "2026-01-01",
        },
        headers=headers,
    )
    assert tariff.status_code == 201

    reading = client.post(
        "/admin/readings",
        json={"meter_id": old_meter_id, "year": 2026, "month": 2, "register_name": "total", "value": "1120"},
        headers=headers,
    )
    assert reading.status_code == 201

    replaced = client.post(
        f"/admin/meters/{old_meter_id}/replace",
        json={
            "serial_number": "E-NEW",
            "initial_reading": "0",
            "installed_at": "2026-03-01",
        },
        headers=headers,
    )
    assert replaced.status_code == 200
    new_meter_id = replaced.json()["id"]
    assert new_meter_id != old_meter_id
    assert replaced.json()["serial_number"] == "E-NEW"
    assert replaced.json()["is_active"] is True

    meters = client.get(f"/admin/apartments/{apartment_id}/meters", headers=headers)
    assert meters.status_code == 200
    rows = meters.json()
    assert len(rows) == 2
    old_row = next(x for x in rows if x["id"] == old_meter_id)
    new_row = next(x for x in rows if x["id"] == new_meter_id)
    assert old_row["is_active"] is False
    assert old_row["replaced_by_meter_id"] == new_meter_id
    assert old_row["retired_at"] == "2026-03-01"
    assert new_row["is_active"] is True

    tariffs_march = client.get(
        f"/admin/apartments/{apartment_id}/tariffs?year=2026&month=3",
        headers=headers,
    )
    assert tariffs_march.status_code == 200
    electricity = next(x for x in tariffs_march.json() if x["service_name"] == "Електроенергія")
    assert electricity["meter_id"] == new_meter_id


def test_electricity_plan_flow_dual_to_single():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Electricity plan address"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    meter = client.post(
        "/admin/meters",
        json={
            "apartment_id": apartment_id,
            "service_name": "Електролічильник",
            "utility_type": "electricity",
            "serial_number": "E-PLAN",
            "initial_reading": "0",
            "installed_at": "2026-01-01",
        },
        headers=headers,
    )
    assert meter.status_code == 201
    meter_id = meter.json()["id"]

    dual = client.put(
        f"/admin/apartments/{apartment_id}/electricity-plan",
        json={
            "plan_mode": "dual",
            "meter_id": meter_id,
            "effective_from": "2026-01-01",
            "day_price_per_unit": "4.50",
            "night_price_per_unit": "2.25",
        },
        headers=headers,
    )
    assert dual.status_code == 200

    tariffs_jan = client.get(
        f"/admin/apartments/{apartment_id}/tariffs?year=2026&month=1",
        headers=headers,
    )
    assert tariffs_jan.status_code == 200
    jan_rows = tariffs_jan.json()
    assert any(x["service_name"] == "Електроенергія денний тариф" and x["meter_register"] == "day" for x in jan_rows)
    assert any(x["service_name"] == "Електроенергія нічний тариф" and x["meter_register"] == "night" for x in jan_rows)

    single = client.put(
        f"/admin/apartments/{apartment_id}/electricity-plan",
        json={
            "plan_mode": "single",
            "meter_id": meter_id,
            "effective_from": "2026-03-01",
            "single_price_per_unit": "4.10",
        },
        headers=headers,
    )
    assert single.status_code == 200

    tariffs_march = client.get(
        f"/admin/apartments/{apartment_id}/tariffs?year=2026&month=3",
        headers=headers,
    )
    assert tariffs_march.status_code == 200
    march_rows = tariffs_march.json()
    single_row = next(x for x in march_rows if x["service_name"] == "Електроенергія")
    assert single_row["meter_register"] == "total"
    assert single_row["is_active_for_period"] is True
    day_row = next(x for x in march_rows if x["service_name"] == "Електроенергія денний тариф")
    night_row = next(x for x in march_rows if x["service_name"] == "Електроенергія нічний тариф")
    assert day_row["is_active_for_period"] is False
    assert night_row["is_active_for_period"] is False


def test_tenant_token_lifecycle_refresh_logout_and_revocation():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    admin_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Tenant auth apartment"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant = client.post(
        "/admin/tenants",
        json={
            "full_name": "Tenant Auth",
            "phone": "+380500000001",
            "email": "tenant-auth@example.com",
            "access_code": f"T-{uuid4().hex[:8].upper()}",
        },
        headers=headers,
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    tenant_update = client.put(
        f"/admin/tenants/{tenant_id}",
        json=_tenant_update_payload(
            full_name="Tenant Auth",
            primary_phone="+380500000001",
            email="tenant-auth@example.com",
            portal_enabled=True,
            can_submit_meter_readings=True,
            portal_password="StrongPass1",
        ),
        headers=headers,
    )
    assert tenant_update.status_code == 200

    tenancy = client.post(
        "/admin/tenancies",
        json={"apartment_id": apartment_id, "tenant_id": tenant_id, "start_date": "2026-01-01"},
        headers=headers,
    )
    assert tenancy.status_code == 201

    tenant_login = client.post(
        "/tenant/login",
        json={"email": "tenant-auth@example.com", "password": "StrongPass1"},
    )
    assert tenant_login.status_code == 200
    tenant_access_token = tenant_login.json()["access_token"]
    tenant_refresh_token = tenant_login.json()["refresh_token"]
    tenant_headers = {"Authorization": f"Bearer {tenant_access_token}"}

    refresh_ok = client.post("/tenant/refresh", json={"refresh_token": tenant_refresh_token})
    assert refresh_ok.status_code == 200
    assert "access_token" in refresh_ok.json()
    assert "refresh_token" in refresh_ok.json()

    logout_all = client.post("/tenant/me/logout-all", headers=tenant_headers)
    assert logout_all.status_code == 200

    refresh_after_logout = client.post("/tenant/refresh", json={"refresh_token": tenant_refresh_token})
    assert refresh_after_logout.status_code == 401
    assert "session" in refresh_after_logout.json()["detail"].lower()

    tenant_login2 = client.post(
        "/tenant/login",
        json={"email": "tenant-auth@example.com", "password": "StrongPass1"},
    )
    assert tenant_login2.status_code == 200
    tenant_access_token2 = tenant_login2.json()["access_token"]
    tenant_headers2 = {"Authorization": f"Bearer {tenant_access_token2}"}

    update_profile = client.put(
        "/tenant/me/profile",
        json={"email": "tenant-auth-updated@example.com"},
        headers=tenant_headers2,
    )
    assert update_profile.status_code == 200

    me_after_email_update = client.get("/tenant/me", headers=tenant_headers2)
    assert me_after_email_update.status_code == 401

    tenant_login3 = client.post(
        "/tenant/login",
        json={"email": "tenant-auth-updated@example.com", "password": "StrongPass1"},
    )
    assert tenant_login3.status_code == 200
    tenant_access_token3 = tenant_login3.json()["access_token"]
    tenant_headers3 = {"Authorization": f"Bearer {tenant_access_token3}"}

    change_password = client.put(
        "/tenant/me/password",
        json={"new_password": "StrongPass2", "confirm_password": "StrongPass2"},
        headers=tenant_headers3,
    )
    assert change_password.status_code == 200
    assert change_password.json()["session_revoked"] is True

    me_after_password_update = client.get("/tenant/me", headers=tenant_headers3)
    assert me_after_password_update.status_code == 401

    old_password_login = client.post(
        "/tenant/login",
        json={"email": "tenant-auth-updated@example.com", "password": "StrongPass1"},
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/tenant/login",
        json={"email": "tenant-auth-updated@example.com", "password": "StrongPass2"},
    )
    assert new_password_login.status_code == 200


def test_tenant_forgot_password_resets_password_and_revokes_old_sessions():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    admin_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    apartment = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Tenant forgot password apartment"},
        headers=headers,
    )
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant_access_code = f"T-{uuid4().hex[:8].upper()}"
    tenant = client.post(
        "/admin/tenants",
        json={
            "full_name": "Tenant Forgot Password",
            "phone": "+380500000021",
            "email": "tenant-reset@example.com",
            "access_code": tenant_access_code,
        },
        headers=headers,
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    tenant_update = client.put(
        f"/admin/tenants/{tenant_id}",
        json=_tenant_update_payload(
            full_name="Tenant Forgot Password",
            primary_phone="+380500000021",
            email="tenant-reset@example.com",
            portal_enabled=True,
            can_submit_meter_readings=True,
            portal_password="StrongPass1",
        ),
        headers=headers,
    )
    assert tenant_update.status_code == 200

    tenancy = client.post(
        "/admin/tenancies",
        json={"apartment_id": apartment_id, "tenant_id": tenant_id, "start_date": "2026-01-01"},
        headers=headers,
    )
    assert tenancy.status_code == 201

    tenant_login = client.post(
        "/tenant/login",
        json={"email": "tenant-reset@example.com", "password": "StrongPass1"},
    )
    assert tenant_login.status_code == 200
    old_access_token = tenant_login.json()["access_token"]

    forgot_password = client.post(
        "/tenant/forgot-password",
        json={
            "email": "tenant-reset@example.com",
            "access_code": tenant_access_code,
            "new_password": "StrongPass2",
            "confirm_password": "StrongPass2",
        },
    )
    assert forgot_password.status_code == 200
    assert forgot_password.json() == {"status": "password_reset", "session_revoked": True}

    me_after_reset = client.get("/tenant/me", headers={"Authorization": f"Bearer {old_access_token}"})
    assert me_after_reset.status_code == 401

    old_password_login = client.post(
        "/tenant/login",
        json={"email": "tenant-reset@example.com", "password": "StrongPass1"},
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/tenant/login",
        json={"email": "tenant-reset@example.com", "password": "StrongPass2"},
    )
    assert new_password_login.status_code == 200

    invalid_access_code = client.post(
        "/tenant/forgot-password",
        json={
            "email": "tenant-reset@example.com",
            "access_code": "WRONG-CODE",
            "new_password": "StrongPass3",
            "confirm_password": "StrongPass3",
        },
    )
    assert invalid_access_code.status_code == 403


def test_tenant_reading_api_conflict_and_not_found_and_forbidden():
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    admin_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    apartment_a = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Tenant reading apartment A"},
        headers=headers,
    )
    assert apartment_a.status_code == 201
    apartment_a_id = apartment_a.json()["id"]

    apartment_b = client.post(
        "/admin/apartments",
        json={"code": f"A-{uuid4().hex[:8].upper()}", "address": "Tenant reading apartment B"},
        headers=headers,
    )
    assert apartment_b.status_code == 201
    apartment_b_id = apartment_b.json()["id"]

    tenant = client.post(
        "/admin/tenants",
        json={
            "full_name": "Tenant Reading",
            "phone": "+380500000002",
            "email": "tenant-reading@example.com",
            "access_code": f"T-{uuid4().hex[:8].upper()}",
        },
        headers=headers,
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    tenant_update = client.put(
        f"/admin/tenants/{tenant_id}",
        json=_tenant_update_payload(
            full_name="Tenant Reading",
            primary_phone="+380500000002",
            email="tenant-reading@example.com",
            portal_enabled=True,
            can_submit_meter_readings=True,
            portal_password="StrongPass1",
        ),
        headers=headers,
    )
    assert tenant_update.status_code == 200

    tenancy = client.post(
        "/admin/tenancies",
        json={"apartment_id": apartment_a_id, "tenant_id": tenant_id, "start_date": "2026-01-01"},
        headers=headers,
    )
    assert tenancy.status_code == 201

    meter_a = client.post(
        "/admin/meters",
        json={
            "apartment_id": apartment_a_id,
            "service_name": "Вода",
            "utility_type": "water",
            "serial_number": "W-A",
            "initial_reading": "0",
            "installed_at": "2026-01-01",
        },
        headers=headers,
    )
    assert meter_a.status_code == 201
    meter_a_id = meter_a.json()["id"]

    meter_b = client.post(
        "/admin/meters",
        json={
            "apartment_id": apartment_b_id,
            "service_name": "Вода B",
            "utility_type": "water",
            "serial_number": "W-B",
            "initial_reading": "0",
            "installed_at": "2026-01-01",
        },
        headers=headers,
    )
    assert meter_b.status_code == 201
    meter_b_id = meter_b.json()["id"]

    tenant_login = client.post(
        "/tenant/login",
        json={"email": "tenant-reading@example.com", "password": "StrongPass1"},
    )
    assert tenant_login.status_code == 200
    tenant_headers = {"Authorization": f"Bearer {tenant_login.json()['access_token']}"}

    not_found = client.post(
        "/tenant/me/readings",
        json={"meter_id": meter_b_id, "year": 2026, "month": 2, "register_name": "total", "value": "12.5"},
        headers=tenant_headers,
    )
    assert not_found.status_code == 404
    assert "not found" in not_found.json()["detail"].lower()

    disable_submit = client.put(
        f"/admin/tenants/{tenant_id}",
        json=_tenant_update_payload(
            full_name="Tenant Reading",
            primary_phone="+380500000002",
            email="tenant-reading@example.com",
            portal_enabled=True,
            can_submit_meter_readings=False,
        ),
        headers=headers,
    )
    assert disable_submit.status_code == 200

    forbidden = client.post(
        "/tenant/me/readings",
        json={"meter_id": meter_a_id, "year": 2026, "month": 2, "register_name": "total", "value": "11.0"},
        headers=tenant_headers,
    )
    assert forbidden.status_code == 403

    enable_submit = client.put(
        f"/admin/tenants/{tenant_id}",
        json=_tenant_update_payload(
            full_name="Tenant Reading",
            primary_phone="+380500000002",
            email="tenant-reading@example.com",
            portal_enabled=True,
            can_submit_meter_readings=True,
        ),
        headers=headers,
    )
    assert enable_submit.status_code == 200

    replace = client.post(
        f"/admin/meters/{meter_a_id}/replace",
        json={"serial_number": "W-A-NEW", "initial_reading": "0", "installed_at": "2026-03-01"},
        headers=headers,
    )
    assert replace.status_code == 200

    conflict = client.post(
        "/tenant/me/readings",
        json={"meter_id": meter_a_id, "year": 2026, "month": 3, "register_name": "total", "value": "15.0"},
        headers=tenant_headers,
    )
    assert conflict.status_code == 409
    assert "archived" in conflict.json()["detail"].lower()
