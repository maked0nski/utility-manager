from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(slots=True)
class ProviderImportRecord:
    service_name: str
    service_catalog_code: str | None = None
    year: int
    month: int
    accrued: Decimal
    paid: Decimal = Decimal("0.00")
    adjustment: Decimal = Decimal("0.00")
    benefit: Decimal = Decimal("0.00")
    subsidy: Decimal = Decimal("0.00")
    raw_payload_json: str | None = None


class ProviderSyncAdapter(Protocol):
    provider_code: str

    def fetch_records(self, apartment_id: int) -> list[ProviderImportRecord]:
        """Return normalized provider records for staging import."""
