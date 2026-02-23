"""P1: add simplified per-service monthly ledger table.

Revision ID: 20260223_01
Revises: 20260221_03
Create Date: 2026-02-23 12:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260223_01"
down_revision = "20260221_03"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("service_ledger_entries"):
        op.create_table(
            "service_ledger_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("apartment_id", sa.Integer(), nullable=False),
            sa.Column("service_name", sa.String(length=128), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("accrued", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("paid", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("adjustment", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("benefit", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("subsidy", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("closing_balance", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "apartment_id",
                "service_name",
                "year",
                "month",
                name="uq_service_ledger_period",
            ),
        )
        op.create_index(
            op.f("ix_service_ledger_entries_id"),
            "service_ledger_entries",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_service_ledger_entries_apartment_id"),
            "service_ledger_entries",
            ["apartment_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_service_ledger_entries_service_name"),
            "service_ledger_entries",
            ["service_name"],
            unique=False,
        )
        op.create_index(
            op.f("ix_service_ledger_entries_year"),
            "service_ledger_entries",
            ["year"],
            unique=False,
        )
        op.create_index(
            op.f("ix_service_ledger_entries_month"),
            "service_ledger_entries",
            ["month"],
            unique=False,
        )

    if not _index_exists("service_ledger_entries", "ix_service_ledger_apartment_service_period"):
        op.create_index(
            "ix_service_ledger_apartment_service_period",
            "service_ledger_entries",
            ["apartment_id", "service_name", "year", "month"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("service_ledger_entries"):
        if _index_exists("service_ledger_entries", "ix_service_ledger_apartment_service_period"):
            op.drop_index("ix_service_ledger_apartment_service_period", table_name="service_ledger_entries")
        op.drop_index(op.f("ix_service_ledger_entries_month"), table_name="service_ledger_entries")
        op.drop_index(op.f("ix_service_ledger_entries_year"), table_name="service_ledger_entries")
        op.drop_index(op.f("ix_service_ledger_entries_service_name"), table_name="service_ledger_entries")
        op.drop_index(op.f("ix_service_ledger_entries_apartment_id"), table_name="service_ledger_entries")
        op.drop_index(op.f("ix_service_ledger_entries_id"), table_name="service_ledger_entries")
        op.drop_table("service_ledger_entries")
