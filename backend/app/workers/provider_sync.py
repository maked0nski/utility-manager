from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    ApartmentAutomation,
    Provider,
    ProviderImportBatch,
    ProviderImportBatchStatus,
    ProviderImportRow,
    ProviderImportRowStatus,
    ServiceCatalog,
)
from app.workers.providers import ADAPTERS, ProviderImportRecord
from app.workers.tariff_auto_check import run_tariff_auto_checks


def _parse_targets(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [x for x in parsed if isinstance(x, dict)]


def _discover_targets(db: Session) -> list[dict]:
    rows = (
        db.query(ApartmentAutomation.apartment_id, Provider.adapter_code)
        .join(Provider, Provider.id == ApartmentAutomation.provider_id)
        .filter(ApartmentAutomation.is_enabled == True)
        .filter(Provider.is_active == True)
        .order_by(ApartmentAutomation.apartment_id.asc(), Provider.adapter_code.asc())
        .all()
    )
    seen: set[tuple[int, str]] = set()
    out: list[dict] = []
    for apartment_id, provider_code in rows:
        code = str(provider_code or "").strip()
        if not code or code not in ADAPTERS:
            continue
        key = (int(apartment_id), code)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "apartment_id": int(apartment_id),
                "provider": code,
                "source_ref": "auto-discovered",
            }
        )
    return out


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _stage_batch(
    db: Session,
    apartment_id: int,
    provider_code: str,
    records: list[ProviderImportRecord],
    source_ref: str | None = None,
) -> ProviderImportBatch:
    catalog_by_code = {
        (row.code or "").strip().casefold(): row
        for row in db.query(ServiceCatalog).all()
        if (row.code or "").strip()
    }
    catalog_by_name = {
        (row.name or "").strip().casefold(): row
        for row in db.query(ServiceCatalog).all()
        if (row.name or "").strip()
    }

    batch = ProviderImportBatch(
        apartment_id=apartment_id,
        provider_code=provider_code,
        status=ProviderImportBatchStatus.pending,
        requested_at=datetime.now(UTC),
        source_ref=source_ref,
        raw_meta_json=json.dumps({"records_count": len(records)}),
    )
    db.add(batch)
    db.flush()

    for item in records:
        normalized_code = (item.service_catalog_code or "").strip().casefold()
        normalized_name = (item.service_name or "").strip().casefold()
        catalog = catalog_by_code.get(normalized_code) if normalized_code else None
        if catalog is None and normalized_name:
            catalog = catalog_by_name.get(normalized_name)
        db.add(
            ProviderImportRow(
                batch_id=batch.id,
                service_catalog_code=catalog.code if catalog is not None else (item.service_catalog_code or None),
                service_name=(catalog.name if catalog is not None else item.service_name),
                period_year=item.year,
                period_month=item.month,
                accrued=_to_decimal(item.accrued),
                paid=_to_decimal(item.paid),
                adjustment=_to_decimal(item.adjustment),
                benefit=_to_decimal(item.benefit),
                subsidy=_to_decimal(item.subsidy),
                status=ProviderImportRowStatus.staged,
                raw_payload_json=item.raw_payload_json,
            )
        )

    batch.status = ProviderImportBatchStatus.completed
    batch.finished_at = datetime.now(UTC)
    return batch


def run_once() -> None:
    db = SessionLocal()
    try:
        targets = _parse_targets(os.getenv("PROVIDER_SYNC_TARGETS"))
        if not targets:
            targets = _discover_targets(db)
        if not targets:
            print("provider-sync: no targets configured and no active automations discovered")
        else:
            print(f"provider-sync: targets count={len(targets)}")
        for target in targets:
            apartment_id = int(target.get("apartment_id") or 0)
            provider_code = str(target.get("provider") or "").strip()
            source_ref = str(target.get("source_ref") or "").strip() or None
            if apartment_id <= 0 or not provider_code:
                print(f"provider-sync: skip invalid target {target}")
                continue
            adapter = ADAPTERS.get(provider_code)
            if adapter is None:
                print(f"provider-sync: adapter not found for provider={provider_code}")
                continue
            try:
                records = adapter.fetch_records(apartment_id=apartment_id)
                batch = _stage_batch(
                    db,
                    apartment_id=apartment_id,
                    provider_code=provider_code,
                    records=records,
                    source_ref=source_ref,
                )
                db.commit()
                print(
                    f"provider-sync: staged batch id={batch.id} "
                    f"provider={provider_code} apartment={apartment_id} rows={len(records)}"
                )
            except Exception as error:
                db.rollback()
                failed = ProviderImportBatch(
                    apartment_id=apartment_id,
                    provider_code=provider_code,
                    status=ProviderImportBatchStatus.failed,
                    requested_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                    source_ref=source_ref,
                    error_message=str(error)[:255],
                    raw_meta_json=json.dumps({"target": target}),
                )
                db.add(failed)
                db.commit()
                print(f"provider-sync: failed provider={provider_code} apartment={apartment_id}: {error}")
        run_tariff_auto_checks(db)
    finally:
        db.close()


if __name__ == "__main__":
    run_once()
