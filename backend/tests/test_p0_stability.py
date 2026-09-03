from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.auth import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AdminUser, UtilityPayment

TEST_DB_PATH = Path("test_p0_stability.db")
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


def _create_fixed_tariff(headers, apartment_id, *, code, name, price_per_unit, effective_from):
    """Replacement for the old single-call POST /admin/tariffs (410 Gone):
    creates a ServiceCatalog entry, an ApartmentServiceConnection for the
    apartment, and one fixed ConnectionChargeLine. _reset_db() wipes the
    catalog before every test in this file, so no cross-test caching is
    needed here (unlike test_v1_flow.py, which shares one DB across its
    whole module)."""
    catalog = client.post(
        "/admin/service-catalog",
        json={
            "code": code,
            "name": name,
            "calculation_kind": "fixed",
            "unit_name": "month",
            "requires_meter": False,
        },
        headers=headers,
    )
    assert catalog.status_code == 201, catalog.text
    catalog_id = catalog.json()["id"]

    connection = client.post(
        "/admin/service-connections",
        json={
            "apartment_id": apartment_id,
            "service_catalog_id": catalog_id,
            "started_at": effective_from,
            "status": "active",
        },
        headers=headers,
    )
    assert connection.status_code == 201, connection.text
    connection_id = connection.json()["id"]

    line = client.post(
        f"/admin/service-connections/{connection_id}/charge-lines",
        json={
            "line_kind": "fixed",
            "label": name,
            "unit_name": "month",
            "price_per_unit": price_per_unit,
            "quantity_source": "fixed_1",
            "quantity_multiplier": "1",
            "effective_from": effective_from,
        },
        headers=headers,
    )
    assert line.status_code == 201, line.text
    return line.json()


def _seed_apartment(headers):
    apartment = client.post("/admin/apartments", json={"address": "Test Address 1"}, headers=headers)
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant = client.post(
        "/admin/tenants",
        json={"full_name": "Tenant 1", "phone": "+380501111111", "access_code": "TENANT-P0-1"},
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

    _create_fixed_tariff(
        headers,
        apartment_id,
        code="maintenance_fee",
        name="Квартплата",
        price_per_unit="100.00",
        effective_from="2024-09-01",
    )
    return apartment_id


def test_balance_formula_and_locked_carry():
    _reset_db()
    headers = _login_headers()
    apartment_id = _seed_apartment(headers)

    # Reimbursement must reduce month charges in September.
    reimbursement = client.post(
        "/admin/owner-charges",
        json={
            "apartment_id": apartment_id,
            "year": 2024,
            "month": 9,
            "kind": "reimbursement",
            "category": "Test reimbursement",
            "amount": "30.00",
            "currency": "UAH",
            "event_date": "2024-09-15",
        },
        headers=headers,
    )
    assert reimbursement.status_code == 201

    sep = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=9", headers=headers)
    assert sep.status_code == 200
    sep_balance = sep.json()["utility_balance"]
    assert sep_balance["previous_month_debt"] == "0.00"
    assert sep_balance["month_charges"] == "70.00"
    assert sep_balance["month_payments"] == "0.00"
    assert sep_balance["current_balance"] == "70.00"

    oct_before_lock = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=10", headers=headers)
    assert oct_before_lock.status_code == 200
    assert oct_before_lock.json()["utility_balance"]["previous_month_debt"] == "0.00"
    assert oct_before_lock.json()["utility_balance"]["month_charges"] == "100.00"
    assert oct_before_lock.json()["utility_balance"]["current_balance"] == "100.00"

    lock_sep = client.post(
        "/admin/billing/lock",
        json={"apartment_id": apartment_id, "year": 2024, "month": 9},
        headers=headers,
    )
    assert lock_sep.status_code == 200

    oct_after_lock = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=10", headers=headers)
    assert oct_after_lock.status_code == 200
    assert oct_after_lock.json()["utility_balance"]["previous_month_debt"] == "70.00"
    assert oct_after_lock.json()["utility_balance"]["month_charges"] == "100.00"
    assert oct_after_lock.json()["utility_balance"]["current_balance"] == "170.00"


def test_utility_payment_upsert_and_payment_date_per_month():
    _reset_db()
    headers = _login_headers()
    apartment = client.post("/admin/apartments", json={"address": "Test Address 2"}, headers=headers)
    assert apartment.status_code == 201
    apartment_id = apartment.json()["id"]

    tenant = client.post(
        "/admin/tenants",
        json={"full_name": "Tenant 2", "phone": "+380502222222", "access_code": "TENANT-P0-2"},
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

    _create_fixed_tariff(
        headers,
        apartment_id,
        code="maintenance_fee",
        name="Квартплата",
        price_per_unit="100.00",
        effective_from="2024-09-01",
    )

    # UtilityPaymentCreate has no year/month fields anymore - the payment's
    # own paid_at date is what determines which month's invoice it applies
    # to (matches the current admin UI's "Саме ця дата визначає, в який
    # місяць потрапить оплата" hint), so both payments' paid_at must
    # actually fall in September to test "same-month accumulation" here.

    # First payment for September.
    pay_sep_1 = client.post(
        "/admin/payments/utilities",
        json={
            "apartment_id": apartment_id,
            "amount": "50.00",
            "paid_at": "2024-09-10",
            "note": "first",
        },
        headers=headers,
    )
    assert pay_sep_1.status_code == 200, pay_sep_1.text

    # Another payment in the same month (must be added and accumulated).
    pay_sep_2 = client.post(
        "/admin/payments/utilities",
        json={
            "apartment_id": apartment_id,
            "amount": "60.00",
            "paid_at": "2024-09-20",
            "note": "second",
        },
        headers=headers,
    )
    assert pay_sep_2.status_code == 200, pay_sep_2.text

    sep = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=9", headers=headers)
    assert sep.status_code == 200
    sep_balance = sep.json()["utility_balance"]
    assert sep_balance["month_payments"] == "110.00"
    assert sep_balance["month_payment_date"] == "2024-09-20"
    assert sep_balance["month_payment_note"] == "second"

    db = TestingSessionLocal()
    try:
        rows = db.scalars(
            select(UtilityPayment).where(
                UtilityPayment.apartment_id == apartment_id,
                UtilityPayment.year == 2024,
                UtilityPayment.month == 9,
            )
        ).all()
        assert len(rows) == 2
        amounts = sorted(str(x.amount) for x in rows)
        paid_dates = sorted(str(x.paid_at) for x in rows)
        assert amounts == ["50.00", "60.00"]
        assert paid_dates == ["2024-09-10", "2024-09-20"]
    finally:
        db.close()

    # October payment date must be independent and not overwrite September date.
    pay_oct = client.post(
        "/admin/payments/utilities",
        json={
            "apartment_id": apartment_id,
            "amount": "70.00",
            "paid_at": "2024-10-15",
            "note": "oct",
        },
        headers=headers,
    )
    assert pay_oct.status_code == 200, pay_oct.text

    sep_again = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=9", headers=headers)
    oct_data = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=10", headers=headers)
    assert sep_again.status_code == 200
    assert oct_data.status_code == 200
    assert sep_again.json()["utility_balance"]["month_payment_date"] == "2024-09-20"
    assert oct_data.json()["utility_balance"]["month_payment_date"] == "2024-10-15"
