"""P1: add personal account and performance indexes.

Revision ID: 20260220_01
Revises:
Create Date: 2026-02-20 18:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260220_01"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade() -> None:
    if not _column_exists("apartment_tariff_settings", "personal_account"):
        op.add_column("apartment_tariff_settings", sa.Column("personal_account", sa.String(length=128), nullable=True))

    if not _index_exists("utility_payments", "ix_utility_payments_apartment_period"):
        op.create_index(
            "ix_utility_payments_apartment_period",
            "utility_payments",
            ["apartment_id", "year", "month"],
            unique=False,
        )

    if not _index_exists("owner_charges", "ix_owner_charges_apartment_period_kind"):
        op.create_index(
            "ix_owner_charges_apartment_period_kind",
            "owner_charges",
            ["apartment_id", "year", "month", "kind"],
            unique=False,
        )

    if not _index_exists("maintenance_records", "ix_maintenance_records_apartment_dates"):
        op.create_index(
            "ix_maintenance_records_apartment_dates",
            "maintenance_records",
            ["apartment_id", "performed_at", "scheduled_for"],
            unique=False,
        )


def downgrade() -> None:
    if _index_exists("maintenance_records", "ix_maintenance_records_apartment_dates"):
        op.drop_index("ix_maintenance_records_apartment_dates", table_name="maintenance_records")
    if _index_exists("owner_charges", "ix_owner_charges_apartment_period_kind"):
        op.drop_index("ix_owner_charges_apartment_period_kind", table_name="owner_charges")
    if _index_exists("utility_payments", "ix_utility_payments_apartment_period"):
        op.drop_index("ix_utility_payments_apartment_period", table_name="utility_payments")
    if _column_exists("apartment_tariff_settings", "personal_account"):
        op.drop_column("apartment_tariff_settings", "personal_account")
