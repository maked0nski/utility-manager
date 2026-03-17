"""tariff fixed formula fields

Revision ID: 20260307_12
Revises: 20260307_11
Create Date: 2026-03-07 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_12"
down_revision = "20260307_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "tariffs" not in table_names:
        return
    tariff_columns = {col["name"] for col in inspector.get_columns("tariffs")}

    if "fixed_quantity_source" not in tariff_columns:
        with op.batch_alter_table("tariffs") as batch_op:
            batch_op.add_column(sa.Column("fixed_quantity_source", sa.String(length=32), nullable=False, server_default="auto"))

    if "fixed_quantity_multiplier" not in tariff_columns:
        with op.batch_alter_table("tariffs") as batch_op:
            batch_op.add_column(
                sa.Column("fixed_quantity_multiplier", sa.Numeric(10, 3), nullable=False, server_default="1.000")
            )

    bind.execute(
        sa.text(
            """
            UPDATE tariffs
            SET fixed_quantity_source = 'auto'
            WHERE fixed_quantity_source IS NULL OR TRIM(fixed_quantity_source) = ''
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE tariffs
            SET fixed_quantity_multiplier = 1.000
            WHERE fixed_quantity_multiplier IS NULL OR fixed_quantity_multiplier <= 0
            """
        )
    )

    target_apartment = bind.execute(
        sa.text(
            """
            SELECT id
            FROM apartments
            WHERE address = :target_address OR code = :target_code
            LIMIT 1
            """
        ),
        {"target_address": "Івасюка 11, кв.195", "target_code": "11-195-D575BB"},
    ).fetchone()

    if target_apartment is not None:
        apartment_id = int(target_apartment[0])
        bind.execute(
            sa.text(
                """
                UPDATE tariffs
                SET fixed_quantity_source = 'apartment_registered_residents',
                    fixed_quantity_multiplier = 1.000
                WHERE apartment_id = :apartment_id
                  AND LOWER(service_name) LIKE :service_mask
                """
            ),
            {"apartment_id": apartment_id, "service_mask": "%вивіз сміття%"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tariffs" not in inspector.get_table_names():
        return
    with op.batch_alter_table("tariffs") as batch_op:
        batch_op.drop_column("fixed_quantity_multiplier")
        batch_op.drop_column("fixed_quantity_source")
