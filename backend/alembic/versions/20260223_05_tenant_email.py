"""tenant email field

Revision ID: 20260223_05
Revises: 20260223_04
Create Date: 2026-02-23 22:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260223_05"
down_revision = "20260223_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("email", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_tenants_email"), "tenants", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_email"), table_name="tenants")
    op.drop_column("tenants", "email")
