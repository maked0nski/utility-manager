"""P2: add admin password_changed_at for rotation reminders.

Revision ID: 20260221_01
Revises: 20260220_02
Create Date: 2026-02-21 19:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260221_01"
down_revision = "20260220_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        op.execute(
            "ALTER TABLE admin_users "
            "ADD COLUMN password_changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        op.execute("ALTER TABLE admin_users DROP COLUMN password_changed_at")
