from __future__ import annotations

import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.security import decrypt_text
from app.db.session import SessionLocal
from app.models import Apartment, ApartmentAutomation, ApartmentServiceConnection, Provider, ServiceCalculationKind
from app.workers.providers.base import ProviderImportRecord
from app.workers.tariff_auto_check import _fetch_visualservice_kvartplata, _prev_month


def _connection_active_on(connection: ApartmentServiceConnection, target_date: date) -> bool:
    if connection.started_at and connection.started_at > target_date:
        return False
    if connection.ended_at and connection.ended_at < target_date:
        return False
    return (connection.status or "active").strip().lower() != "inactive"


class VisualServiceFixedAdapter:
    provider_code = "visualservice_fixed"
    provider_codes = ("visualservice_fixed",)

    def fetch_records(self, apartment_id: int) -> list[ProviderImportRecord]:
        db = SessionLocal()
        try:
            automation = db.scalar(
                select(ApartmentAutomation)
                .join(Provider, Provider.id == ApartmentAutomation.provider_id)
                .where(ApartmentAutomation.apartment_id == apartment_id)
                .where(ApartmentAutomation.is_enabled == True)
                .where(Provider.is_active == True)
                .where(Provider.adapter_code.in_(self.provider_codes))
                .order_by(ApartmentAutomation.id.asc())
            )
            if automation is None:
                return []

            login_url = (automation.cabinet_url or "").strip()
            cabinet_login = (automation.cabinet_login or "").strip()
            cabinet_password = decrypt_text(automation.cabinet_password_encrypted) or ""
            if not login_url:
                raise RuntimeError("VisualService adapter: cabinet_url is empty")
            if not cabinet_login or not cabinet_password:
                raise RuntimeError("VisualService adapter: cabinet credentials are missing")

            apartment = db.get(Apartment, apartment_id)
            timezone_name = (apartment.timezone if apartment else None) or "Europe/Kyiv"
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))
            target_year, target_month = _prev_month(local_now.year, local_now.month)
            period_start = date(target_year, target_month, 1)
            balance_url = login_url.rstrip("/") + "/balance/"

            connections = db.scalars(
                select(ApartmentServiceConnection)
                .where(ApartmentServiceConnection.apartment_id == apartment_id)
                .where(ApartmentServiceConnection.automation_id == automation.id)
                .order_by(ApartmentServiceConnection.started_at.desc(), ApartmentServiceConnection.id.desc())
            ).all()

            records: list[ProviderImportRecord] = []
            for connection in connections:
                if not _connection_active_on(connection, period_start):
                    continue
                catalog = connection.service_catalog
                if catalog is None or catalog.calculation_kind != ServiceCalculationKind.fixed:
                    continue
                service_label = (catalog.name or "").strip()
                service_code = (catalog.code or "").strip() or None
                if not service_label:
                    continue

                result = _fetch_visualservice_kvartplata(
                    login_url=login_url,
                    balance_url=balance_url,
                    cabinet_login=cabinet_login,
                    cabinet_password=cabinet_password,
                    service_label=service_label,
                    target_year=target_year,
                    target_month=target_month,
                )
                if result.status != "found" or result.raw_value is None:
                    continue

                records.append(
                    ProviderImportRecord(
                        service_name=service_label,
                        service_catalog_code=service_code,
                        year=target_year,
                        month=target_month,
                        accrued=result.raw_value,
                        raw_payload_json=json.dumps(
                            {
                                "adapter": self.provider_code,
                                "apartment_id": apartment_id,
                                "automation_id": automation.id,
                                "connection_id": connection.id,
                                "service_catalog_code": service_code,
                                "period_year": target_year,
                                "period_month": target_month,
                                "balance_url": balance_url,
                            },
                            ensure_ascii=False,
                        ),
                    )
                )

            return records
        finally:
            db.close()
