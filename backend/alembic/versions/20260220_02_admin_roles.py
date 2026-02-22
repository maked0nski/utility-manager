"""P2: expand admin roles enum.

Revision ID: 20260220_02
Revises: 20260220_01
Create Date: 2026-02-20 20:10:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260220_02"
down_revision = "20260220_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        op.execute(
            "ALTER TABLE admin_users "
            "MODIFY COLUMN role ENUM('admin','operator','read_only') NOT NULL DEFAULT 'admin'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        op.execute(
            "ALTER TABLE admin_users "
            "MODIFY COLUMN role ENUM('admin') NOT NULL DEFAULT 'admin'"
        )
