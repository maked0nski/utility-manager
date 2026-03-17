"""P1: add apartment passport fields and equipment table.

Revision ID: 20260223_03
Revises: 20260223_02
Create Date: 2026-02-23 16:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260223_03"
down_revision = "20260223_02"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    apartment_cols = _column_names("apartments")
    if "area_m2" not in apartment_cols:
        op.add_column("apartments", sa.Column("area_m2", sa.Numeric(10, 2), nullable=True))
    if "latitude" not in apartment_cols:
        op.add_column("apartments", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    if "longitude" not in apartment_cols:
        op.add_column("apartments", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    if "location_note" not in apartment_cols:
        op.add_column("apartments", sa.Column("location_note", sa.String(length=255), nullable=True))
    if "object_notes" not in apartment_cols:
        op.add_column("apartments", sa.Column("object_notes", sa.Text(), nullable=True))

    if not _table_exists("apartment_equipments"):
        op.create_table(
            "apartment_equipments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("apartment_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False, server_default="other"),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("serial_number", sa.String(length=128), nullable=True),
            sa.Column("installed_at", sa.Date(), nullable=True),
            sa.Column("manual_url", sa.String(length=512), nullable=True),
            sa.Column("service_interval_days", sa.Integer(), nullable=True),
            sa.Column("last_service_at", sa.Date(), nullable=True),
            sa.Column("next_service_at", sa.Date(), nullable=True),
            sa.Column("note", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_apartment_equipments_id"), "apartment_equipments", ["id"], unique=False)
        op.create_index(
            op.f("ix_apartment_equipments_apartment_id"),
            "apartment_equipments",
            ["apartment_id"],
            unique=False,
        )

    if not _index_exists("apartment_equipments", "ix_apartment_equipments_apartment_name"):
        op.create_index(
            "ix_apartment_equipments_apartment_name",
            "apartment_equipments",
            ["apartment_id", "name"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("apartment_equipments"):
        if _index_exists("apartment_equipments", "ix_apartment_equipments_apartment_name"):
            op.drop_index("ix_apartment_equipments_apartment_name", table_name="apartment_equipments")
        op.drop_index(op.f("ix_apartment_equipments_apartment_id"), table_name="apartment_equipments")
        op.drop_index(op.f("ix_apartment_equipments_id"), table_name="apartment_equipments")
        op.drop_table("apartment_equipments")

    apartment_cols = _column_names("apartments")
    if "object_notes" in apartment_cols:
        op.drop_column("apartments", "object_notes")
    if "location_note" in apartment_cols:
        op.drop_column("apartments", "location_note")
    if "longitude" in apartment_cols:
        op.drop_column("apartments", "longitude")
    if "latitude" in apartment_cols:
        op.drop_column("apartments", "latitude")
    if "area_m2" in apartment_cols:
        op.drop_column("apartments", "area_m2")
