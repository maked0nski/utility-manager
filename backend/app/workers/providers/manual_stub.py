from __future__ import annotations

from app.workers.providers.base import ProviderImportRecord


class ManualStubAdapter:
    provider_code = "manual_stub"

    def fetch_records(self, apartment_id: int) -> list[ProviderImportRecord]:
        # Placeholder adapter: real providers will parse cabinet/API data here.
        return []
