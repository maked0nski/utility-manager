from datetime import UTC, datetime
from decimal import Decimal

from app.workers.tariff_auto_check import (
    _is_day_in_window,
    _next_run_at,
    _round_up_to_half,
    _parse_atp0928_accrued_from_html,
    _parse_atp0928_tariff_from_html,
    _parse_vodokanal_tariffs,
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


def test_parse_vodokanal_tariffs_from_dashboard_cards():
    long_gap = "x" * 2500
    html = f"""
    <div class="card">
      <div class="card-header bg-light"><h5 class="m-0">Послуга водопостачання</h5></div>
      <div class="card-body">{long_gap}<ul><li>Тариф: 12.95 грн/м<sup>3</sup></li></ul></div>
    </div>
    <div class="card">
      <div class="card-header bg-light"><h5 class="m-0">Послуга водовідведення</h5></div>
      <div class="card-body"><ul><li>Тариф: 15.29 грн/м<sup>3</sup></li></ul></div>
    </div>
    <div class="card">
      <div class="card-header bg-light"><h5 class="m-0">Абонплата</h5></div>
      <div class="card-body"><ul><li>Тариф: 24.67 грн/м<sup>3</sup></li></ul></div>
    </div>
    """
    parsed = _parse_vodokanal_tariffs(html)
    assert parsed["Водопостачання"] == Decimal("12.95")
    assert parsed["Водовідведення"] == Decimal("15.29")
    assert parsed["Абонентська плата (водоканал)"] == Decimal("24.67")


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
    assert _parse_atp0928_tariff_from_html(html, "Вивіз сміття") == Decimal("59.88")
    assert _parse_atp0928_tariff_from_html(html, "Вивіз сміття (приватний сектор)") == Decimal("61.72")


def test_round_up_to_half_for_atp0928_update_rule():
    assert _round_up_to_half(Decimal("59.88")) == Decimal("60")
    assert _round_up_to_half(Decimal("60.00")) == Decimal("60")
    assert _round_up_to_half(Decimal("60.01")) == Decimal("60.5")
