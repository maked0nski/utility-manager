from decimal import Decimal

from app.workers.tariff_auto_check import _parse_gas_ua_price_from_html

# Real (redacted of PII beyond what's already public in this repo's design docs)
# fragment captured live from GET /home on 2026-09-04, matching the actual
# markup shape: a `<personal-accounts-dropdown user_info="...">` component
# whose attribute is an HTML-entity-escaped JSON object.
REAL_FRAGMENT = (
    '<personal-accounts-dropdown class_names="nav-item" '
    'user_info="{&quot;kodr&quot;:&quot;801685457&quot;,&quot;peracc&quot;:&quot;160026427&quot;,'
    '&quot;pay_lastsum&quot;:&quot;2451.85&quot;,&quot;beforelimit_price&quot;:&quot;7.95689&quot;,'
    '&quot;afterlimit_price&quot;:&quot;7.95689&quot;,&quot;single_price&quot;:&quot;7.95689&quot;,'
    '&quot;priv_percent&quot;:&quot;&quot;}" />'
)


def test_parses_real_captured_fragment():
    assert _parse_gas_ua_price_from_html(REAL_FRAGMENT) == Decimal("7.95689")


def test_returns_none_when_component_missing():
    assert _parse_gas_ua_price_from_html("<div>no such component here</div>") is None


def test_returns_none_when_user_info_is_not_valid_json():
    html = '<personal-accounts-dropdown user_info="{not json" />'
    assert _parse_gas_ua_price_from_html(html) is None


def test_returns_none_when_single_price_key_missing():
    html = '<personal-accounts-dropdown user_info="{&quot;kodr&quot;:&quot;1&quot;}" />'
    assert _parse_gas_ua_price_from_html(html) is None


def test_returns_none_when_single_price_is_empty_string():
    html = '<personal-accounts-dropdown user_info="{&quot;single_price&quot;:&quot;&quot;}" />'
    assert _parse_gas_ua_price_from_html(html) is None


def test_returns_none_when_user_info_is_json_array():
    html = '<personal-accounts-dropdown user_info="[]" />'
    assert _parse_gas_ua_price_from_html(html) is None


def test_returns_none_when_user_info_is_json_scalar():
    html = '<personal-accounts-dropdown user_info="123" />'
    assert _parse_gas_ua_price_from_html(html) is None


def test_returns_none_when_user_info_is_json_null():
    html = '<personal-accounts-dropdown user_info="null" />'
    assert _parse_gas_ua_price_from_html(html) is None
