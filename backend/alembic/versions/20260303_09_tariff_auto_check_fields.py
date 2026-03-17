"""tariff setting auto-check fields

Revision ID: 20260303_09
Revises: 20260302_08
Create Date: 2026-03-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260303_09"
down_revision = "20260302_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("apartment_tariff_settings") as batch_op:
        batch_op.add_column(sa.Column("auto_check_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("auto_check_time", sa.String(length=5), nullable=False, server_default="09:00"))
        batch_op.add_column(
            sa.Column("auto_check_timezone", sa.String(length=64), nullable=False, server_default="Europe/Kyiv")
        )
        batch_op.add_column(
            sa.Column("auto_check_window_day_from", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(sa.Column("auto_check_window_day_to", sa.Integer(), nullable=False, server_default="10"))
        batch_op.add_column(sa.Column("auto_check_target_year", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("auto_check_target_month", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("auto_check_completed_for_period", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("auto_check_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("auto_check_message", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("auto_check_last_value_raw", sa.Numeric(12, 4), nullable=True))
        batch_op.add_column(sa.Column("auto_check_last_value_rounded", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("auto_check_last_checked_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("auto_check_last_updated_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("auto_check_next_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_apartment_tariff_settings_auto_check_target_year", ["auto_check_target_year"])
        batch_op.create_index("ix_apartment_tariff_settings_auto_check_target_month", ["auto_check_target_month"])


def downgrade() -> None:
    with op.batch_alter_table("apartment_tariff_settings") as batch_op:
        batch_op.drop_index("ix_apartment_tariff_settings_auto_check_target_month")
        batch_op.drop_index("ix_apartment_tariff_settings_auto_check_target_year")
        batch_op.drop_column("auto_check_next_at")
        batch_op.drop_column("auto_check_last_updated_at")
        batch_op.drop_column("auto_check_last_checked_at")
        batch_op.drop_column("auto_check_last_value_rounded")
        batch_op.drop_column("auto_check_last_value_raw")
        batch_op.drop_column("auto_check_message")
        batch_op.drop_column("auto_check_status")
        batch_op.drop_column("auto_check_completed_for_period")
        batch_op.drop_column("auto_check_target_month")
        batch_op.drop_column("auto_check_target_year")
        batch_op.drop_column("auto_check_window_day_to")
        batch_op.drop_column("auto_check_window_day_from")
        batch_op.drop_column("auto_check_timezone")
        batch_op.drop_column("auto_check_time")
        batch_op.drop_column("auto_check_enabled")
