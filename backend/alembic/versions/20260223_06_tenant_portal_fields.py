"""tenant portal fields

Revision ID: 20260223_06
Revises: 20260223_05
Create Date: 2026-02-23 23:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260223_06"
down_revision = "20260223_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("portal_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tenants",
        sa.Column("can_submit_meter_readings", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tenants", "can_submit_meter_readings")
    op.drop_column("tenants", "portal_enabled")
    op.drop_column("tenants", "password_hash")
