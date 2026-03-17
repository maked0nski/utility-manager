"""providers catalog and provider link for tariff settings

Revision ID: 20260307_10
Revises: 20260303_09
Create Date: 2026-03-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_10"
down_revision = "20260303_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "providers" not in table_names:
        op.create_table(
            "providers",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name_full", sa.String(length=255), nullable=False),
            sa.Column(
                "utility_type",
                sa.Enum("electricity", "water", "gas", "heating", "sewage", "internet", "other", name="utilitytype"),
                nullable=False,
            ),
            sa.Column("adapter_code", sa.String(length=64), nullable=False, server_default="manual_stub"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("name_full", name="uq_providers_name_full"),
        )
        table_names.add("providers")

    provider_indexes = {idx.get("name") for idx in inspector.get_indexes("providers")}
    if "ix_providers_name_full" not in provider_indexes:
        op.create_index("ix_providers_name_full", "providers", ["name_full"], unique=False)
    if "ix_providers_utility_type" not in provider_indexes:
        op.create_index("ix_providers_utility_type", "providers", ["utility_type"], unique=False)
    if "ix_providers_adapter_code" not in provider_indexes:
        op.create_index("ix_providers_adapter_code", "providers", ["adapter_code"], unique=False)

    if "apartment_tariff_settings" not in table_names:
        return

    tariff_columns = {col["name"] for col in inspector.get_columns("apartment_tariff_settings")}
    if "provider_id" not in tariff_columns:
        with op.batch_alter_table("apartment_tariff_settings") as batch_op:
            batch_op.add_column(sa.Column("provider_id", sa.Integer(), nullable=True))

    tariff_indexes = {idx.get("name") for idx in inspector.get_indexes("apartment_tariff_settings")}
    if "ix_apartment_tariff_settings_provider_id" not in tariff_indexes:
        op.create_index(
            "ix_apartment_tariff_settings_provider_id",
            "apartment_tariff_settings",
            ["provider_id"],
            unique=False,
        )

    tariff_foreign_keys = inspector.get_foreign_keys("apartment_tariff_settings")
    has_provider_fk = any(
        fk.get("referred_table") == "providers" and fk.get("constrained_columns") == ["provider_id"]
        for fk in tariff_foreign_keys
    )
    if not has_provider_fk:
        with op.batch_alter_table("apartment_tariff_settings") as batch_op:
            batch_op.create_foreign_key(
                "fk_apartment_tariff_settings_provider_id",
                "providers",
                ["provider_id"],
                ["id"],
            )

    migrated_note = "Auto-migrated from apartment_tariff_settings.provider_company"
    stub_name = "Заглушка: Постачальник не вказаний"
    stub_note = "Auto-generated placeholder provider"

    existing_names = bind.execute(
        sa.text(
            """
            SELECT DISTINCT provider_company
            FROM apartment_tariff_settings
            WHERE provider_company IS NOT NULL
              AND TRIM(provider_company) <> ''
            """
        )
    ).fetchall()

    for row in existing_names:
        name = str(row[0]).strip()
        if not name:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO providers (name_full, utility_type, adapter_code, is_active, note, created_at)
                SELECT :name, :utility_type, :adapter_code, :is_active, :note, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (
                  SELECT 1 FROM providers WHERE name_full = :name
                )
                """
            ),
            {
                "name": name,
                "utility_type": "other",
                "adapter_code": "manual_stub",
                "is_active": True,
                "note": migrated_note,
            },
        )

    bind.execute(
        sa.text(
            """
            INSERT INTO providers (name_full, utility_type, adapter_code, is_active, note, created_at)
            SELECT :name, :utility_type, :adapter_code, :is_active, :note, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
              SELECT 1 FROM providers WHERE name_full = :name
            )
            """
        ),
        {
            "name": stub_name,
            "utility_type": "other",
            "adapter_code": "manual_stub",
            "is_active": True,
            "note": stub_note,
        },
    )

    provider_rows = bind.execute(sa.text("SELECT id, name_full FROM providers")).fetchall()
    provider_map = {str(name): int(pid) for pid, name in provider_rows}
    stub_id = provider_map.get(stub_name)

    setting_rows = bind.execute(
        sa.text("SELECT id, provider_company FROM apartment_tariff_settings")
    ).fetchall()
    for setting_id, provider_company in setting_rows:
        normalized = str(provider_company).strip() if provider_company is not None else ""
        provider_id = provider_map.get(normalized) if normalized else stub_id
        if provider_id is None:
            continue
        bind.execute(
            sa.text(
                """
                UPDATE apartment_tariff_settings
                SET provider_id = :provider_id
                WHERE id = :setting_id
                """
            ),
            {"provider_id": provider_id, "setting_id": int(setting_id)},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "apartment_tariff_settings" in table_names:
        with op.batch_alter_table("apartment_tariff_settings") as batch_op:
            batch_op.drop_constraint("fk_apartment_tariff_settings_provider_id", type_="foreignkey")
            batch_op.drop_index("ix_apartment_tariff_settings_provider_id")
            batch_op.drop_column("provider_id")

    if "providers" not in table_names:
        return

    op.drop_index("ix_providers_adapter_code", table_name="providers")
    op.drop_index("ix_providers_utility_type", table_name="providers")
    op.drop_index("ix_providers_name_full", table_name="providers")
    op.drop_table("providers")
