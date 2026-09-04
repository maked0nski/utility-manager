from types import SimpleNamespace

from app.workers.tariff_auto_check import _is_gas_ua_setting


def _setting(*, adapter_code=None, provider_company=None, cabinet_url=None, service_code=None):
    provider = SimpleNamespace(adapter_code=adapter_code) if adapter_code is not None else None
    return SimpleNamespace(
        provider=provider,
        provider_company=provider_company,
        cabinet_url=cabinet_url,
        service_code=service_code,
    )


def test_matches_by_adapter_code():
    assert _is_gas_ua_setting(_setting(adapter_code="gas_ua_supply")) is True


def test_matches_by_cabinet_url_fallback():
    assert _is_gas_ua_setting(_setting(cabinet_url="https://my.gas.ua/login")) is True


def test_does_not_match_unrelated_provider():
    assert _is_gas_ua_setting(_setting(adapter_code="atp0928_if", cabinet_url="https://atp0928.if.ua")) is False


def test_does_not_match_empty_setting():
    assert _is_gas_ua_setting(_setting()) is False
