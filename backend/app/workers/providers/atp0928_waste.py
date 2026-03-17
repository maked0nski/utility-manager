from __future__ import annotations

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.security import decrypt_text
from app.db.session import SessionLocal
from app.models import Apartment, ApartmentAutomation, ApartmentServiceConnection, Provider, ServiceCatalog
from app.workers.providers.base import ProviderImportRecord
from app.workers.tariff_auto_check import _fetch_atp0928_cabinet_html, _parse_atp0928_accrued_from_html, _prev_month


class ATP0928WasteAdapter:
    provider_code = "if_atp0928_waste"
    provider_codes = ("if_atp0928_waste", "atp0928_if")
    service_catalog_code = "waste"

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

            cabinet_login = (automation.cabinet_login or "").strip()
            cabinet_password = decrypt_text(automation.cabinet_password_encrypted) or ""
            if not cabinet_login or not cabinet_password:
                raise RuntimeError("ATP-0928 adapter: cabinet credentials are missing")

            apartment = db.get(Apartment, apartment_id)
            timezone_name = (apartment.timezone if apartment else None) or "Europe/Kyiv"
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))
            target_year, target_month = _prev_month(local_now.year, local_now.month)

            cabinet_html, cabinet_error = _fetch_atp0928_cabinet_html(
                cabinet_url=(automation.cabinet_url or "").strip() or "https://atp0928.if.ua/osobystyy-kabinet-korystuvacha",
                cabinet_login=cabinet_login,
                cabinet_password=cabinet_password,
            )
            if cabinet_error or cabinet_html is None:
                raise RuntimeError(cabinet_error or "ATP-0928 adapter: failed to read cabinet")

            accrued = _parse_atp0928_accrued_from_html(cabinet_html, target_year, target_month)
            if accrued is None:
                return []

            service_name = "Вивіз сміття"
            connection = db.scalar(
                select(ApartmentServiceConnection)
                .join(ServiceCatalog, ServiceCatalog.id == ApartmentServiceConnection.service_catalog_id)
                .where(ApartmentServiceConnection.apartment_id == apartment_id)
                .where(ServiceCatalog.code == self.service_catalog_code)
                .order_by(ApartmentServiceConnection.started_at.desc(), ApartmentServiceConnection.id.desc())
            )
            if connection is not None and connection.service_catalog and (connection.service_catalog.name or "").strip():
                service_name = connection.service_catalog.name.strip()

            return [
                ProviderImportRecord(
                    service_name=service_name,
                    service_catalog_code=self.service_catalog_code,
                    year=target_year,
                    month=target_month,
                    accrued=accrued,
                    raw_payload_json=json.dumps(
                        {
                            "adapter": self.provider_code,
                            "provider_codes": list(self.provider_codes),
                            "apartment_id": apartment_id,
                            "automation_id": automation.id,
                            "period_year": target_year,
                            "period_month": target_month,
                            "cabinet_url": automation.cabinet_url,
                        },
                        ensure_ascii=False,
                    ),
                )
            ]
        finally:
            db.close()
