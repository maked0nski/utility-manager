"""P2: add provider import staging tables.

Revision ID: 20260223_02
Revises: 20260223_01
Create Date: 2026-02-23 16:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260223_02"
down_revision = "20260223_01"
branch_labels = None
depends_on = None


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
    if not _table_exists("provider_import_batches"):
        op.create_table(
            "provider_import_batches",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("apartment_id", sa.Integer(), nullable=False),
            sa.Column("provider_code", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("requested_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("source_ref", sa.String(length=255), nullable=True),
            sa.Column("period_year", sa.Integer(), nullable=True),
            sa.Column("period_month", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.String(length=255), nullable=True),
            sa.Column("raw_meta_json", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_provider_import_batches_id"), "provider_import_batches", ["id"], unique=False)
        op.create_index(
            op.f("ix_provider_import_batches_apartment_id"),
            "provider_import_batches",
            ["apartment_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_provider_import_batches_provider_code"),
            "provider_import_batches",
            ["provider_code"],
            unique=False,
        )
        op.create_index(
            op.f("ix_provider_import_batches_period_year"),
            "provider_import_batches",
            ["period_year"],
            unique=False,
        )
        op.create_index(
            op.f("ix_provider_import_batches_period_month"),
            "provider_import_batches",
            ["period_month"],
            unique=False,
        )

    if not _index_exists("provider_import_batches", "ix_provider_import_batches_provider_requested"):
        op.create_index(
            "ix_provider_import_batches_provider_requested",
            "provider_import_batches",
            ["provider_code", "requested_at"],
            unique=False,
        )

    if not _table_exists("provider_import_rows"):
        op.create_table(
            "provider_import_rows",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("service_name", sa.String(length=128), nullable=False),
            sa.Column("period_year", sa.Integer(), nullable=False),
            sa.Column("period_month", sa.Integer(), nullable=False),
            sa.Column("accrued", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("paid", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("adjustment", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("benefit", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("subsidy", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="staged"),
            sa.Column("error_message", sa.String(length=255), nullable=True),
            sa.Column("raw_payload_json", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["provider_import_batches.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_provider_import_rows_id"), "provider_import_rows", ["id"], unique=False)
        op.create_index(op.f("ix_provider_import_rows_batch_id"), "provider_import_rows", ["batch_id"], unique=False)
        op.create_index(
            op.f("ix_provider_import_rows_service_name"),
            "provider_import_rows",
            ["service_name"],
            unique=False,
        )
        op.create_index(
            op.f("ix_provider_import_rows_period_year"),
            "provider_import_rows",
            ["period_year"],
            unique=False,
        )
        op.create_index(
            op.f("ix_provider_import_rows_period_month"),
            "provider_import_rows",
            ["period_month"],
            unique=False,
        )

    if not _index_exists("provider_import_rows", "ix_provider_import_rows_batch_service_period"):
        op.create_index(
            "ix_provider_import_rows_batch_service_period",
            "provider_import_rows",
            ["batch_id", "service_name", "period_year", "period_month"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("provider_import_rows"):
        if _index_exists("provider_import_rows", "ix_provider_import_rows_batch_service_period"):
            op.drop_index("ix_provider_import_rows_batch_service_period", table_name="provider_import_rows")
        op.drop_index(op.f("ix_provider_import_rows_period_month"), table_name="provider_import_rows")
        op.drop_index(op.f("ix_provider_import_rows_period_year"), table_name="provider_import_rows")
        op.drop_index(op.f("ix_provider_import_rows_service_name"), table_name="provider_import_rows")
        op.drop_index(op.f("ix_provider_import_rows_batch_id"), table_name="provider_import_rows")
        op.drop_index(op.f("ix_provider_import_rows_id"), table_name="provider_import_rows")
        op.drop_table("provider_import_rows")

    if _table_exists("provider_import_batches"):
        if _index_exists("provider_import_batches", "ix_provider_import_batches_provider_requested"):
            op.drop_index("ix_provider_import_batches_provider_requested", table_name="provider_import_batches")
        op.drop_index(op.f("ix_provider_import_batches_period_month"), table_name="provider_import_batches")
        op.drop_index(op.f("ix_provider_import_batches_period_year"), table_name="provider_import_batches")
        op.drop_index(op.f("ix_provider_import_batches_provider_code"), table_name="provider_import_batches")
        op.drop_index(op.f("ix_provider_import_batches_apartment_id"), table_name="provider_import_batches")
        op.drop_index(op.f("ix_provider_import_batches_id"), table_name="provider_import_batches")
        op.drop_table("provider_import_batches")
