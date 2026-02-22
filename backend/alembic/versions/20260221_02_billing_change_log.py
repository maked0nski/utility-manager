"""P2: add billing change log table.

Revision ID: 20260221_02
Revises: 20260221_01
Create Date: 2026-02-21 22:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260221_02"
down_revision = "20260221_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade() -> None:
    if not _table_exists("billing_change_logs"):
        op.create_table(
            "billing_change_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("apartment_id", sa.Integer(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("service_name", sa.String(length=128), nullable=True),
            sa.Column("actor_username", sa.String(length=64), nullable=False),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["apartment_id"], ["apartments.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_billing_change_logs_id"), "billing_change_logs", ["id"], unique=False)
        op.create_index(
            op.f("ix_billing_change_logs_apartment_id"),
            "billing_change_logs",
            ["apartment_id"],
            unique=False,
        )
        op.create_index(op.f("ix_billing_change_logs_year"), "billing_change_logs", ["year"], unique=False)
        op.create_index(op.f("ix_billing_change_logs_month"), "billing_change_logs", ["month"], unique=False)

    if not _index_exists("billing_change_logs", "ix_billing_change_logs_apartment_period_created"):
        op.create_index(
            "ix_billing_change_logs_apartment_period_created",
            "billing_change_logs",
            ["apartment_id", "year", "month", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("billing_change_logs"):
        if _index_exists("billing_change_logs", "ix_billing_change_logs_apartment_period_created"):
            op.drop_index("ix_billing_change_logs_apartment_period_created", table_name="billing_change_logs")
        op.drop_index(op.f("ix_billing_change_logs_month"), table_name="billing_change_logs")
        op.drop_index(op.f("ix_billing_change_logs_year"), table_name="billing_change_logs")
        op.drop_index(op.f("ix_billing_change_logs_apartment_id"), table_name="billing_change_logs")
        op.drop_index(op.f("ix_billing_change_logs_id"), table_name="billing_change_logs")
        op.drop_table("billing_change_logs")
