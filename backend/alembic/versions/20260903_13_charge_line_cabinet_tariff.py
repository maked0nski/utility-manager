"""connection charge line cabinet tariff fields

Revision ID: 20260903_13
Revises: 20260307_12
Create Date: 2026-09-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_13"
down_revision = "20260307_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("connection_charge_lines") as batch_op:
        batch_op.add_column(sa.Column("cabinet_price_per_unit", sa.Numeric(12, 4), nullable=True))
        batch_op.add_column(sa.Column("cabinet_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("connection_charge_lines") as batch_op:
        batch_op.drop_column("cabinet_checked_at")
        batch_op.drop_column("cabinet_price_per_unit")
