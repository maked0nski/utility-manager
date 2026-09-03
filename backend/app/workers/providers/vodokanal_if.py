from __future__ import annotations

from app.workers.providers.base import ProviderImportRecord


class VodokanalIFAdapter:
    provider_code = "if_vodokanal"
    provider_codes = ("if_vodokanal", "vodokanal_if")

    def fetch_records(self, apartment_id: int) -> list[ProviderImportRecord]:
        # vodokanal.if.ua replaced its old cabinet (the bridge-auth flow this
        # adapter used to scrape "нараховано" amounts from) with a WordPress
        # AJAX-based one in 2026. The new API (see `_run_vodokanal` in
        # tariff_auto_check.py) exposes tariffs and a debt/balance snapshot
        # (`borg`), not a per-month accrued amount, so this adapter needs a
        # proper redesign rather than a drop-in swap. Fail loudly (caught by
        # provider_sync's per-apartment try/except) instead of silently
        # returning nothing.
        raise RuntimeError(
            "Vodokanal adapter: fetch_records is not implemented for the redesigned "
            "vodokanal.if.ua cabinet yet; see _run_vodokanal in tariff_auto_check.py "
            "for the current login/data flow this needs to be rebuilt on."
        )
