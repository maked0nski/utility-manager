from datetime import UTC, datetime
from decimal import Decimal

from app.workers.tariff_auto_check import (
    _is_day_in_window,
    _next_run_at,
    _round_up_to_half,
    _parse_atp0928_accrued_from_html,
    _parse_atp0928_tariff_from_html,
    _parse_vodokanal_tariffs,
    _parse_vkcab_price,
    _extract_vkcab_osr,
    _vodokanal_acceptable_submission_periods,
)


def test_is_day_in_window_regular_range():
    assert _is_day_in_window(5, 1, 10) is True
    assert _is_day_in_window(15, 1, 10) is False


def test_is_day_in_window_cross_month_range():
    assert _is_day_in_window(26, 25, 3) is True
    assert _is_day_in_window(2, 25, 3) is True
    assert _is_day_in_window(10, 25, 3) is False


def test_next_run_at_cross_month_window_after_today_slot():
    tz = UTC
    local_now = datetime(2026, 3, 1, 12, 0, tzinfo=tz)

    next_utc = _next_run_at(local_now, tz, hh=9, mm=0, day_from=25, day_to=3)
    next_local = next_utc.astimezone(tz)

    assert next_local.year == 2026
    assert next_local.month == 3
    assert next_local.day == 2
    assert next_local.hour == 9
    assert next_local.minute == 0
    assert next_utc.tzinfo == UTC


def test_parse_vodokanal_tariffs_from_vkcab_bootstrap():
    # Since the 2026 site redesign, tariffs come from the public (unauthenticated)
    # `VKCAB.tarify` JSON embedded on the kabinet page, keyed by "voda"/"kanal"/"abon".
    # _parse_vodokanal_tariffs maps those to internal service codes
    # ("water_supply", "sewage", "water_subscription").
    bootstrap = {
        "tarify": {
            "voda": {"t": "35,45 грн/м³", "from": "09.07.2026"},
            "kanal": {"t": "30,06 грн/м³", "from": "09.07.2026"},
            "abon": {"t": "24.67 грн/м³", "from": "01.04.2022"},
        }
    }
    parsed = _parse_vodokanal_tariffs(bootstrap)
    assert parsed["water_supply"] == Decimal("35.45")
    assert parsed["sewage"] == Decimal("30.06")
    assert parsed["water_subscription"] == Decimal("24.67")


def test_parse_vodokanal_tariffs_missing_entries():
    parsed = _parse_vodokanal_tariffs({"tarify": {"voda": {"t": "35,45 грн/м³"}}})
    assert parsed == {"water_supply": Decimal("35.45")}
    assert _parse_vodokanal_tariffs({}) == {}


def test_parse_vkcab_price_strips_unit_suffix_and_comma_decimal():
    assert _parse_vkcab_price("35,45 грн/м³") == Decimal("35.45")
    assert _parse_vkcab_price("24.67 грн/м³") == Decimal("24.67")
    assert _parse_vkcab_price(None) is None
    assert _parse_vkcab_price("") is None


def test_extract_vkcab_osr_from_dashboard_markup():
    html = '<div id="vkcab-app" data-osr="812363" data-agree="0">'
    assert _extract_vkcab_osr(html) == "812363"
    assert _extract_vkcab_osr("<div>no app here</div>") is None


def test_vodokanal_acceptable_submission_periods_cross_month_window():
    # Target period August 2026, window 25..3 straddles Aug and Sep -
    # a submission near the window's start or end could be filed under either.
    periods = _vodokanal_acceptable_submission_periods(2026, 8, day_from=25, day_to=3)
    assert periods == {202608, 202609}


def test_vodokanal_acceptable_submission_periods_year_rollover():
    periods = _vodokanal_acceptable_submission_periods(2026, 12, day_from=25, day_to=3)
    assert periods == {202612, 202701}


def test_vodokanal_acceptable_submission_periods_non_cross_month_window():
    # A regular (non cross-month) window doesn't straddle two calendar months.
    periods = _vodokanal_acceptable_submission_periods(2026, 8, day_from=1, day_to=10)
    assert periods == {202608}


def test_parse_atp0928_accrued_from_html_table():
    html = """
    <table>
      <tr><th>Період</th><th>Нараховано, грн</th></tr>
      <tr><td>02.2026</td><td>59,88</td></tr>
      <tr><td>01.2026</td><td>57,11</td></tr>
    </table>
    """
    value = _parse_atp0928_accrued_from_html(html, target_year=2026, target_month=2)
    assert value == Decimal("59.88")


def test_parse_atp0928_tariff_from_html_prefers_apartment_row():
    html = """
    <table>
      <tr><th>Послуга</th><th>Одиниця виміру</th><th>Вартість, грн</th></tr>
      <tr><td>Управління побутовими відходами для мешканців багатоквартирних будинків</td><td>грн/ людину в місяць</td><td>59,88</td></tr>
      <tr><td>Управління побутовими відходами для мешканців житлових будинків індивідуальної забудови</td><td>грн/ людину в місяць</td><td>61,72</td></tr>
    </table>
    """
    # service_code is always the short internal ServiceCatalog.code slug
    # (e.g. "waste", "water_supply"), never the Ukrainian display label - see
    # its real caller at tariff_auto_check.py:913 (`setting.service_code`,
    # populated from `connection.service_catalog.code`). The "private
    # sector" branch checks for {"waste_private", "waste_individual"}.
    assert _parse_atp0928_tariff_from_html(html, "waste") == Decimal("59.88")
    assert _parse_atp0928_tariff_from_html(html, "waste_private") == Decimal("61.72")


def test_round_up_to_half_for_atp0928_update_rule():
    assert _round_up_to_half(Decimal("59.88")) == Decimal("60")
    assert _round_up_to_half(Decimal("60.00")) == Decimal("60")
    assert _round_up_to_half(Decimal("60.01")) == Decimal("60.5")
