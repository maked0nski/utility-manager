"""utility payment source and nullable tenant/invoice

Revision ID: 20260302_08
Revises: 20260224_07
Create Date: 2026-03-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260302_08"
down_revision = "20260224_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("utility_payments") as batch_op:
        batch_op.add_column(sa.Column("payer_type", sa.String(length=16), nullable=False, server_default="tenant"))
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("invoice_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("utility_payments") as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("invoice_id", existing_type=sa.Integer(), nullable=True)
        batch_op.drop_column("payer_type")
