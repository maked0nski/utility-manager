from app.workers.providers.base import ProviderImportRecord, ProviderSyncAdapter
from app.workers.providers.atp0928_waste import ATP0928WasteAdapter
from app.workers.providers.manual_stub import ManualStubAdapter
from app.workers.providers.visualservice_fixed import VisualServiceFixedAdapter
from app.workers.providers.vodokanal_if import VodokanalIFAdapter

ADAPTERS = {
    ManualStubAdapter.provider_code: ManualStubAdapter(),
    ATP0928WasteAdapter.provider_code: ATP0928WasteAdapter(),
    "atp0928_if": ATP0928WasteAdapter(),
    VisualServiceFixedAdapter.provider_code: VisualServiceFixedAdapter(),
    VodokanalIFAdapter.provider_code: VodokanalIFAdapter(),
    "vodokanal_if": VodokanalIFAdapter(),
}

__all__ = [
    "ADAPTERS",
    "ProviderImportRecord",
    "ProviderSyncAdapter",
]
