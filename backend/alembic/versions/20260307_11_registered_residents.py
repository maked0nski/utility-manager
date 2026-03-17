"""add apartment registered residents and migrate garbage tariff to per-person

Revision ID: 20260307_11
Revises: 20260307_10
Create Date: 2026-03-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_11"
down_revision = "20260307_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "apartments" not in table_names:
        return
    apartment_columns = {col["name"] for col in inspector.get_columns("apartments")}

    if "registered_residents" not in apartment_columns:
        with op.batch_alter_table("apartments") as batch_op:
            batch_op.add_column(sa.Column("registered_residents", sa.Integer(), nullable=False, server_default="1"))

    bind.execute(sa.text("UPDATE apartments SET registered_residents = 1 WHERE registered_residents IS NULL"))

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
                UPDATE apartments
                SET registered_residents = 3
                WHERE id = :apartment_id
                """
            ),
            {"apartment_id": apartment_id},
        )
        bind.execute(
            sa.text(
                """
                UPDATE tariffs
                SET price_per_unit = ROUND(price_per_unit / 3, 4)
                WHERE apartment_id = :apartment_id
                  AND LOWER(service_name) LIKE :service_mask
                  AND price_per_unit >= 100
                """
            ),
            {"apartment_id": apartment_id, "service_mask": "%вивіз сміття%"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "apartments" not in inspector.get_table_names():
        return
    with op.batch_alter_table("apartments") as batch_op:
        batch_op.drop_column("registered_residents")
