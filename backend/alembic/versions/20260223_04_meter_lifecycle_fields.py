"""P1: add meter lifecycle fields.

Revision ID: 20260223_04
Revises: 20260223_03
Create Date: 2026-02-23 20:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260223_04"
down_revision = "20260223_03"
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


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    meter_cols = _column_names("meters")
    if "retired_at" not in meter_cols:
        op.add_column("meters", sa.Column("retired_at", sa.Date(), nullable=True))
    if "replaced_by_meter_id" not in meter_cols:
        op.add_column("meters", sa.Column("replaced_by_meter_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_meters_replaced_by_meter_id",
            "meters",
            "meters",
            ["replaced_by_meter_id"],
            ["id"],
        )
        op.create_index(op.f("ix_meters_replaced_by_meter_id"), "meters", ["replaced_by_meter_id"], unique=False)
    if "is_active" not in meter_cols:
        op.add_column("meters", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")))


def downgrade() -> None:
    meter_cols = _column_names("meters")
    if "is_active" in meter_cols:
        op.drop_column("meters", "is_active")
    if "replaced_by_meter_id" in meter_cols:
        if _index_exists("meters", op.f("ix_meters_replaced_by_meter_id")):
            op.drop_index(op.f("ix_meters_replaced_by_meter_id"), table_name="meters")
        op.drop_constraint("fk_meters_replaced_by_meter_id", "meters", type_="foreignkey")
        op.drop_column("meters", "replaced_by_meter_id")
    if "retired_at" in meter_cols:
        op.drop_column("meters", "retired_at")
