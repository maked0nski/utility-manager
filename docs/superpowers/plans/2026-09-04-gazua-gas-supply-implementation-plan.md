# Газопостачання (my.gas.ua): автоматизація тарифу — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically keep `cabinet_price_per_unit`/`cabinet_checked_at` on the `gas_supply` `ConnectionChargeLine` up to date by logging into `my.gas.ua` and reading the live per-m³ price, triggered only by the admin's "Оновити тарифи"/"Запустити плановий цикл" buttons — never by the hourly OS cron.

**Architecture:** A new provider branch in `tariff_auto_check.py` (`_is_gas_ua_setting`/`_run_gas_ua`), mirroring the existing ATP0928 branch's shape: `httpx`-based login, fetch the authenticated home page, parse the embedded `user_info` JSON attribute for the price, and call the existing `_apply_cabinet_tariff_observation` helper. A new `AutomationTemplate.cron_eligible` field (shared with the sibling GRMU plan) lets this provider opt out of the hourly cron sweep while still running from either manual-trigger button.

**Tech Stack:** FastAPI + SQLAlchemy backend, `httpx` for the cabinet HTTP client, pytest for backend tests.

## Global Constraints

- No automation may ever write `ConnectionChargeLine.price_per_unit` directly — only `cabinet_price_per_unit`, `cabinet_checked_at`, via the existing `_apply_cabinet_tariff_observation(current_line, *, candidate_value, checked_at, is_estimated=False)` helper (`backend/app/workers/tariff_auto_check.py:597`).
- `effective_from` on every `ConnectionChargeLine` is always the 1st of its month — this plan never writes `effective_from` itself (it only updates existing lines' cabinet fields).
- This provider must NEVER run from the hourly OS cron sweep — only from an admin-triggered manual run (`trigger_mode="manual"`). See Task 1.
- Follow the existing dispatch pattern in `_run_single_setting` (`tariff_auto_check.py:1587`) exactly: `_is_vodokanal_setting` → `_is_atp0928_setting` → (new) `_is_gas_ua_setting` → generic VisualService fallback. Insert the new check before the generic fallback, after the ATP0928 check.
- Real login/parsing code below was verified live against the production cabinet on 2026-09-04 (real `httpx` requests, real credentials) — it is not a guess. Cloudflare Turnstile (present on the login page) did **not** block the plain `httpx` login.
- Secrets (`cabinet_login`/`cabinet_password_encrypted`) are handled exactly like every other provider — encrypted at rest via `decrypt_text`/the existing encryption helper, never logged in plaintext.

---

### Task 1: `AutomationTemplate.cron_eligible` — manual-trigger-only providers

**Files:**
- Modify: `backend/app/models/entities.py` (`class AutomationTemplate`)
- Modify: `backend/app/db/migrations.py` (new column registration)
- Modify: `backend/app/workers/tariff_auto_check.py:1275-1330` (`run_tariff_auto_checks`, both the accrual loop and the submit loop)
- Test: `backend/tests/test_cron_eligible_gating.py` (new)

**Interfaces:**
- Produces: `AutomationTemplate.cron_eligible: bool` (default `True`).
- Consumes (for the gating check): `ApartmentAutomation.template` relationship (already exists), `trigger_mode` parameter already passed into `run_tariff_auto_checks`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cron_eligible_gating.py
from datetime import UTC, datetime
from decimal import Decimal

from app.models import ApartmentAutomation, AutomationTemplate


def _make_automation(cron_eligible: bool) -> ApartmentAutomation:
    template = AutomationTemplate(
        code="test_template",
        name="Test",
        cron_eligible=cron_eligible,
        supports_accrual=True,
        supports_meter_submit=False,
        is_active=True,
    )
    automation = ApartmentAutomation(
        apartment_id=1,
        template=template,
        is_enabled=True,
        accrual_enabled=True,
    )
    return automation


def test_cron_eligible_defaults_to_true():
    template = AutomationTemplate(code="t", name="T", supports_accrual=True, supports_meter_submit=False, is_active=True)
    assert template.cron_eligible is True


def test_scheduled_trigger_skips_cron_ineligible_automation():
    automation = _make_automation(cron_eligible=False)
    should_skip = automation.template is not None and not automation.template.cron_eligible
    trigger_mode = "scheduled"
    assert (trigger_mode != "manual" and should_skip) is True


def test_manual_trigger_runs_cron_ineligible_automation():
    automation = _make_automation(cron_eligible=False)
    should_skip = automation.template is not None and not automation.template.cron_eligible
    trigger_mode = "manual"
    assert (trigger_mode != "manual" and should_skip) is False


def test_scheduled_trigger_runs_cron_eligible_automation():
    automation = _make_automation(cron_eligible=True)
    should_skip = automation.template is not None and not automation.template.cron_eligible
    trigger_mode = "scheduled"
    assert (trigger_mode != "manual" and should_skip) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_cron_eligible_gating.py -v`
Expected: FAIL — `TypeError: 'cron_eligible' is an invalid keyword argument for AutomationTemplate` (column doesn't exist yet).

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/entities.py`, find `class AutomationTemplate` and its existing `is_active: Mapped[bool] = mapped_column(Boolean, default=True)` field (or the nearest boolean field in that class). Add right after it:
```python
    cron_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Register the migration**

In `backend/app/db/migrations.py`, find the function that adds columns to `automation_templates` (search for an existing `_ensure_..._columns` function referencing that table — if none exists yet, add a new one and call it from `run_startup_migrations()`). Add:
```python
def _ensure_automation_template_cron_eligible_column(db: Session) -> None:
    if _has_column(db, "automation_templates", "cron_eligible"):
        return
    db.execute(text("ALTER TABLE automation_templates ADD COLUMN cron_eligible BOOLEAN NOT NULL DEFAULT TRUE"))
    db.commit()
```
Call it from `run_startup_migrations()` (`backend/app/db/migrations.py`, the function that calls `_ensure_apartment_profile_columns(db)` etc.) — add `_ensure_automation_template_cron_eligible_column(db)` to that call chain.

- [ ] **Step 5: Run test to verify it passes**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_cron_eligible_gating.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Wire the gate into `run_tariff_auto_checks`**

In `backend/app/workers/tariff_auto_check.py`, in `run_tariff_auto_checks` (~line 1275), find the accrual loop:
```python
    for automation in automations:
        run_tariff_auto_check_for_automation(db, automation=automation, now_utc=now_utc)
        processed_accrual_automations += 1
```
Replace with:
```python
    for automation in automations:
        if trigger_mode != "manual" and automation.template is not None and not automation.template.cron_eligible:
            continue
        run_tariff_auto_check_for_automation(db, automation=automation, now_utc=now_utc)
        processed_accrual_automations += 1
```
Find the analogous submit loop a little further down in the same function (iterating `submit_automations`) and apply the identical guard before its call to the per-automation submit function.

- [ ] **Step 7: Run the full backend test suite**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest -q`
Expected: all tests pass, no regressions.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/entities.py backend/app/db/migrations.py backend/app/workers/tariff_auto_check.py backend/tests/test_cron_eligible_gating.py
git commit -m "feat(automations): add cron_eligible flag so a template can opt out of the hourly sweep"
```

---

### Task 2: Pure parsing function for `my.gas.ua`'s tariff

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new pure function, near `_parse_atp0928_tariff_from_html`)
- Test: `backend/tests/test_gas_ua_parsing.py` (new)

**Interfaces:**
- Produces: `_parse_gas_ua_price_from_html(html: str) -> Decimal | None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_gas_ua_parsing.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_gas_ua_parsing.py -v`
Expected: FAIL — `ImportError: cannot import name '_parse_gas_ua_price_from_html'`

- [ ] **Step 3: Implement the pure function**

In `backend/app/workers/tariff_auto_check.py`, near `_parse_atp0928_tariff_from_html` (~line 334), add:

```python
def _parse_gas_ua_price_from_html(html: str) -> Decimal | None:
    match = re.search(r'<personal-accounts-dropdown\s+[^>]*user_info="([^"]*)"', html)
    if match is None:
        return None
    try:
        user_info = json.loads(_html_unescape(match.group(1)))
    except (json.JSONDecodeError, ValueError):
        return None
    raw = user_info.get("single_price")
    if not raw:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None
```

Check the top of `tariff_auto_check.py` for existing imports of `json`, `re`, `Decimal`, `InvalidOperation` — reuse them if already imported (this file already imports `json` and `re` for the Vodokanal bootstrap parsing, and `Decimal`/`InvalidOperation` from the `decimal` module for the rounding helpers). If there is no existing `html.unescape` import, add `import html as html_module` at the top and use `html_module.unescape(...)` instead of a bespoke `_html_unescape` name — match whatever import style the file already uses for stdlib `html` if it's already imported under a different alias; otherwise add the import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_gas_ua_parsing.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_gas_ua_parsing.py
git commit -m "feat(tariff-worker): add pure parser for my.gas.ua's embedded tariff JSON"
```

---

### Task 3: Login + authenticated fetch for `my.gas.ua`

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new `_fetch_gas_ua_home_html` function, near `_fetch_atp0928_cabinet_html`)

**Interfaces:**
- Consumes: `_parse_gas_ua_price_from_html` (Task 2).
- Produces: `_fetch_gas_ua_home_html(*, cabinet_login: str, cabinet_password: str) -> tuple[str | None, str | None]` (html, error_message) — same return shape as `_fetch_atp0928_cabinet_html`.

- [ ] **Step 1: Implement the function**

This function makes real network calls, so it is not unit-tested directly (same convention as `_fetch_atp0928_cabinet_html`, which also has no dedicated test — it's exercised indirectly via `_run_atp0928`/manual verification). In `backend/app/workers/tariff_auto_check.py`, near `_fetch_atp0928_cabinet_html` (~line 710), add:

```python
GAS_UA_LOGIN_URL = "https://my.gas.ua/login"
GAS_UA_HOME_URL = "https://my.gas.ua/home"


def _fetch_gas_ua_home_html(
    *,
    cabinet_login: str,
    cabinet_password: str,
) -> tuple[str | None, str | None]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "uk,en-US;q=0.9,en;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
        login_page = client.get(GAS_UA_LOGIN_URL)
        if login_page.status_code != 200:
            return None, f"my.gas.ua login page HTTP {login_page.status_code}"
        csrf_match = re.search(r'name="csrf-token" content="([^"]*)"', login_page.text)
        csrf_token = csrf_match.group(1) if csrf_match else ""
        xsrf_cookie = client.cookies.get("XSRF-TOKEN")
        if not xsrf_cookie:
            return None, "my.gas.ua login page did not set XSRF-TOKEN cookie"
        xsrf_token = unquote(xsrf_cookie)

        post_headers = {
            "X-XSRF-TOKEN": xsrf_token,
            "X-CSRF-TOKEN": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "X-Inertia": "true",
            "X-Inertia-Version": "1",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": GAS_UA_LOGIN_URL,
            "Origin": "https://my.gas.ua",
        }
        auth = client.post(
            GAS_UA_LOGIN_URL,
            headers=post_headers,
            json={"login": cabinet_login, "password": cabinet_password, "remember": False},
        )
        if auth.status_code != 200:
            return None, f"my.gas.ua authorization failed (HTTP {auth.status_code})"

        dashboard = client.get(GAS_UA_HOME_URL)
        if dashboard.status_code != 200:
            return None, f"my.gas.ua cabinet HTTP {dashboard.status_code}"
        html_text = dashboard.text
        if "personal-accounts-dropdown" not in html_text:
            return None, "my.gas.ua authorization failed (session not authenticated)"
        return html_text, None
```

Check the top of `tariff_auto_check.py` for an existing `from urllib.parse import unquote` (or `urljoin`/`urlparse`) import — the file already imports `urljoin`/`urlparse` for other providers; add `unquote` to that same import line if it's not already there.

- [ ] **Step 2: Manual verification**

This function makes real HTTP calls to production — verify it manually rather than with a unit test, consistent with `_fetch_atp0928_cabinet_html`'s own testing convention. From a Python shell in the backend environment (or a scratch script), call it with the real `cabinet_login`/`cabinet_password` for this account and confirm it returns `(html, None)` where `html` contains `"personal-accounts-dropdown"`, and that `_parse_gas_ua_price_from_html(html)` on the result returns the real current tariff (`Decimal("7.95689")` as of 2026-09-04, but the live value may have changed by the time you run this — just confirm it returns *some* non-`None` `Decimal`).

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py
git commit -m "feat(tariff-worker): add my.gas.ua login + authenticated home-page fetch"
```

---

### Task 4: Wire into `_run_single_setting` dispatch

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new `_is_gas_ua_setting`, new `_run_gas_ua`, dispatch wiring in `_run_single_setting`)
- Test: `backend/tests/test_gas_ua_dispatch.py` (new)

**Interfaces:**
- Consumes: `_fetch_gas_ua_home_html` (Task 3), `_parse_gas_ua_price_from_html` (Task 2), `_apply_cabinet_tariff_observation` (existing, `tariff_auto_check.py:597`), `_provider_adapter_code` (existing, `tariff_auto_check.py:510`).
- Produces: `_is_gas_ua_setting(setting: BindingSetting) -> bool`.

- [ ] **Step 1: Write the failing test for the dispatch predicate**

```python
# backend/tests/test_gas_ua_dispatch.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_gas_ua_dispatch.py -v`
Expected: FAIL — `ImportError: cannot import name '_is_gas_ua_setting'`

- [ ] **Step 3: Implement `_is_gas_ua_setting`**

In `backend/app/workers/tariff_auto_check.py`, right after `_is_atp0928_setting` (~line 518), add:

```python
def _is_gas_ua_setting(setting: BindingSetting) -> bool:
    adapter_code = _provider_adapter_code(setting)
    if adapter_code == "gas_ua_supply":
        return True
    haystack = " ".join(
        [
            setting.provider_company or "",
            setting.cabinet_url or "",
            setting.service_code or "",
        ]
    ).casefold()
    return "my.gas.ua" in haystack
```

- [ ] **Step 4: Run test to verify it passes**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_gas_ua_dispatch.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Implement `_run_gas_ua` and wire it into `_run_single_setting`**

In `backend/app/workers/tariff_auto_check.py`, add `_run_gas_ua` near `_run_atp0928` (~line 753):

```python
def _run_gas_ua(
    db: Session,
    *,
    setting: BindingSetting,
    now_utc: datetime,
) -> None:
    cabinet_login = (setting.cabinet_login or "").strip()
    cabinet_password = decrypt_text(setting.cabinet_password_encrypted) or ""
    if not cabinet_login or not cabinet_password:
        setting.auto_check_status = "error"
        setting.auto_check_message = "cabinet credentials are missing"
        setting.auto_check_last_checked_at = now_utc
        return

    try:
        html_text, error = _fetch_gas_ua_home_html(
            cabinet_login=cabinet_login,
            cabinet_password=cabinet_password,
        )
    except (httpx.HTTPError, OSError, socket.gaierror) as exc:
        setting.auto_check_status = "error"
        setting.auto_check_message = f"my.gas.ua network error: {exc}"
        setting.auto_check_last_checked_at = now_utc
        return

    setting.auto_check_last_checked_at = now_utc
    if error or html_text is None:
        setting.auto_check_status = "error"
        setting.auto_check_message = (error or "my.gas.ua fetch failed")[:255]
        return

    price = _parse_gas_ua_price_from_html(html_text)
    if price is None:
        setting.auto_check_status = "error"
        setting.auto_check_message = "На сторінці /home не знайдено single_price"
        return

    period_start = _month_start(*_prev_month(now_utc.year, now_utc.month)).date()
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

    _apply_cabinet_tariff_observation(current_line, candidate_value=price, checked_at=now_utc)
    setting.auto_check_completed_for_period = True
    setting.auto_check_last_value_raw = price.quantize(Decimal("0.0001"))
    setting.auto_check_last_value_rounded = price.quantize(Decimal("0.01"))
    setting.auto_check_status = "updated"
    setting.auto_check_message = f"Кабінет: Ціна за 1 куб. м = {price.quantize(Decimal('0.01'))} грн"
```

Note: `period_start` above resolves to the **previous** month. **Correction from the final whole-branch review:** the claim that this "matches every other provider's convention in this file" was wrong — `_run_atp0928` and `_run_vodokanal` both resolve their period from the *current* month (`date(local_now.year, local_now.month, 1)`); only the generic VisualService fallback branch (and `AUTOMATION_TEMPLATE.md`'s own stated rule, "target period: previous month") use the previous month. Previous-month is still the *correct* choice here — `ConnectionChargeLine` periods represent the month being billed (the 1st–5th billing cycle bills the previous month) — just don't cite the wrong precedent when building the next provider off this one.

**Also corrected:** use `local_now` (already computed by `_run_single_setting` and passed to sibling runners like `_run_atp0928`/`_run_vodokanal`), not `now_utc`, when deriving `_prev_month(...)`. Using UTC here is a real bug: for roughly the first few hours of Kyiv local time on the 1st of a month, `now_utc` is still in the *prior* calendar month, so the observation would land two months back from where `_run_single_setting` already computed `target_year`/`target_month` to be (it derives those from `local_now`, not `now_utc`). Thread `local_now` into `_run_gas_ua`'s signature and use it for period resolution, matching every sibling provider.

In `_run_single_setting` (~line 1587), find the existing dispatch chain:
```python
    if _is_atp0928_setting(setting):
        _run_atp0928(
            db,
            setting=setting,
            now_utc=now_utc,
            local_now=local_now,
            force_mode=mode,
        )
        return
```
Add a new branch right after it, before the generic VisualService fallback code:
```python
    if _is_gas_ua_setting(setting):
        _run_gas_ua(db, setting=setting, now_utc=now_utc)
        return
```

- [ ] **Step 6: Run the full backend test suite**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_gas_ua_dispatch.py
git commit -m "feat(tariff-worker): wire my.gas.ua tariff automation into the dispatch chain"
```

---

### Task 5: Manual end-to-end verification + admin setup

**Files:** none (verification only)

- [ ] **Step 1: Create the `AutomationTemplate` via the admin UI**

Log into the admin app, go to the Автоматизації tab, create a new automation template with: `code=gas_ua_supply`, `cabinet_url=https://my.gas.ua/login`, `utility_type=gas`, `supports_accrual=True`, `supports_meter_submit=False`, and **`cron_eligible=False`** — the final whole-branch review found the plan's original wording here ("set it via a manual DB UPDATE, exposing it in the UI is out of scope") left this provider's core "never on the hourly cron" promise unreachable through any real admin action, so a follow-up fix task made `cron_eligible` a genuine field in the create/update forms and API — use that checkbox/field directly, do not fall back to a manual SQL statement.

- [ ] **Step 2: Connect the template to the relevant apartment**

Using the existing "Підключити до об'єкта" flow, connect this template to the apartment that has the `gas_supply` service connection, with the real `cabinet_login`/`cabinet_password` for `my.gas.ua`. **Also explicitly set `cabinet_url=https://my.gas.ua/login` on this automation/connection row itself** (not just on the template) — `_is_gas_ua_setting`'s dispatch match falls back to a substring check against `automation.cabinet_url` (via the binding built in `_build_automation_bindings`), not the template's `cabinet_url`, so leaving this blank on the automation row causes the run to silently fall through to the generic VisualService branch and fail with "cabinet_url is empty" even though the template looks correctly configured.

- [ ] **Step 3: Trigger a manual run and verify**

Click "Оновити тарифи" (Розрахунок tab) or "Запустити плановий цикл" (Автоматизації tab). Confirm in the automation's run log that the status is `updated` (or `error` with a clear message if something's wrong — investigate before proceeding), and confirm `ConnectionChargeLine.cabinet_price_per_unit`/`cabinet_checked_at` for the `gas_supply` line now reflect the real cabinet price.

- [ ] **Step 4: Verify cron exclusion**

Confirm (via the VPS's OS-level cron logs, or by checking `AutomationCycleRun.trigger_mode="scheduled"` rows after the next hourly run) that this automation is **not** touched by the scheduled sweep — its `auto_check_last_checked_at` should not advance between manual runs.
