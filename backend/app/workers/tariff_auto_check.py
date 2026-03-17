from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from html import unescape
import json
import re
import socket
import time
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.api.admin import _recalc_from_period
from app.core.security import decrypt_text
from app.models import (
    Apartment,
    ApartmentAutomation,
    ApartmentServiceConnection,
    AutomationCyclePhaseRun,
    AutomationCycleRun,
    AutomationRunLog,
    ChargeMode,
    ConnectionChargeLine,
    Meter,
    MeterReading,
    Provider,
)
from app.services.tariff_rules import fixed_charge_multiplier

UK_MONTHS = {
    1: "січень",
    2: "лютий",
    3: "березень",
    4: "квітень",
    5: "травень",
    6: "червень",
    7: "липень",
    8: "серпень",
    9: "вересень",
    10: "жовтень",
    11: "листопад",
    12: "грудень",
}

VODOKANAL_CABINET_LOGIN_URL = "https://new.vodokanal.if.ua/kabinet-spozhyvacha/pereity-v-kabinet-spozhyvacha/"
VODOKANAL_AUTH_URL = "https://vodokanal.if.ua/propibank/newcab.php"
ATP0928_CABINET_URL = "https://atp0928.if.ua/osobystyy-kabinet-korystuvacha"
ATP0928_LOGIN_URL = "https://atp0928.if.ua/wp-login.php"
ATP0928_TARIFF_URL = "https://atp0928.if.ua/tarif"

VODOKANAL_SERVICE_CARD_MAP: dict[str, tuple[str, str]] = {
    "Послуга водопостачання": ("water_supply", "Водопостачання"),
    "Послуга водовідведення": ("sewage", "Водовідведення"),
    "Абонплата": ("water_subscription", "Абонентська плата (водоканал)"),
}

VODOKANAL_SERVICE_CODES = {code for code, _ in VODOKANAL_SERVICE_CARD_MAP.values()}
VODOKANAL_SERVICE_LABELS = {code: label for code, label in VODOKANAL_SERVICE_CARD_MAP.values()}
VODOKANAL_READING_DRIVER_CODE = "water_supply"
ATP0928_SERVICE_CODE = "waste"


@dataclass(slots=True)
class VisualServiceCheckResult:
    status: str
    message: str
    raw_value: Decimal | None = None


@dataclass(slots=True)
class AutomationBindingContext:
    apartment_id: int
    connection_id: int
    service_catalog_id: int | None
    service_code: str | None
    service_name: str
    provider_id: int | None
    provider_company: str | None
    provider: Provider | None
    cabinet_url: str | None
    cabinet_login: str | None
    cabinet_password_encrypted: str | None
    personal_account: str | None
    auto_check_enabled: bool
    auto_check_time: str
    auto_check_timezone: str
    auto_check_window_day_from: int
    auto_check_window_day_to: int
    auto_check_target_year: int | None = None
    auto_check_target_month: int | None = None
    auto_check_completed_for_period: bool = False
    auto_check_status: str | None = None
    auto_check_message: str | None = None
    auto_check_last_value_raw: Decimal | None = None
    auto_check_last_value_rounded: Decimal | None = None
    auto_check_last_checked_at: datetime | None = None
    auto_check_last_updated_at: datetime | None = None
    auto_check_next_at: datetime | None = None
    last_tariff_check_at: datetime | None = None
    related_bindings: dict[str, "AutomationBindingContext"] | None = None


BindingSetting = AutomationBindingContext


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(int((finished_at - started_at).total_seconds() * 1000), 0)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year=year, month=month, day=1, tzinfo=UTC)


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _only_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _extract_td(row_html: str, label: str) -> str:
    pattern = re.compile(
        r'<td[^>]*data-label="' + re.escape(label) + r'"[^>]*>(.*?)</td>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(row_html)
    if not match:
        return ""
    return _only_text(match.group(1))


def _extract_link_by_caption(html: str, caption: str) -> str | None:
    pattern = re.compile(
        r'<a[^>]*href="([^"]+)"[^>]*>\s*' + re.escape(caption) + r"\s*</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    found = pattern.search(html)
    if not found:
        return None
    return found.group(1).strip()


def _extract_login_bridge_fields(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for input_tag in re.findall(r"<input\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL):
        attrs: dict[str, str] = {}
        for attr_match in re.finditer(
            r'([a-zA-Z_:][a-zA-Z0-9_.:-]*)\s*=\s*([\'"])(.*?)\2',
            input_tag,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            attrs[attr_match.group(1).lower()] = unescape(attr_match.group(3))
        name = attrs.get("name")
        if not name:
            continue
        fields[name] = attrs.get("value", "")
    return fields


def _extract_form(html: str) -> tuple[str | None, str] | None:
    form_match = re.search(r"<form[^>]*>(.*?)</form>", html, flags=re.IGNORECASE | re.DOTALL)
    if not form_match:
        return None
    whole_form = form_match.group(0)
    action_match = re.search(r'action=[\'"]([^\'"]*)[\'"]', whole_form, flags=re.IGNORECASE)
    action = action_match.group(1).strip() if action_match else None
    return action, form_match.group(1)


def _extract_form_by_id(html: str, form_id: str) -> tuple[str | None, str | None, dict[str, str]] | None:
    pattern = re.compile(
        r'<form[^>]*id=[\'"]' + re.escape(form_id) + r'[\'"][^>]*>(.*?)</form>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return None
    whole_form = match.group(0)
    action_match = re.search(r'action=[\'"]([^\'"]*)[\'"]', whole_form, flags=re.IGNORECASE)
    method_match = re.search(r'method=[\'"]([^\'"]*)[\'"]', whole_form, flags=re.IGNORECASE)
    action = action_match.group(1).strip() if action_match else None
    method = method_match.group(1).strip().lower() if method_match else "get"
    body = match.group(1)
    fields: dict[str, str] = {}
    for input_tag in re.findall(r"<input\b[^>]*>", body, flags=re.IGNORECASE | re.DOTALL):
        attrs: dict[str, str] = {}
        for attr_match in re.finditer(
            r'([a-zA-Z_:][a-zA-Z0-9_.:-]*)\s*=\s*([\'"])(.*?)\2',
            input_tag,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            attrs[attr_match.group(1).lower()] = unescape(attr_match.group(3))
        name = attrs.get("name")
        if not name:
            continue
        fields[name] = attrs.get("value", "")
    return action, method, fields


def _extract_vodokanal_submit_form(html: str) -> tuple[str, str, dict[str, str]] | None:
    forms = re.finditer(r"<form[^>]*>.*?</form>", html, flags=re.IGNORECASE | re.DOTALL)
    for form_match in forms:
        whole_form = form_match.group(0)
        action_match = re.search(r'action=[\'"]([^\'"]*)[\'"]', whole_form, flags=re.IGNORECASE)
        method_match = re.search(r'method=[\'"]([^\'"]*)[\'"]', whole_form, flags=re.IGNORECASE)
        action = (action_match.group(1).strip() if action_match else "")
        method = (method_match.group(1).strip().lower() if method_match else "get")
        if "viberpokaz2.php" not in action:
            continue
        fields: dict[str, str] = {}
        for input_tag in re.findall(r"<input\b[^>]*>", whole_form, flags=re.IGNORECASE | re.DOTALL):
            attrs: dict[str, str] = {}
            for attr_match in re.finditer(
                r'([a-zA-Z_:][a-zA-Z0-9_.:-]*)\s*=\s*([\'"])(.*?)\2',
                input_tag,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                attrs[attr_match.group(1).lower()] = unescape(attr_match.group(3))
            name = attrs.get("name")
            if not name:
                continue
            fields[name] = attrs.get("value", "")
        if "pokaz" in fields and "osr" in fields and "nlichn" in fields:
            return action, method, fields
    return None


def _parse_vodokanal_stats_rows(stats_html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row_html in re.findall(r"<tr[^>]*>.*?</tr>", stats_html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        texts = [_only_text(c) for c in cells]
        if len(texts) < 7:
            continue
        # Expected order: month, location, meter name, meter number, verification date, value, submitted date
        rows.append(
            {
                "month": texts[0],
                "location": texts[1],
                "meter_name": texts[2],
                "meter_number": texts[3],
                "verification_date": texts[4],
                "value": texts[5],
                "submitted_date": texts[6],
            }
        )
    return rows


def _vodokanal_target_period(local_now: datetime, day_from: int, day_to: int) -> tuple[int, int]:
    # For cross-month window like 25..3:
    # 25..end of month -> same month, 1..3 -> previous month.
    if day_from > day_to:
        if local_now.day >= day_from:
            return local_now.year, local_now.month
        return _prev_month(local_now.year, local_now.month)
    # Fallback for provider business rule even if UI still has legacy 1..10 window.
    if local_now.day <= 3:
        return _prev_month(local_now.year, local_now.month)
    if local_now.day >= 25:
        return local_now.year, local_now.month
    return local_now.year, local_now.month


def _build_month_short_label(year: int, month: int) -> str:
    return f"{month:02d}.{str(year)[-2:]}"


def _build_month_full_label(year: int, month: int) -> str:
    return f"{month:02d}.{year}"


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = value.strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", cleaned):
        return None
    return Decimal(cleaned)


def _parse_decimal_from_text(value: str) -> Decimal | None:
    compact = value.replace("\xa0", " ")
    match = re.search(r"([0-9]+(?:[ .,][0-9]{1,4})?)", compact)
    if not match:
        return None
    token = match.group(1).replace(" ", "").replace(",", ".")
    if token.count(".") > 1:
        parts = token.split(".")
        token = "".join(parts[:-1]) + "." + parts[-1]
    return _parse_decimal(token)


def _extract_table_rows(html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr[^>]*>.*?</tr>", html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        rows.append([_only_text(cell) for cell in cells])
    return rows


def _matches_period_label(period_text: str, target_year: int, target_month: int) -> bool:
    normalized = period_text.strip().lower().replace("\xa0", " ")
    if not normalized:
        return False
    month_name = UK_MONTHS[target_month]
    year_short = str(target_year)[-2:]
    direct_labels = {
        f"{target_month:02d}.{target_year}",
        f"{target_month:02d}/{target_year}",
        f"{target_month:02d}-{target_year}",
        f"{target_month:02d}.{year_short}",
        f"{target_month:02d}/{year_short}",
        f"{target_month:02d}-{year_short}",
    }
    if normalized in direct_labels:
        return True
    if month_name in normalized and str(target_year) in normalized:
        return True
    return False


def _parse_atp0928_accrued_from_html(html: str, target_year: int, target_month: int) -> Decimal | None:
    for table_html in re.findall(r"<table[^>]*>.*?</table>", html, flags=re.IGNORECASE | re.DOTALL):
        rows = _extract_table_rows(table_html)
        if len(rows) < 2:
            continue
        header = [x.lower() for x in rows[0]]
        period_idx = next((idx for idx, name in enumerate(header) if "період" in name or "місяц" in name), None)
        accrued_idx = next((idx for idx, name in enumerate(header) if "нараховано" in name), None)
        if period_idx is None or accrued_idx is None:
            continue
        for row in rows[1:]:
            if period_idx >= len(row) or accrued_idx >= len(row):
                continue
            if not _matches_period_label(row[period_idx], target_year, target_month):
                continue
            parsed = _parse_decimal_from_text(row[accrued_idx])
            if parsed is not None:
                return parsed

    text = _only_text(html)
    month_name = UK_MONTHS[target_month]
    year_short = str(target_year)[-2:]
    tokens = [
        f"{target_month:02d}.{target_year}",
        f"{target_month:02d}/{target_year}",
        f"{target_month:02d}-{target_year}",
        f"{target_month:02d}.{year_short}",
        f"{month_name} {target_year}",
    ]
    for token in tokens:
        pattern = re.compile(
            re.escape(token) + r".{0,180}?Нараховано[^0-9]{0,24}([0-9]+(?:[.,][0-9]{1,4})?)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if match:
            parsed = _parse_decimal(match.group(1).replace(",", "."))
            if parsed is not None:
                return parsed
    return None


def _parse_atp0928_tariff_from_html(html: str, service_code: str | None) -> Decimal | None:
    candidate_rows: list[tuple[str, Decimal]] = []
    for table_html in re.findall(r"<table[^>]*>.*?</table>", html, flags=re.IGNORECASE | re.DOTALL):
        rows = _extract_table_rows(table_html)
        if len(rows) < 2:
            continue
        header = [x.lower() for x in rows[0]]
        service_idx = next((idx for idx, name in enumerate(header) if "послуга" in name), None)
        value_idx = next((idx for idx, name in enumerate(header) if "вартість" in name), None)
        if service_idx is None or value_idx is None:
            continue
        for row in rows[1:]:
            if service_idx >= len(row) or value_idx >= len(row):
                continue
            parsed = _parse_decimal_from_text(row[value_idx])
            if parsed is None:
                continue
            candidate_rows.append((row[service_idx].lower(), parsed))

    if not candidate_rows:
        return None

    if service_code in {"waste_private", "waste_individual"}:
        for label, value in candidate_rows:
            if "індивідуаль" in label or "приват" in label:
                return value
    for label, value in candidate_rows:
        if "багатоквартир" in label:
            return value
    return candidate_rows[0][1]


def _round_up_to_half(value: Decimal) -> Decimal:
    return (value * Decimal("2")).to_integral_value(rounding=ROUND_CEILING) / Decimal("2")


def _resolve_check_time(hhmm: str | None) -> tuple[int, int]:
    if not hhmm:
        return 9, 0
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", hhmm.strip())
    if not match:
        return 9, 0
    return int(match.group(1)), int(match.group(2))


def _is_day_in_window(day: int, day_from: int, day_to: int) -> bool:
    if day_from <= day_to:
        return day_from <= day <= day_to
    return day >= day_from or day <= day_to


def _target_period_for_window(local_now: datetime, day_from: int, day_to: int) -> tuple[int, int]:
    if day_from > day_to:
        if local_now.day >= day_from:
            return local_now.year, local_now.month
        return _prev_month(local_now.year, local_now.month)
    return local_now.year, local_now.month


def _next_run_at(local_now: datetime, tz: ZoneInfo, hh: int, mm: int, day_from: int, day_to: int) -> datetime:
    today_at = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    in_window = _is_day_in_window(local_now.day, day_from, day_to)

    if in_window and local_now < today_at:
        return today_at.astimezone(UTC)

    candidate = local_now + timedelta(days=1)
    for _ in range(62):
        if _is_day_in_window(candidate.day, day_from, day_to):
            target_local = candidate.replace(hour=hh, minute=mm, second=0, microsecond=0)
            return target_local.astimezone(UTC)
        candidate += timedelta(days=1)

    # Fallback should never happen; keeps scheduler stable.
    return (local_now + timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0).astimezone(UTC)


def _fetch_visualservice_kvartplata(
    *,
    login_url: str,
    balance_url: str,
    cabinet_login: str,
    cabinet_password: str,
    service_label: str,
    target_year: int,
    target_month: int,
) -> VisualServiceCheckResult:
    parsed = urlparse(login_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    login_ajax = urljoin(base_url, "/ajax/login/loginCD.php")
    month_label = f"{UK_MONTHS[target_month].capitalize()} {target_year}"
    month_label_cmp = month_label.casefold()
    service_cmp = service_label.strip().casefold()

    last_error: str | None = None
    for attempt in range(1, 4):
        try:
            with httpx.Client(follow_redirects=True, timeout=20.0) as client:
                login_page = client.get(login_url)
                auth = client.post(
                    login_ajax,
                    # VisualService uses l/p in AJAX payload. Keep login/password as fallback.
                    data={"l": cabinet_login, "p": cabinet_password, "login": cabinet_login, "password": cabinet_password},
                )
                if auth.status_code != 200:
                    return VisualServiceCheckResult(status="error", message=f"Login failed: HTTP {auth.status_code}")

                balance = client.get(balance_url)
                if balance.status_code != 200:
                    return VisualServiceCheckResult(status="error", message=f"Balance failed: HTTP {balance.status_code}")
                if "/login" in balance.url.path:
                    return VisualServiceCheckResult(
                        status="error",
                        message=(
                            "Authorization failed: redirected to /login/. "
                            f"login_page={login_page.status_code}, auth={auth.status_code}, balance_url={balance.url}"
                        ),
                    )

                html = balance.text
                rows = re.findall(r"<tr[^>]*class=\"[^\"]*tr-href[^\"]*\"[^>]*>.*?</tr>", html, flags=re.IGNORECASE | re.DOTALL)
                if not rows:
                    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
                    page_title = _only_text(title_match.group(1)) if title_match else "n/a"
                    return VisualServiceCheckResult(
                        status="error",
                        message=f"Balance rows not found; url={balance.url}; title={page_title}",
                    )

                for row_html in rows:
                    row_service = _extract_td(row_html, "Різновид послуг")
                    row_period = _extract_td(row_html, "Період")
                    if row_service.casefold() != service_cmp or row_period.casefold() != month_label_cmp:
                        continue
                    accrued_text = _extract_td(row_html, "Нараховано, грн")
                    if not accrued_text:
                        return VisualServiceCheckResult(
                            status="waiting",
                            message=f"Нарахування за {month_label} не відображено в колонці 'Нараховано'",
                        )
                    raw_value = _parse_decimal(accrued_text)
                    if raw_value is None:
                        return VisualServiceCheckResult(status="error", message=f"Cannot parse accrued value: '{accrued_text}'")
                    return VisualServiceCheckResult(status="found", message=f"Знайдено нарахування {raw_value}", raw_value=raw_value)

                return VisualServiceCheckResult(status="error", message=f"Рядок {service_label} / {month_label} не знайдено")
        except (httpx.HTTPError, OSError, socket.gaierror) as error:
            last_error = f"{type(error).__name__}: {error}"
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue

    return VisualServiceCheckResult(status="error", message=f"Network error after retries: {last_error or 'unknown'}")


def _is_vodokanal_setting(setting: BindingSetting) -> bool:
    adapter_code = _provider_adapter_code(setting)
    if adapter_code in {"if_vodokanal", "vodokanal_if"}:
        return True
    haystack = " ".join(
        [
            setting.provider_company or "",
            setting.cabinet_url or "",
            setting.service_code or "",
        ]
    ).casefold()
    return ("vodokanal.if.ua" in haystack) or ("водоканал" in haystack and setting.service_code in VODOKANAL_SERVICE_CODES)


def _provider_adapter_code(setting: BindingSetting) -> str:
    provider = getattr(setting, "provider", None)
    if provider is None:
        return ""
    code = getattr(provider, "adapter_code", "") or ""
    return str(code).strip().lower()


def _is_atp0928_setting(setting: BindingSetting) -> bool:
    adapter_code = _provider_adapter_code(setting)
    if adapter_code in {"if_atp0928_waste", "atp0928_if"}:
        return True
    haystack = " ".join(
        [
            setting.provider_company or "",
            setting.cabinet_url or "",
            setting.service_code or "",
        ]
    ).casefold()
    return ("atp0928.if.ua" in haystack) or ("атп-0928" in haystack) or (setting.service_code == ATP0928_SERVICE_CODE)


def _connection_active_on(connection: ApartmentServiceConnection, target_date: date) -> bool:
    if connection.started_at and connection.started_at > target_date:
        return False
    if connection.ended_at and connection.ended_at < target_date:
        return False
    return (connection.status or "active").strip().lower() != "inactive"


def _charge_line_active_on(line: ConnectionChargeLine, target_date: date) -> bool:
    if not line.is_active:
        return False
    if line.effective_from and line.effective_from > target_date:
        return False
    if line.effective_to and line.effective_to < target_date:
        return False
    return True


def _service_charge_line_for_period(
    db: Session,
    *,
    apartment_id: int,
    service_name: str,
    period_start: date,
    connection_id: int | None = None,
    service_catalog_id: int | None = None,
) -> ConnectionChargeLine | None:
    connection: ApartmentServiceConnection | None = None
    if connection_id is not None:
        candidate = db.get(ApartmentServiceConnection, connection_id)
        if candidate is not None and candidate.apartment_id == apartment_id and _connection_active_on(candidate, period_start):
            connection = candidate
    if connection is None:
        connections = db.scalars(
            select(ApartmentServiceConnection)
            .where(ApartmentServiceConnection.apartment_id == apartment_id)
            .order_by(ApartmentServiceConnection.started_at.desc(), ApartmentServiceConnection.id.desc())
        ).all()
        for candidate in connections:
            if not _connection_active_on(candidate, period_start):
                continue
            if service_catalog_id is not None and candidate.service_catalog_id == service_catalog_id:
                connection = candidate
                break
            catalog_name = (
                candidate.service_catalog.name.strip()
                if candidate.service_catalog and (candidate.service_catalog.name or "").strip()
                else ""
            )
            if catalog_name == (service_name or "").strip():
                connection = candidate
                break
    if connection is None:
        return None
    lines = db.scalars(
        select(ConnectionChargeLine)
        .where(ConnectionChargeLine.connection_id == connection.id)
        .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
    ).all()
    for line in lines:
        if _charge_line_active_on(line, period_start):
            return line
    return None


def _upsert_service_charge_line_price(
    db: Session,
    *,
    apartment_id: int,
    service_name: str,
    period_start: date,
    new_value: Decimal,
    connection_id: int | None = None,
    service_catalog_id: int | None = None,
) -> tuple[ConnectionChargeLine | None, Decimal | None]:
    current_line = _service_charge_line_for_period(
        db,
        apartment_id=apartment_id,
        service_name=service_name,
        period_start=period_start,
        connection_id=connection_id,
        service_catalog_id=service_catalog_id,
    )
    if current_line is None:
        return None, None
    old_value = Decimal(current_line.price_per_unit).quantize(Decimal("0.01"))
    existing = db.scalar(
        select(ConnectionChargeLine).where(
            and_(
                ConnectionChargeLine.connection_id == current_line.connection_id,
                ConnectionChargeLine.label == current_line.label,
                ConnectionChargeLine.line_kind == current_line.line_kind,
                ConnectionChargeLine.meter_id == current_line.meter_id,
                ConnectionChargeLine.meter_register == current_line.meter_register,
                ConnectionChargeLine.effective_from == period_start,
            )
        )
    )
    if existing is not None:
        existing.price_per_unit = new_value
        return existing, old_value
    if current_line.effective_from < period_start and (
        current_line.effective_to is None or current_line.effective_to >= period_start
    ):
        current_line.effective_to = period_start - timedelta(days=1)
    clone = ConnectionChargeLine(
        connection_id=current_line.connection_id,
        line_kind=current_line.line_kind,
        label=current_line.label,
        meter_id=current_line.meter_id,
        meter_register=current_line.meter_register,
        derived_from_line_id=current_line.derived_from_line_id,
        unit_name=current_line.unit_name,
        price_per_unit=new_value,
        quantity_source=current_line.quantity_source,
        quantity_multiplier=current_line.quantity_multiplier,
        effective_from=period_start,
        effective_to=None,
        is_active=current_line.is_active,
    )
    db.add(clone)
    db.flush()
    return clone, old_value


def _build_automation_bindings(
    db: Session,
    *,
    automation: ApartmentAutomation,
    timezone_name: str,
    for_submit: bool = False,
    target_date: date | None = None,
) -> dict[str, AutomationBindingContext]:
    connections = db.scalars(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == automation.apartment_id)
        .where(ApartmentServiceConnection.automation_id == automation.id)
        .order_by(ApartmentServiceConnection.id.asc())
    ).all()
    out: dict[str, AutomationBindingContext] = {}
    for connection in connections:
        if target_date is not None and not _connection_active_on(connection, target_date):
            continue
        service_name = (
            connection.service_catalog.name.strip()
            if connection.service_catalog and (connection.service_catalog.name or "").strip()
            else ""
        )
        if not service_name:
            continue
        provider = connection.provider or automation.provider or (automation.template.provider if automation.template else None)
        provider_company = provider.name_full if provider else None
        out[service_name] = AutomationBindingContext(
            apartment_id=automation.apartment_id,
            connection_id=connection.id,
            service_catalog_id=connection.service_catalog_id,
            service_code=(connection.service_catalog.code if connection.service_catalog else None),
            service_name=service_name,
            provider_id=connection.provider_id or automation.provider_id,
            provider_company=provider_company,
            provider=provider,
            cabinet_url=automation.cabinet_url,
            cabinet_login=automation.cabinet_login,
            cabinet_password_encrypted=automation.cabinet_password_encrypted,
            personal_account=connection.personal_account or automation.personal_account,
            auto_check_enabled=(automation.is_enabled and automation.submit_enabled) if for_submit else (automation.is_enabled and automation.accrual_enabled),
            auto_check_time=automation.submit_time if for_submit else automation.accrual_time,
            auto_check_timezone=timezone_name,
            auto_check_window_day_from=(automation.submit_window_day_from if for_submit else automation.accrual_window_day_from),
            auto_check_window_day_to=(automation.submit_window_day_to if for_submit else automation.accrual_window_day_to),
        )
    for binding in out.values():
        binding.related_bindings = out
    return out


def _aggregate_binding_state(
    automation: ApartmentAutomation,
    bindings: list[AutomationBindingContext],
    *,
    now_utc: datetime,
) -> None:
    if not bindings:
        automation.auto_check_status = "error"
        automation.auto_check_message = "Automation не має пов'язаних послуг."
        automation.auto_check_last_checked_at = now_utc
        return
    statuses = [binding.auto_check_status for binding in bindings if binding.auto_check_status]
    messages = [binding.auto_check_message for binding in bindings if binding.auto_check_message]
    automation.auto_check_last_checked_at = max(
        [binding.auto_check_last_checked_at for binding in bindings if binding.auto_check_last_checked_at] or [now_utc]
    )
    automation.auto_check_last_updated_at = max(
        [binding.auto_check_last_updated_at for binding in bindings if binding.auto_check_last_updated_at] or [automation.auto_check_last_updated_at]
    )
    automation.auto_check_next_at = max(
        [binding.auto_check_next_at for binding in bindings if binding.auto_check_next_at] or [automation.auto_check_next_at]
    )
    if "error" in statuses:
        automation.auto_check_status = "error"
    elif "updated" in statuses:
        automation.auto_check_status = "updated"
    elif "waiting" in statuses:
        automation.auto_check_status = "waiting"
    elif "no_change" in statuses:
        automation.auto_check_status = "no_change"
    else:
        automation.auto_check_status = None
    if all(binding.auto_check_completed_for_period for binding in bindings):
        automation.accrual_completed_for_period = True
    automation.auto_check_message = "; ".join(
        f"{binding.service_name}: {binding.auto_check_message}"
        for binding in bindings
        if binding.auto_check_message
    )[:255] or (messages[0][:255] if messages else None)


def _fetch_atp0928_cabinet_html(
    *,
    cabinet_url: str,
    cabinet_login: str,
    cabinet_password: str,
) -> tuple[str | None, str | None]:
    parsed = urlparse(cabinet_url)
    if not parsed.scheme or not parsed.netloc:
        return None, "Invalid cabinet_url for ATP-0928"
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    login_endpoint = urljoin(base_url, "/wp-login.php")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "uk,en-US;q=0.9,en;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
        login_page = client.get(cabinet_url)
        if login_page.status_code != 200:
            return None, f"ATP-0928 login page HTTP {login_page.status_code}"
        payload = {
            "log": cabinet_login,
            "pwd": cabinet_password,
            "rememberme": "forever",
            "wp-submit": "Увійти",
            "redirect_to": cabinet_url,
            "testcookie": "1",
        }
        auth = client.post(login_endpoint, data=payload)
        if auth.status_code != 200:
            return None, f"ATP-0928 auth HTTP {auth.status_code}"
        dashboard = client.get(cabinet_url)
        if dashboard.status_code != 200:
            return None, f"ATP-0928 cabinet HTTP {dashboard.status_code}"
        html = dashboard.text
        # Login form still present -> wrong credentials.
        if 'name="log"' in html and 'name="pwd"' in html:
            return None, "ATP-0928 authorization failed (invalid login/password)"
        return html, None


def _run_atp0928(
    db: Session,
    *,
    setting: BindingSetting,
    now_utc: datetime,
    local_now: datetime,
    force_mode: str,
) -> None:
    apartment = db.get(Apartment, setting.apartment_id)
    residents_multiplier = fixed_charge_multiplier(
        setting.service_name,
        apartment.registered_residents if apartment else 1,
        quantity_source="apartment_registered_residents",
        quantity_multiplier=Decimal("1"),
    )
    residents_count = int(residents_multiplier)
    cabinet_login = (setting.cabinet_login or "").strip()
    cabinet_password = decrypt_text(setting.cabinet_password_encrypted) or ""
    if not cabinet_login or not cabinet_password:
        setting.auto_check_status = "error"
        setting.auto_check_message = "cabinet credentials are missing"
        setting.auto_check_last_checked_at = now_utc
        return

    cabinet_url = (setting.cabinet_url or "").strip() or ATP0928_CABINET_URL
    tariff_url = ATP0928_TARIFF_URL
    target_year, target_month = _prev_month(local_now.year, local_now.month)
    message_parts: list[str] = []
    has_error = False
    has_waiting = False
    has_update = False
    accrued_month_value: Decimal | None = None
    public_tariff_per_person: Decimal | None = None

    if force_mode in {"full", "readings"}:
        try:
            cabinet_html, cabinet_error = _fetch_atp0928_cabinet_html(
                cabinet_url=cabinet_url,
                cabinet_login=cabinet_login,
                cabinet_password=cabinet_password,
            )
            if cabinet_error or cabinet_html is None:
                has_error = True
                message_parts.append(cabinet_error or "ATP-0928 cabinet read failed")
            else:
                accrued = _parse_atp0928_accrued_from_html(cabinet_html, target_year, target_month)
                if accrued is None:
                    has_waiting = True
                    message_parts.append(f"Нарахування за {target_month:02d}.{target_year} у кабінеті не знайдено")
                else:
                    accrued_month_value = accrued
                    setting.auto_check_last_value_raw = accrued.quantize(Decimal("0.0001"))
                    setting.auto_check_last_value_rounded = accrued.quantize(Decimal("0.01"))
                    message_parts.append(
                        f"Кабінет: Нараховано за {target_month:02d}.{target_year} = {accrued.quantize(Decimal('0.01'))} грн"
                    )
        except (httpx.HTTPError, OSError, socket.gaierror) as error:
            has_error = True
            message_parts.append(f"ATP-0928 cabinet network error: {error}")

    if force_mode in {"full", "tariffs"}:
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=20.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "uk,en-US;q=0.9,en;q=0.8",
                },
            ) as client:
                tariff_page = client.get(tariff_url)
            if tariff_page.status_code != 200:
                has_error = True
                message_parts.append(f"Тарифна сторінка ATP-0928 HTTP {tariff_page.status_code}")
            else:
                fetched_tariff = _parse_atp0928_tariff_from_html(tariff_page.text, setting.service_code)
                if fetched_tariff is None:
                    has_error = True
                    message_parts.append("На сторінці /tarif не знайдено числового тарифу")
                else:
                    public_tariff_per_person = fetched_tariff
                    message_parts.append(
                        f"Публічний тариф: {fetched_tariff.quantize(Decimal('0.01'))} грн/особа"
                    )
        except (httpx.HTTPError, OSError, socket.gaierror) as error:
            has_error = True
            message_parts.append(f"ATP-0928 tariff network error: {error}")

    if force_mode in {"full", "tariffs"} and not has_error:
        period_start = date(local_now.year, local_now.month, 1)
        current_line = _service_charge_line_for_period(
            db,
            apartment_id=setting.apartment_id,
            service_name=setting.service_name,
            period_start=period_start,
            connection_id=setting.connection_id,
            service_catalog_id=setting.service_catalog_id,
        )
        if current_line is None:
            has_error = True
            message_parts.append("Активний рядок тарифу послуги у БД не знайдено")
        else:
            # For ATP-0928 cabinet accrued is monthly total, while /tarif is per-person.
            if accrued_month_value is not None:
                candidate_total_raw = accrued_month_value
            elif public_tariff_per_person is not None:
                candidate_total_raw = (public_tariff_per_person * residents_multiplier).quantize(Decimal("0.0001"))
            else:
                candidate_total_raw = None
            if candidate_total_raw is None:
                has_waiting = True
                message_parts.append("Немає значення для порівняння з тарифом у БД")
            else:
                current_per_person = Decimal(current_line.price_per_unit)
                current_total = (current_per_person * residents_multiplier).quantize(Decimal("0.01"))
                candidate_total_rounded = _round_up_to_half(candidate_total_raw).quantize(Decimal("0.01"))
                setting.auto_check_last_value_raw = candidate_total_raw.quantize(Decimal("0.0001"))
                setting.auto_check_last_value_rounded = candidate_total_rounded

                if public_tariff_per_person is not None and accrued_month_value is not None:
                    persons_estimate = (accrued_month_value / public_tariff_per_person) if public_tariff_per_person > 0 else Decimal("0")
                    message_parts.append(
                        f"Оцінка к-сті прописаних: {persons_estimate.quantize(Decimal('0.01'))}"
                    )
                message_parts.append(f"К-сть прописаних: {residents_count}")

                # Business rule: if DB total >= cabinet-derived total, keep unchanged.
                if current_total >= candidate_total_rounded:
                    message_parts.append(f"Без змін: у БД {current_total} >= {candidate_total_rounded}")
                    setting.auto_check_completed_for_period = True
                else:
                    candidate_per_person = (candidate_total_rounded / residents_multiplier).quantize(Decimal("0.0001"))
                    target_line, _ = _upsert_service_charge_line_price(
                        db,
                        apartment_id=setting.apartment_id,
                        service_name=setting.service_name,
                        period_start=period_start,
                        new_value=candidate_per_person,
                        connection_id=setting.connection_id,
                        service_catalog_id=setting.service_catalog_id,
                    )
                    if target_line is None:
                        has_error = True
                        message_parts.append("Не вдалося оновити рядок тарифу")
                    else:
                        db.flush()
                        _recalc_from_period(db, setting.apartment_id, local_now.year, local_now.month)
                        has_update = True
                        message_parts.append(
                            f"Тариф оновлено: {current_per_person.quantize(Decimal('0.0001'))} -> {candidate_per_person}"
                        )
                        setting.auto_check_last_updated_at = now_utc
                        setting.auto_check_completed_for_period = True

    setting.auto_check_last_checked_at = now_utc
    setting.last_tariff_check_at = now_utc
    if has_error:
        setting.auto_check_status = "error"
    elif has_update:
        setting.auto_check_status = "updated"
    elif has_waiting:
        setting.auto_check_status = "waiting"
    else:
        setting.auto_check_status = "no_change"
    setting.auto_check_message = "; ".join(message_parts)[:255] if message_parts else "ATP-0928 sync completed"


def _parse_vodokanal_tariffs(dashboard_html: str) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for card_title, (service_code, _) in VODOKANAL_SERVICE_CARD_MAP.items():
        # Parse from raw DOM to avoid brittle distance limits on flattened text.
        found = re.search(
            r"<h5[^>]*>\s*" + re.escape(card_title) + r"\s*</h5>.*?Тариф:\s*([0-9]+(?:[.,][0-9]+)?)",
            dashboard_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not found:
            # Fallback by text for minor layout changes.
            text = _only_text(dashboard_html)
            found = re.search(
                re.escape(card_title) + r".*?Тариф:\s*([0-9]+(?:[.,][0-9]+)?)",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
        if not found:
            continue
        value = _parse_decimal(found.group(1))
        if value is not None:
            result[service_code] = value
    return result


def _extract_vodokanal_payload_from_bridge_fields(bridge_fields: dict[str, str]) -> dict:
    payload: dict = {"stat": bridge_fields.get("stat"), "osr": bridge_fields.get("osr")}
    for field in ("dani", "dani_k", "dani_info"):
        raw = bridge_fields.get(field)
        if not raw:
            payload[field] = {}
            continue
        try:
            payload[field] = json.loads(raw)
        except Exception:
            payload[field] = {}
    return payload


def _parse_vodokanal_tariffs_from_payload(payload: dict) -> dict[str, Decimal]:
    z = payload.get("dani_k", {}).get("zaborgovanosti", {})
    values = {
        "water_supply": z.get("vodopostachannya_tarif"),
        "sewage": z.get("vodovidvedennya_tarif"),
        "water_subscription": z.get("abon_tarif"),
    }
    out: dict[str, Decimal] = {}
    for service_name, raw in values.items():
        if raw is None:
            continue
        val = _parse_decimal(str(raw))
        if val is not None:
            out[service_name] = val
    return out


def _extract_vodokanal_current_meter_rows(payload: dict) -> list[dict]:
    rows = payload.get("dani_k", {}).get("lichul", {}).get("lic_potochni", {}).get("pot_lich", [])
    if isinstance(rows, list):
        return [x for x in rows if isinstance(x, dict)]
    return []


def _find_current_meter_reading_for_service(
    db: Session,
    *,
    apartment_id: int,
    service_name: str,
    year: int,
    month: int,
    connection_id: int | None = None,
    service_catalog_id: int | None = None,
) -> Decimal | None:
    period_start = date(year, month, 1)
    current_line = _service_charge_line_for_period(
        db,
        apartment_id=apartment_id,
        service_name=service_name,
        period_start=period_start,
        connection_id=connection_id,
        service_catalog_id=service_catalog_id,
    )
    if current_line is None or current_line.meter_id is None:
        return None
    meter: Meter | None = None
    if current_line.meter_id:
        meter = db.get(Meter, current_line.meter_id)
    if meter is None:
        return None
    register_name = current_line.meter_register or "total"
    current = db.scalar(
        select(MeterReading).where(
            and_(
                MeterReading.meter_id == meter.id,
                MeterReading.register_name == register_name,
                MeterReading.year == year,
                MeterReading.month == month,
            )
        )
    )
    if current is None:
        return None
    return Decimal(current.value)


def _format_reading_for_submit(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.001"))
    text = format(normalized, "f").rstrip("0").rstrip(".")
    return text or "0"


def _stats_row_matches_target_reading(row_value: str, expected: Decimal) -> bool:
    parsed = _parse_decimal(row_value)
    if parsed is None:
        return False
    return parsed.quantize(Decimal("0.001")) == expected.quantize(Decimal("0.001"))


def _run_vodokanal(
    db: Session,
    *,
    setting: BindingSetting,
    now_utc: datetime,
    local_now: datetime,
    day_from: int,
    day_to: int,
    force_mode: str,
) -> None:
    cabinet_login = (setting.cabinet_login or "").strip()
    cabinet_password = decrypt_text(setting.cabinet_password_encrypted) or ""
    if not cabinet_login or not cabinet_password:
        setting.auto_check_status = "error"
        setting.auto_check_message = "cabinet credentials are missing"
        setting.auto_check_last_checked_at = now_utc
        return

    login_url = (setting.cabinet_url or "").strip() or VODOKANAL_CABINET_LOGIN_URL
    login_url = login_url.rstrip("/") + "/"
    parsed = urlparse(login_url)
    cabinet_base = f"{parsed.scheme}://{parsed.netloc}"
    cabinet_dashboard_url = urljoin(cabinet_base, "/kabinet-spozhyvacha/")

    with httpx.Client(follow_redirects=True, timeout=25.0) as client:
        auth = client.post(VODOKANAL_AUTH_URL, data={"login": cabinet_login, "password": cabinet_password})
        if auth.status_code != 200:
            setting.auto_check_status = "error"
            setting.auto_check_message = f"Vodokanal auth failed: HTTP {auth.status_code}"
            setting.auto_check_last_checked_at = now_utc
            return

        bridge_fields = _extract_login_bridge_fields(auth.text)
        if not bridge_fields:
            setting.auto_check_status = "error"
            setting.auto_check_message = "Vodokanal auth bridge fields were not found"
            setting.auto_check_last_checked_at = now_utc
            return
        bridge_payload = _extract_vodokanal_payload_from_bridge_fields(bridge_fields)
        if (bridge_payload.get("stat") or "").strip().lower() != "ok":
            setting.auto_check_status = "error"
            setting.auto_check_message = "Vodokanal auth status is not OK"
            setting.auto_check_last_checked_at = now_utc
            return

        cabinet = client.post(cabinet_dashboard_url, data=bridge_fields)
        if cabinet.status_code != 200:
            setting.auto_check_status = "error"
            setting.auto_check_message = f"Cabinet open failed: HTTP {cabinet.status_code}"
            setting.auto_check_last_checked_at = now_utc
            return

        dashboard_html = cabinet.text
        dashboard_text = _only_text(dashboard_html)
        if "Невірно введений логін або пароль" in dashboard_text:
            setting.auto_check_status = "error"
            setting.auto_check_message = "Невірно введений логін або пароль"
            setting.auto_check_last_checked_at = now_utc
            return
        if "Кабінет споживача" not in dashboard_text:
            setting.auto_check_status = "error"
            setting.auto_check_message = "Vodokanal cabinet page did not match expected layout"
            setting.auto_check_last_checked_at = now_utc
            return

        message_parts: list[str] = []
        has_error = False
        has_waiting = False
        has_update = False
        this_service_updated = False
        this_service_no_change = False
        apartment_settings = list((setting.related_bindings or {}).values())
        for row in apartment_settings:
            if _is_vodokanal_setting(row) and row.auto_check_window_day_from == 1 and row.auto_check_window_day_to == 10:
                row.auto_check_window_day_from = 25
                row.auto_check_window_day_to = 3

        if force_mode in {"full", "readings"}:
            if setting.service_code == VODOKANAL_READING_DRIVER_CODE:
                if _is_day_in_window(local_now.day, day_from, day_to):
                    target_reading_year, target_reading_month = _vodokanal_target_period(local_now, day_from, day_to)
                    target_reading_label = _build_month_short_label(target_reading_year, target_reading_month)
                    target_reading_label_full = _build_month_full_label(target_reading_year, target_reading_month)
                    current_reading = _find_current_meter_reading_for_service(
                        db,
                        apartment_id=setting.apartment_id,
                        service_name=setting.service_name,
                        year=target_reading_year,
                        month=target_reading_month,
                        connection_id=setting.connection_id,
                        service_catalog_id=setting.service_catalog_id,
                    )
                    if current_reading is None:
                        has_waiting = True
                        message_parts.append("Немає поточного показника на вкладці Розрахунок")
                    else:
                        osr = (bridge_payload.get("osr") or "").strip()
                        meter_rows = _extract_vodokanal_current_meter_rows(bridge_payload)
                        meter_row = meter_rows[0] if meter_rows else {}
                        meter_number = str(meter_row.get("nomerlich") or "").strip()
                        if not osr:
                            has_error = True
                            message_parts.append("У кабінеті відсутній особовий рахунок (osr)")
                        elif not meter_number:
                            has_error = True
                            message_parts.append("У кабінеті відсутній номер лічильника для submit")
                        else:
                            stats_endpoint = "https://vodokanal.if.ua/propibank/lichpot.php"
                            submit_endpoint = "https://vodokanal.if.ua/propibank/viberpokaz2.php"
                            stats_before_resp = client.post(stats_endpoint, data={"osr": osr})

                            stats_rows_before = (
                                _parse_vodokanal_stats_rows(stats_before_resp.text)
                                if stats_before_resp.status_code == 200
                                else []
                            )
                            already_exists = any(
                                row.get("month", "").strip() in {target_reading_label, target_reading_label_full}
                                and _stats_row_matches_target_reading(row.get("value", "").strip(), current_reading)
                                for row in stats_rows_before
                            )
                            if already_exists:
                                this_service_no_change = True
                                setting.auto_check_last_value_raw = current_reading.quantize(Decimal("0.0001"))
                                setting.auto_check_last_value_rounded = current_reading.quantize(Decimal("0.01"))
                                message_parts.append(
                                    f"Показник за {target_reading_label} вже є у 'Статистика показників', submit пропущено"
                                )
                                skip_submit = True
                            else:
                                skip_submit = False
                            if not skip_submit:
                                submit_value = _format_reading_for_submit(current_reading)
                                submit_resp = client.get(
                                    submit_endpoint,
                                    params={"pokaz": submit_value, "osr": osr, "nlichn": meter_number},
                                )
                                if submit_resp.status_code != 200:
                                    has_error = True
                                    message_parts.append(f"Submit показника повернув HTTP {submit_resp.status_code}")
                                else:
                                    stats_resp = client.post(stats_endpoint, data={"osr": osr})
                                    stats_rows_after = (
                                        _parse_vodokanal_stats_rows(stats_resp.text)
                                        if stats_resp.status_code == 200
                                        else []
                                    )
                                    confirmed = any(
                                        row.get("month", "").strip() in {target_reading_label, target_reading_label_full}
                                        and _stats_row_matches_target_reading(
                                            row.get("value", "").strip(),
                                            current_reading,
                                        )
                                        for row in stats_rows_after
                                    )
                                    if not confirmed:
                                        has_error = True
                                        message_parts.append("Показник не підтверджено у 'Статистика показників'")
                                    else:
                                        has_update = True
                                        this_service_updated = True
                                        setting.auto_check_last_value_raw = current_reading.quantize(Decimal("0.0001"))
                                        setting.auto_check_last_value_rounded = current_reading.quantize(Decimal("0.01"))
                                        message_parts.append(
                                            f"Показник {submit_value} за {target_reading_label} підтверджено у статистиці"
                                        )
            else:
                message_parts.append("Подача показників керується послугою 'Водопостачання'")

        if force_mode in {"full", "tariffs"}:
            parsed_tariffs = _parse_vodokanal_tariffs_from_payload(bridge_payload)
            if not parsed_tariffs:
                parsed_tariffs = _parse_vodokanal_tariffs(dashboard_html)
            if not parsed_tariffs:
                has_error = True
                message_parts.append("Тарифи в кабінеті не знайдено")
            else:
                period_start = date(local_now.year, local_now.month, 1)
                settings_by_service_code = {row.service_code: row for row in apartment_settings if row.service_code}
                updated_service_codes: set[str] = set()
                unchanged_service_codes: set[str] = set()
                updated_services: list[str] = []
                unchanged_services: list[str] = []
                missing_services: list[str] = []
                recalc_needed = False

                for service_code in ("water_supply", "sewage", "water_subscription"):
                    service_label = VODOKANAL_SERVICE_LABELS.get(service_code, service_code)
                    fetched_raw = parsed_tariffs.get(service_code)
                    target_setting = settings_by_service_code.get(service_code)
                    if fetched_raw is None:
                        missing_services.append(service_label)
                        if target_setting is not None:
                            target_setting.auto_check_status = "error"
                            target_setting.auto_check_message = "Тариф у кабінеті не знайдено"
                            target_setting.auto_check_last_checked_at = now_utc
                            target_setting.last_tariff_check_at = now_utc
                        continue

                    current_line = _service_charge_line_for_period(
                        db,
                        apartment_id=setting.apartment_id,
                        service_name=service_label,
                        period_start=period_start,
                        connection_id=target_setting.connection_id if target_setting is not None else None,
                        service_catalog_id=target_setting.service_catalog_id if target_setting is not None else None,
                    )
                    if current_line is None:
                        missing_services.append(service_label)
                        if target_setting is not None:
                            target_setting.auto_check_status = "error"
                            target_setting.auto_check_message = "Активний рядок тарифу у БД не знайдено"
                            target_setting.auto_check_last_checked_at = now_utc
                            target_setting.last_tariff_check_at = now_utc
                    else:
                        new_value = fetched_raw.quantize(Decimal("0.01"))
                        current_value = Decimal(current_line.price_per_unit).quantize(Decimal("0.01"))
                        if target_setting is not None:
                            target_setting.auto_check_last_value_raw = fetched_raw.quantize(Decimal("0.0001"))
                            target_setting.auto_check_last_checked_at = now_utc
                            target_setting.last_tariff_check_at = now_utc
                        if new_value <= current_value:
                            unchanged_service_codes.add(service_code)
                            unchanged_services.append(service_label)
                            if target_setting is not None:
                                target_setting.auto_check_status = "no_change"
                                target_setting.auto_check_last_value_rounded = current_value
                                target_setting.auto_check_completed_for_period = True
                                target_setting.auto_check_message = f"Без змін ({new_value} <= {current_value})"
                        else:
                            target_line, _ = _upsert_service_charge_line_price(
                                db,
                                apartment_id=setting.apartment_id,
                                service_name=service_label,
                                period_start=period_start,
                                new_value=new_value,
                                connection_id=target_setting.connection_id if target_setting is not None else None,
                                service_catalog_id=target_setting.service_catalog_id if target_setting is not None else None,
                            )
                            if target_line is None:
                                missing_services.append(service_label)
                                if target_setting is not None:
                                    target_setting.auto_check_status = "error"
                                    target_setting.auto_check_message = "Не вдалося оновити рядок тарифу"
                            else:
                                recalc_needed = True
                                updated_service_codes.add(service_code)
                                updated_services.append(service_label)
                                if target_setting is not None:
                                    target_setting.auto_check_status = "updated"
                                    target_setting.auto_check_last_value_rounded = new_value
                                    target_setting.auto_check_completed_for_period = True
                                    target_setting.auto_check_last_updated_at = now_utc
                                    target_setting.auto_check_message = f"Тариф оновлено до {new_value}"

                if recalc_needed:
                    db.flush()
                    _recalc_from_period(db, setting.apartment_id, local_now.year, local_now.month)
                    has_update = True
                if updated_services:
                    message_parts.append("Оновлено тарифи: " + ", ".join(updated_services))
                if unchanged_services:
                    message_parts.append("Без змін: " + ", ".join(unchanged_services))
                if missing_services:
                    has_error = True
                    message_parts.append("Не знайдено/не оновлено: " + ", ".join(missing_services))
                this_service_updated = (setting.service_code or "") in updated_service_codes
                this_service_no_change = (setting.service_code or "") in unchanged_service_codes

        setting.auto_check_last_checked_at = now_utc
        setting.last_tariff_check_at = now_utc
        if has_error:
            setting.auto_check_status = "error"
        elif has_update:
            setting.auto_check_status = "updated"
            setting.auto_check_completed_for_period = True
            setting.auto_check_last_updated_at = now_utc
        elif has_waiting:
            setting.auto_check_status = "waiting"
        elif this_service_no_change:
            setting.auto_check_status = "no_change"
            setting.auto_check_completed_for_period = True
        else:
            setting.auto_check_status = "no_change"
        setting.auto_check_message = "; ".join(message_parts)[:255] if message_parts else "Vodokanal sync completed"


def run_tariff_auto_checks(db: Session, *, trigger_mode: str = "scheduled") -> dict[str, int | str | datetime | None]:
    now_utc = datetime.now(UTC)
    cycle_row = AutomationCycleRun(
        trigger_mode=(trigger_mode or "scheduled").strip().lower() or "scheduled",
        started_at=now_utc,
    )
    db.add(cycle_row)
    db.flush()
    processed_accrual_automations = 0
    processed_submit_automations = 0
    processed_legacy_settings = 0
    submitted_readings = 0
    automations = db.scalars(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.is_enabled == True)
        .where(ApartmentAutomation.accrual_enabled == True)
        .order_by(ApartmentAutomation.apartment_id, ApartmentAutomation.id)
    ).all()
    accrual_started_at = datetime.now(UTC)
    for automation in automations:
        run_tariff_auto_check_for_automation(db, automation=automation, now_utc=now_utc)
        processed_accrual_automations += 1
    accrual_finished_at = datetime.now(UTC)
    db.add(
        AutomationCyclePhaseRun(
            cycle_run_id=cycle_row.id,
            phase="accrual",
            status="completed",
            processed_count=processed_accrual_automations,
            skipped_count=0,
            submitted_readings=0,
            duration_ms=_duration_ms(accrual_started_at, accrual_finished_at),
            message=f"Оброблено accrual automation: {processed_accrual_automations}"[:255],
            started_at=accrual_started_at,
            finished_at=accrual_finished_at,
        )
    )

    submit_automations = db.scalars(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.is_enabled == True)
        .where(ApartmentAutomation.submit_enabled == True)
        .order_by(ApartmentAutomation.apartment_id, ApartmentAutomation.id)
    ).all()
    submit_started_at = datetime.now(UTC)
    for automation in submit_automations:
        if run_meter_submit_for_automation(db, automation=automation, now_utc=now_utc):
            submitted_readings += 1
        processed_submit_automations += 1
    submit_finished_at = datetime.now(UTC)
    db.add(
        AutomationCyclePhaseRun(
            cycle_run_id=cycle_row.id,
            phase="submit",
            status="completed",
            processed_count=processed_submit_automations,
            skipped_count=max(processed_submit_automations - submitted_readings, 0),
            submitted_readings=submitted_readings,
            duration_ms=_duration_ms(submit_started_at, submit_finished_at),
            message=f"Оброблено submit automation: {processed_submit_automations}, відправлено: {submitted_readings}"[:255],
            started_at=submit_started_at,
            finished_at=submit_finished_at,
        )
    )

    legacy_started_at = datetime.now(UTC)
    skipped_legacy_settings = 0
    legacy_finished_at = datetime.now(UTC)
    db.add(
        AutomationCyclePhaseRun(
            cycle_run_id=cycle_row.id,
            phase="legacy",
            status="completed",
            processed_count=processed_legacy_settings,
            skipped_count=skipped_legacy_settings,
            submitted_readings=0,
            duration_ms=_duration_ms(legacy_started_at, legacy_finished_at),
            message="Legacy tariff settings phase вимкнена; worker працює через apartment automations."[:255],
            started_at=legacy_started_at,
            finished_at=legacy_finished_at,
        )
    )

    finished_at = datetime.now(UTC)
    cycle_row.processed_accrual_automations = processed_accrual_automations
    cycle_row.processed_submit_automations = processed_submit_automations
    cycle_row.processed_legacy_settings = processed_legacy_settings
    cycle_row.submitted_readings = submitted_readings
    cycle_row.message = (
        "Плановий цикл виконано: "
        f"accrual={processed_accrual_automations}, "
        f"submit={processed_submit_automations}, "
        f"submitted={submitted_readings}"
    )[:255]
    cycle_row.finished_at = finished_at
    db.add(cycle_row)
    db.commit()
    return {
        "id": cycle_row.id,
        "trigger_mode": cycle_row.trigger_mode,
        "processed_accrual_automations": processed_accrual_automations,
        "processed_submit_automations": processed_submit_automations,
        "processed_legacy_settings": processed_legacy_settings,
        "submitted_readings": submitted_readings,
        "message": cycle_row.message,
        "started_at": cycle_row.started_at,
        "finished_at": cycle_row.finished_at,
    }


def _sync_automation_from_setting(
    automation: ApartmentAutomation,
    setting: BindingSetting,
) -> None:
    automation.auto_check_target_year = setting.auto_check_target_year
    automation.auto_check_target_month = setting.auto_check_target_month
    automation.accrual_completed_for_period = setting.auto_check_completed_for_period
    automation.auto_check_status = setting.auto_check_status
    automation.auto_check_message = setting.auto_check_message
    automation.auto_check_last_checked_at = setting.auto_check_last_checked_at
    automation.auto_check_last_updated_at = setting.auto_check_last_updated_at
    automation.auto_check_next_at = setting.auto_check_next_at


def run_tariff_auto_check_for_automation(
    db: Session,
    *,
    automation: ApartmentAutomation,
    now_utc: datetime | None = None,
) -> None:
    now_utc = now_utc or datetime.now(UTC)
    apartment = db.get(Apartment, automation.apartment_id)
    timezone_name = (apartment.timezone if apartment else None) or "Europe/Kyiv"
    tz = ZoneInfo(timezone_name)
    local_now = now_utc.astimezone(tz)
    target_year, target_month = _prev_month(local_now.year, local_now.month)
    if (
        automation.auto_check_target_year != target_year
        or automation.auto_check_target_month != target_month
    ):
        automation.auto_check_target_year = target_year
        automation.auto_check_target_month = target_month
        automation.accrual_completed_for_period = False
        automation.auto_check_status = None
        automation.auto_check_message = None

    day_from = max(1, min(automation.accrual_window_day_from or 1, 31))
    day_to = max(1, min(automation.accrual_window_day_to or 10, 31))
    hh, mm = _resolve_check_time(automation.accrual_time)
    automation.auto_check_next_at = _next_run_at(local_now, tz, hh, mm, day_from, day_to)
    db.add(automation)
    db.commit()

    bindings_map = _build_automation_bindings(
        db,
        automation=automation,
        timezone_name=timezone_name,
        for_submit=False,
        target_date=date(target_year, target_month, 1),
    )
    if not bindings_map:
        automation.auto_check_status = "error"
        automation.auto_check_message = "Automation не має пов'язаних послуг об'єкта."
        automation.auto_check_last_checked_at = now_utc
        db.add(automation)
        db.commit()
        return

    bindings = list(bindings_map.values())
    if any(_is_vodokanal_setting(binding) for binding in bindings):
        ordered_bindings = [
            next((binding for binding in bindings if binding.service_code == VODOKANAL_READING_DRIVER_CODE), None)
            or bindings[0]
        ]
    else:
        ordered_bindings = bindings
    try:
        for binding in ordered_bindings:
            _run_single_setting(db, binding, now_utc, force_run=False, force_mode="tariffs")
    finally:
        db.refresh(automation)
        _aggregate_binding_state(automation, bindings, now_utc=now_utc)
        db.add(automation)
        db.commit()


def run_meter_submit_for_automation(
    db: Session,
    *,
    automation: ApartmentAutomation,
    now_utc: datetime | None = None,
) -> bool:
    now_utc = now_utc or datetime.now(UTC)
    apartment = db.get(Apartment, automation.apartment_id)
    timezone_name = (apartment.timezone if apartment else None) or "Europe/Kyiv"
    tz = ZoneInfo(timezone_name)
    local_now = now_utc.astimezone(tz)
    target_year, target_month = _target_period_for_window(
        local_now,
        automation.submit_window_day_from or 28,
        automation.submit_window_day_to or 3,
    )
    if (
        automation.submit_target_year != target_year
        or automation.submit_target_month != target_month
    ):
        automation.submit_target_year = target_year
        automation.submit_target_month = target_month
        automation.submit_completed_for_period = False

    if not _is_day_in_window(local_now.day, automation.submit_window_day_from or 28, automation.submit_window_day_to or 3):
        db.add(automation)
        db.commit()
        return False
    if automation.submit_completed_for_period:
        db.add(automation)
        db.commit()
        return False
    if automation.provider_id is None:
        automation.auto_check_status = "error"
        automation.auto_check_message = "Automation submit не прив'язана до provider."
        automation.auto_check_last_checked_at = now_utc
        db.add(automation)
        db.commit()
        return False

    bindings_map = _build_automation_bindings(
        db,
        automation=automation,
        timezone_name=timezone_name,
        for_submit=True,
        target_date=date(target_year, target_month, 1),
    )
    bindings = list(bindings_map.values())
    if not bindings:
        automation.auto_check_status = "error"
        automation.auto_check_message = "Automation submit не має пов'язаних послуг об'єкта."
        automation.auto_check_last_checked_at = now_utc
        db.add(automation)
        db.commit()
        return False

    selected_binding: AutomationBindingContext | None = None
    target_date = date(target_year, target_month, 1)
    vodokanal_driver = next((binding for binding in bindings if binding.service_code == VODOKANAL_READING_DRIVER_CODE), None)
    for binding in ([vodokanal_driver] if vodokanal_driver else bindings):
        if binding is None:
            continue
        binding_connections = [
            connection
            for connection in db.scalars(
                select(ApartmentServiceConnection)
                .where(ApartmentServiceConnection.apartment_id == automation.apartment_id)
                .where(ApartmentServiceConnection.automation_id == automation.id)
                .order_by(ApartmentServiceConnection.id.asc())
            ).all()
            if connection.id == binding.connection_id
        ]
        found_reading = False
        for connection in binding_connections:
            charge_lines = db.scalars(
                select(ConnectionChargeLine)
                .where(ConnectionChargeLine.connection_id == connection.id)
                .where(ConnectionChargeLine.meter_id.is_not(None))
                .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
            ).all()
            for line in charge_lines:
                if line.meter_id is None or not _charge_line_active_on(line, target_date):
                    continue
                reading = db.scalar(
                    select(MeterReading)
                    .where(MeterReading.meter_id == line.meter_id)
                    .where(MeterReading.register_name == (line.meter_register or "total"))
                    .where(MeterReading.year == target_year)
                    .where(MeterReading.month == target_month)
                )
                if reading is None:
                    continue
                found_reading = True
                break
            if found_reading:
                break
        if found_reading:
            selected_binding = binding
            break

    if selected_binding is None:
        automation.auto_check_status = "waiting"
        automation.auto_check_message = (
            f"Немає поточного показника за {target_month:02d}.{target_year} для automation submit."
        )[:255]
        automation.auto_check_last_checked_at = now_utc
        db.add(automation)
        db.commit()
        return False

    try:
        _run_single_setting(db, selected_binding, now_utc, force_run=True, force_mode="readings")
    finally:
        db.refresh(automation)
        _aggregate_binding_state(automation, bindings, now_utc=now_utc)
        automation.submit_target_year = target_year
        automation.submit_target_month = target_month
        if selected_binding.auto_check_status in {"updated", "no_change"}:
            automation.submit_completed_for_period = True
        db.add(automation)
        db.commit()
    return automation.submit_completed_for_period


def _run_single_setting(
    db: Session,
    setting: BindingSetting,
    now_utc: datetime,
    *,
    force_run: bool = False,
    force_mode: str = "full",
) -> None:
    mode = (force_mode or "full").strip().lower()
    if mode not in {"full", "readings", "tariffs"}:
        mode = "full"

    tz = ZoneInfo(setting.auto_check_timezone or "Europe/Kyiv")
    local_now = now_utc.astimezone(tz)
    day_from = max(1, min(setting.auto_check_window_day_from or 1, 31))
    day_to = max(1, min(setting.auto_check_window_day_to or 10, 31))
    if _is_vodokanal_setting(setting) and day_from == 1 and day_to == 10:
        day_from, day_to = 25, 3
        setting.auto_check_window_day_from = day_from
        setting.auto_check_window_day_to = day_to
    hh, mm = _resolve_check_time(setting.auto_check_time)

    target_year, target_month = _prev_month(local_now.year, local_now.month)
    if setting.auto_check_target_year != target_year or setting.auto_check_target_month != target_month:
        setting.auto_check_target_year = target_year
        setting.auto_check_target_month = target_month
        setting.auto_check_completed_for_period = False
        setting.auto_check_status = None
        setting.auto_check_message = None

    setting.auto_check_next_at = _next_run_at(local_now, tz, hh, mm, day_from, day_to)
    if not force_run and not _is_day_in_window(local_now.day, day_from, day_to):
        return

    planned_local = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if not force_run and (local_now < planned_local or setting.auto_check_completed_for_period):
        return

    if _is_vodokanal_setting(setting):
        _run_vodokanal(
            db,
            setting=setting,
            now_utc=now_utc,
            local_now=local_now,
            day_from=day_from,
            day_to=day_to,
            force_mode=mode,
        )
        return

    if _is_atp0928_setting(setting):
        _run_atp0928(
            db,
            setting=setting,
            now_utc=now_utc,
            local_now=local_now,
            force_mode=mode,
        )
        return

    if mode == "readings":
        setting.auto_check_status = "waiting"
        setting.auto_check_message = "Цей провайдер не підтримує автоподачу показників"
        setting.auto_check_last_checked_at = now_utc
        return

    login_url = (setting.cabinet_url or "").strip()
    if not login_url:
        setting.auto_check_status = "error"
        setting.auto_check_message = "cabinet_url is empty"
        setting.auto_check_last_checked_at = now_utc
        return
    balance_url = urljoin(login_url, "/balance/")
    cabinet_login = (setting.cabinet_login or "").strip()
    cabinet_password = decrypt_text(setting.cabinet_password_encrypted) or ""
    if not cabinet_login or not cabinet_password:
        setting.auto_check_status = "error"
        setting.auto_check_message = "cabinet credentials are missing"
        setting.auto_check_last_checked_at = now_utc
        return

    check = _fetch_visualservice_kvartplata(
        login_url=login_url,
        balance_url=balance_url,
        cabinet_login=cabinet_login,
        cabinet_password=cabinet_password,
        service_label=setting.service_name,
        target_year=target_year,
        target_month=target_month,
    )
    setting.auto_check_last_checked_at = now_utc
    setting.last_tariff_check_at = now_utc
    setting.auto_check_message = check.message[:255]

    if check.status == "waiting":
        setting.auto_check_status = "waiting"
        return
    if check.status == "error":
        setting.auto_check_status = "error"
        return

    raw = check.raw_value or Decimal("0")
    setting.auto_check_last_value_raw = raw.quantize(Decimal("0.0001"))
    period_start = _month_start(target_year, target_month).date()
    current_line = _service_charge_line_for_period(
        db,
        apartment_id=setting.apartment_id,
        service_name=setting.service_name,
        period_start=period_start,
        connection_id=setting.connection_id,
        service_catalog_id=setting.service_catalog_id,
    )
    if current_line is None:
        setting.auto_check_status = "error"
        setting.auto_check_message = "Current charge line for period not found"
        return

    current_value = Decimal(current_line.price_per_unit)
    if raw <= current_value:
        setting.auto_check_status = "no_change"
        setting.auto_check_completed_for_period = True
        setting.auto_check_last_value_rounded = current_value.quantize(Decimal("0.01"))
        return

    rounded = _round_up_to_half(raw).quantize(Decimal("0.01"))
    target_line, _ = _upsert_service_charge_line_price(
        db,
        apartment_id=setting.apartment_id,
        service_name=setting.service_name,
        period_start=period_start,
        new_value=rounded,
        connection_id=setting.connection_id,
        service_catalog_id=setting.service_catalog_id,
    )
    if target_line is None:
        setting.auto_check_status = "error"
        setting.auto_check_message = "Target charge line for period not found"
        return

    db.flush()
    _recalc_from_period(db, setting.apartment_id, target_year, target_month)
    setting.auto_check_status = "updated"
    setting.auto_check_completed_for_period = True
    setting.auto_check_last_updated_at = now_utc
    setting.auto_check_last_value_rounded = rounded
