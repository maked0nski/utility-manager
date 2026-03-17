"""P2: add meter registers and tariff meter/source binding.

Revision ID: 20260221_03
Revises: 20260221_02
Create Date: 2026-02-21 23:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260221_03"
down_revision = "20260221_02"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _unique_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {uc["name"] for uc in inspector.get_unique_constraints(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    tariff_cols = _column_names("tariffs")
    if "meter_id" not in tariff_cols:
        op.add_column("tariffs", sa.Column("meter_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_tariffs_meter_id", "tariffs", "meters", ["meter_id"], ["id"])
        op.create_index(op.f("ix_tariffs_meter_id"), "tariffs", ["meter_id"], unique=False)
    if "meter_register" not in tariff_cols:
        op.add_column("tariffs", sa.Column("meter_register", sa.String(length=32), nullable=False, server_default="total"))
        op.alter_column("tariffs", "meter_register", server_default=None)
    if "source_service_name" not in tariff_cols:
        op.add_column("tariffs", sa.Column("source_service_name", sa.String(length=128), nullable=True))

    reading_cols = _column_names("meter_readings")
    if "register_name" not in reading_cols:
        op.add_column(
            "meter_readings",
            sa.Column("register_name", sa.String(length=32), nullable=False, server_default="total"),
        )
        op.alter_column("meter_readings", "register_name", server_default=None)

    uq_names = _unique_names("meter_readings")
    if "uq_reading_period" in uq_names:
        op.drop_constraint("uq_reading_period", "meter_readings", type_="unique")
    uq_names = _unique_names("meter_readings")
    if "uq_reading_period" not in uq_names:
        op.create_unique_constraint(
            "uq_reading_period",
            "meter_readings",
            ["meter_id", "register_name", "year", "month"],
        )


def downgrade() -> None:
    uq_names = _unique_names("meter_readings")
    if "uq_reading_period" in uq_names:
        op.drop_constraint("uq_reading_period", "meter_readings", type_="unique")
    if _table_exists("meter_readings"):
        op.create_unique_constraint("uq_reading_period", "meter_readings", ["meter_id", "year", "month"])

    reading_cols = _column_names("meter_readings")
    if "register_name" in reading_cols:
        op.drop_column("meter_readings", "register_name")

    tariff_cols = _column_names("tariffs")
    idx_names = _index_names("tariffs")
    if "source_service_name" in tariff_cols:
        op.drop_column("tariffs", "source_service_name")
    if "meter_register" in tariff_cols:
        op.drop_column("tariffs", "meter_register")
    if "meter_id" in tariff_cols:
        if op.f("ix_tariffs_meter_id") in idx_names:
            op.drop_index(op.f("ix_tariffs_meter_id"), table_name="tariffs")
        op.drop_constraint("fk_tariffs_meter_id", "tariffs", type_="foreignkey")
        op.drop_column("tariffs", "meter_id")
