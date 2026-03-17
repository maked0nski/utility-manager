"""tenant session version and token lifecycle

Revision ID: 20260224_07
Revises: 20260223_06
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260224_07"
down_revision = "20260223_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column("tenants", "session_version", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "session_version")
