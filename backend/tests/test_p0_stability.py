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

    tariff = client.post(
        "/admin/tariffs",
        json={
            "apartment_id": apartment_id,
            "service_name": "Квартплата",
            "charge_mode": "fixed",
            "utility_type": None,
            "price_per_unit": "100.00",
            "unit_name": "month",
            "effective_from": "2024-09-01",
        },
        headers=headers,
    )
    assert tariff.status_code == 201
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

    tariff = client.post(
        "/admin/tariffs",
        json={
            "apartment_id": apartment_id,
            "service_name": "Квартплата",
            "charge_mode": "fixed",
            "utility_type": None,
            "price_per_unit": "100.00",
            "unit_name": "month",
            "effective_from": "2024-09-01",
        },
        headers=headers,
    )
    assert tariff.status_code == 201

    # First payment for September.
    pay_sep_1 = client.post(
        "/admin/payments/utilities",
        json={
            "apartment_id": apartment_id,
            "year": 2024,
            "month": 9,
            "amount": "50.00",
            "paid_at": "2024-10-01",
            "note": "first",
        },
        headers=headers,
    )
    assert pay_sep_1.status_code == 200

    # Another payment in the same month (must be added and accumulated).
    pay_sep_2 = client.post(
        "/admin/payments/utilities",
        json={
            "apartment_id": apartment_id,
            "year": 2024,
            "month": 9,
            "amount": "60.00",
            "paid_at": "2024-10-02",
            "note": "second",
        },
        headers=headers,
    )
    assert pay_sep_2.status_code == 200

    sep = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=9", headers=headers)
    assert sep.status_code == 200
    sep_balance = sep.json()["utility_balance"]
    assert sep_balance["month_payments"] == "110.00"
    assert sep_balance["month_payment_date"] == "2024-10-02"
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
        assert paid_dates == ["2024-10-01", "2024-10-02"]
    finally:
        db.close()

    # October payment date must be independent and not overwrite September date.
    pay_oct = client.post(
        "/admin/payments/utilities",
        json={
            "apartment_id": apartment_id,
            "year": 2024,
            "month": 10,
            "amount": "70.00",
            "paid_at": "2024-11-06",
            "note": "oct",
        },
        headers=headers,
    )
    assert pay_oct.status_code == 200

    sep_again = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=9", headers=headers)
    oct_data = client.get(f"/admin/dashboard/apartments/{apartment_id}?year=2024&month=10", headers=headers)
    assert sep_again.status_code == 200
    assert oct_data.status_code == 200
    assert sep_again.json()["utility_balance"]["month_payment_date"] == "2024-10-02"
    assert oct_data.json()["utility_balance"]["month_payment_date"] == "2024-11-06"
