from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from app.core.security import decrypt_text
from app.db.session import SessionLocal
from app.models import Apartment, ApartmentAutomation, ApartmentServiceConnection, Provider, ServiceCatalog
from app.workers.providers.base import ProviderImportRecord
from app.workers.tariff_auto_check import (
    VODOKANAL_AUTH_URL,
    VODOKANAL_CABINET_LOGIN_URL,
    _extract_login_bridge_fields,
    _extract_vodokanal_payload_from_bridge_fields,
    _parse_decimal,
    _prev_month,
)

SERVICE_CONFIG = (
    (
        "water_supply",
        "Водопостачання",
        (
            ("dani_k", "zaborgovanosti", "vodopostachannya_narah"),
            ("dani_k", "zaborgovanosti", "vodopostachannya_narahovano"),
            ("dani_k", "zaborgovanosti", "vodopostachannya_suma"),
            ("dani_k", "zaborgovanosti", "vodopostachannya_do_splaty"),
        ),
    ),
    (
        "sewage",
        "Водовідведення",
        (
            ("dani_k", "zaborgovanosti", "vodovidvedennya_narah"),
            ("dani_k", "zaborgovanosti", "vodovidvedennya_narahovano"),
            ("dani_k", "zaborgovanosti", "vodovidvedennya_suma"),
            ("dani_k", "zaborgovanosti", "vodovidvedennya_do_splaty"),
        ),
    ),
    (
        "water_subscription",
        "Абонентська плата (водоканал)",
        (
            ("dani_k", "zaborgovanosti", "abon_narah"),
            ("dani_k", "zaborgovanosti", "abon_narahovano"),
            ("dani_k", "zaborgovanosti", "abon_suma"),
            ("dani_k", "zaborgovanosti", "abon_do_splaty"),
        ),
    ),
)


def _deep_get(payload: dict, path: tuple[str, ...]) -> object | None:
    current: object = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _extract_amount(payload: dict, paths: tuple[tuple[str, ...], ...]) -> Decimal | None:
    for path in paths:
        raw = _deep_get(payload, path)
        if raw is None or raw == "":
            continue
        parsed = _parse_decimal(str(raw))
        if parsed is not None:
            return parsed
    return None


class VodokanalIFAdapter:
    provider_code = "if_vodokanal"
    provider_codes = ("if_vodokanal", "vodokanal_if")

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
                raise RuntimeError("Vodokanal adapter: cabinet credentials are missing")

            login_url = (automation.cabinet_url or "").strip() or VODOKANAL_CABINET_LOGIN_URL
            login_url = login_url.rstrip("/") + "/"
            apartment = db.get(Apartment, apartment_id)
            timezone_name = (apartment.timezone if apartment else None) or "Europe/Kyiv"
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))
            target_year, target_month = _prev_month(local_now.year, local_now.month)

            with httpx.Client(follow_redirects=True, timeout=25.0) as client:
                auth = client.post(VODOKANAL_AUTH_URL, data={"login": cabinet_login, "password": cabinet_password})
            if auth.status_code != 200:
                raise RuntimeError(f"Vodokanal adapter: auth HTTP {auth.status_code}")

            bridge_fields = _extract_login_bridge_fields(auth.text)
            if not bridge_fields:
                raise RuntimeError("Vodokanal adapter: auth bridge fields were not found")

            payload = _extract_vodokanal_payload_from_bridge_fields(bridge_fields)
            if (payload.get("stat") or "").strip().lower() != "ok":
                raise RuntimeError("Vodokanal adapter: auth status is not OK")

            connection_by_code: dict[str, ApartmentServiceConnection] = {}
            connections = db.scalars(
                select(ApartmentServiceConnection)
                .join(ServiceCatalog, ServiceCatalog.id == ApartmentServiceConnection.service_catalog_id)
                .where(ApartmentServiceConnection.apartment_id == apartment_id)
                .where(ServiceCatalog.code.in_([code for code, _, _ in SERVICE_CONFIG]))
                .order_by(ApartmentServiceConnection.started_at.desc(), ApartmentServiceConnection.id.desc())
            ).all()
            for connection in connections:
                code = (connection.service_catalog.code if connection.service_catalog else "").strip()
                if code and code not in connection_by_code:
                    connection_by_code[code] = connection

            records: list[ProviderImportRecord] = []
            for service_code, default_label, amount_paths in SERVICE_CONFIG:
                accrued = _extract_amount(payload, amount_paths)
                if accrued is None:
                    continue
                connection = connection_by_code.get(service_code)
                service_label = default_label
                if connection is not None and connection.service_catalog and (connection.service_catalog.name or "").strip():
                    service_label = connection.service_catalog.name.strip()
                records.append(
                    ProviderImportRecord(
                        service_name=service_label,
                        service_catalog_code=service_code,
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
                                "osr": payload.get("osr"),
                            },
                            ensure_ascii=False,
                        ),
                    )
                )

            return records
        finally:
            db.close()
