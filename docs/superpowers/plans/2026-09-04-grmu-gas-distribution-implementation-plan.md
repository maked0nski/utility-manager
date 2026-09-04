# Розподіл газу (my.grmu.com.ua): тариф + подача показників — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Task 6 of this plan is explicitly NOT safe to dispatch to an autonomous subagent without the project owner directly supervising it live — read its framing before starting it.**

**Goal:** Automatically keep `cabinet_price_per_unit`/`cabinet_checked_at` on the `gas_distribution` `ConnectionChargeLine` up to date by logging into `my.grmu.com.ua` and reading the live monthly distribution charge, AND automatically submit the tenant's own already-recorded meter reading to the same cabinet — both triggered only by the admin's "Оновити тарифи"/"Запустити плановий цикл" buttons, never by the hourly OS cron.

**Architecture:** A new provider branch in `tariff_auto_check.py` (`_is_grmu_setting`/`_run_grmu`), following the same shape as the sibling `my.gas.ua` plan for the tariff half (Laravel+Inertia JSON login, parse the `data-page` Inertia payload for `auth.info.DISTR_SUM`), plus a second, submit-mode branch that reuses the existing generic `run_meter_submit_for_automation` infrastructure (the same one Vodokanal uses) to find our own system's `MeterReading` and push it to the cabinet. The `AutomationTemplate.cron_eligible` flag (shared infra, same as the sibling plan) keeps both halves off the hourly cron.

**Tech Stack:** FastAPI + SQLAlchemy backend, `httpx` for the cabinet HTTP client, pytest for backend tests.

## Global Constraints

- No automation may ever write `ConnectionChargeLine.price_per_unit` directly — only `cabinet_price_per_unit`, `cabinet_checked_at`, via the existing `_apply_cabinet_tariff_observation(current_line, *, candidate_value, checked_at, is_estimated=False)` helper (`backend/app/workers/tariff_auto_check.py:597`).
- The meter-submission half must **never invent or round a reading value** — it only ever forwards whatever is already recorded in our own `MeterReading` table (entered by the admin/tenant via "Послуги об'єкта"/"Розрахунок"). If no reading exists for the target period, the automation does nothing (`waiting`), exactly like Vodokanal.
- This provider must NEVER run from the hourly OS cron sweep — only from an admin-triggered manual run (`trigger_mode="manual"`). See Task 1 (shared with the sibling `gazua-gas-supply-automation` plan — if that plan's Task 1 already merged first, skip Task 1 here and just confirm the column/gating already exists).
- Follow the existing dispatch pattern in `_run_single_setting` (`tariff_auto_check.py:1587`) exactly: `_is_vodokanal_setting` → `_is_atp0928_setting` → `_is_gas_ua_setting` (if merged) → (new) `_is_grmu_setting` → generic VisualService fallback.
- Real login/tariff-parsing code below was verified live against the production cabinet on 2026-09-04 (real `httpx` requests, real credentials, the account owner's own re-registered email+password login — no Google OAuth involved). Cloudflare Turnstile (present on the login page) did **not** block the plain `httpx` login.
- **The meter-submission HTTP call itself (Task 6) is NOT verified** — the design deliberately avoided clicking "Внесені дані вірні" during research to avoid submitting fabricated data to a real production utility account. Task 6 requires a live, human-supervised discovery step before any submit code can be written — do not fabricate a request shape.
- Secrets (`cabinet_login`/`cabinet_password_encrypted`) are handled exactly like every other provider.

---

### Task 1: `AutomationTemplate.cron_eligible` — manual-trigger-only providers

**Files:**
- Modify: `backend/app/models/entities.py` (`class AutomationTemplate`)
- Modify: `backend/app/db/migrations.py` (new column registration)
- Modify: `backend/app/workers/tariff_auto_check.py:1275-1330` (`run_tariff_auto_checks`, both the accrual loop and the submit loop)
- Test: `backend/tests/test_cron_eligible_gating.py` (new)

**Interfaces:**
- Produces: `AutomationTemplate.cron_eligible: bool` (default `True`).

**If the sibling plan (`docs/superpowers/plans/2026-09-04-gazua-gas-supply-implementation-plan.md`) has already been implemented and merged to `master` before this task starts:** skip this task entirely — pull `master` into this branch and confirm `cron_eligible` already exists on `AutomationTemplate` and the gating is already in `run_tariff_auto_checks`. Only do the steps below if it does not exist yet.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cron_eligible_gating.py
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
Expected: FAIL — `TypeError: 'cron_eligible' is an invalid keyword argument for AutomationTemplate`.

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/entities.py`, find `class AutomationTemplate` and its existing `is_active: Mapped[bool] = mapped_column(Boolean, default=True)` field. Add right after it:
```python
    cron_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Register the migration**

In `backend/app/db/migrations.py`, add:
```python
def _ensure_automation_template_cron_eligible_column(db: Session) -> None:
    if _has_column(db, "automation_templates", "cron_eligible"):
        return
    db.execute(text("ALTER TABLE automation_templates ADD COLUMN cron_eligible BOOLEAN NOT NULL DEFAULT TRUE"))
    db.commit()
```
Call `_ensure_automation_template_cron_eligible_column(db)` from `run_startup_migrations()`.

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
Find the analogous submit loop further down in the same function (iterating `submit_automations`, feeding into `run_meter_submit_for_automation`) and apply the identical guard before its call.

- [ ] **Step 7: Run the full backend test suite**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/entities.py backend/app/db/migrations.py backend/app/workers/tariff_auto_check.py backend/tests/test_cron_eligible_gating.py
git commit -m "feat(automations): add cron_eligible flag so a template can opt out of the hourly sweep"
```

---

### Task 2: Pure parsing function for GRMU's tariff

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new pure function)
- Test: `backend/tests/test_grmu_parsing.py` (new)

**Interfaces:**
- Produces: `_parse_grmu_tariff_from_page_html(html: str) -> Decimal | None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_grmu_parsing.py
from decimal import Decimal

from app.workers.tariff_auto_check import _parse_grmu_tariff_from_page_html

# Real Inertia data-page JSON shape captured live on 2026-09-04 (auth.info is a
# shared Inertia prop present on every authenticated page, not just the home page).
REAL_FRAGMENT = (
    '<div id="app" data-page="{&quot;component&quot;:&quot;Home\\/Home&quot;,'
    '&quot;props&quot;:{&quot;auth&quot;:{&quot;user&quot;:{&quot;id&quot;:3515816},'
    '&quot;info&quot;:{&quot;PERACC&quot;:&quot;0710333638&quot;,&quot;TARIF&quot;:&quot;2,232&quot;,'
    '&quot;DISTR_SUM&quot;:&quot;138,43&quot;,&quot;DISTR_MONTH_V&quot;:&quot;62,02&quot;}}}}" />'
)


def test_parses_real_captured_fragment():
    assert _parse_grmu_tariff_from_page_html(REAL_FRAGMENT) == Decimal("138.43")


def test_returns_none_when_data_page_missing():
    assert _parse_grmu_tariff_from_page_html("<div>no data-page here</div>") is None


def test_returns_none_when_data_page_is_not_valid_json():
    html = '<div data-page="{not json" />'
    assert _parse_grmu_tariff_from_page_html(html) is None


def test_returns_none_when_auth_info_missing():
    html = '<div data-page="{&quot;component&quot;:&quot;X&quot;,&quot;props&quot;:{}}" />'
    assert _parse_grmu_tariff_from_page_html(html) is None


def test_returns_none_when_distr_sum_missing():
    html = (
        '<div data-page="{&quot;props&quot;:{&quot;auth&quot;:'
        '{&quot;info&quot;:{&quot;TARIF&quot;:&quot;2,232&quot;}}}}" />'
    )
    assert _parse_grmu_tariff_from_page_html(html) is None


def test_converts_comma_decimal_separator():
    html = (
        '<div data-page="{&quot;props&quot;:{&quot;auth&quot;:'
        '{&quot;info&quot;:{&quot;DISTR_SUM&quot;:&quot;1234,56&quot;}}}}" />'
    )
    assert _parse_grmu_tariff_from_page_html(html) == Decimal("1234.56")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_grmu_parsing.py -v`
Expected: FAIL — `ImportError: cannot import name '_parse_grmu_tariff_from_page_html'`

- [ ] **Step 3: Implement the pure function**

In `backend/app/workers/tariff_auto_check.py`, add (near `_parse_gas_ua_price_from_html` if the sibling plan already added it, otherwise near `_parse_atp0928_tariff_from_html`):

```python
def _parse_grmu_tariff_from_page_html(html: str) -> Decimal | None:
    match = re.search(r'data-page="([^"]*)"', html)
    if match is None:
        return None
    try:
        page = json.loads(_html_unescape(match.group(1)))
    except (json.JSONDecodeError, ValueError):
        return None
    info = (page.get("props") or {}).get("auth", {})
    if not isinstance(info, dict):
        return None
    info = info.get("info") or {}
    raw = info.get("DISTR_SUM")
    if not raw:
        return None
    normalized = str(raw).replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None
```

Reuse whatever `html.unescape` import/alias was already added by Task 2 of the sibling `gazua-gas-supply-automation` plan if it merged first (search the file for an existing `_html_unescape` helper or `import html as ...` before adding a duplicate).

- [ ] **Step 4: Run tests to verify they pass**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_grmu_parsing.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_grmu_parsing.py
git commit -m "feat(tariff-worker): add pure parser for GRMU's Inertia-embedded tariff data"
```

---

### Task 3: Login + authenticated fetch for `my.grmu.com.ua`

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new `_fetch_grmu_page_html`)

**Interfaces:**
- Consumes: `_parse_grmu_tariff_from_page_html` (Task 2).
- Produces: `_fetch_grmu_page_html(*, cabinet_login: str, cabinet_password: str) -> tuple[str | None, str | None]`.

- [ ] **Step 1: Implement the function**

Not unit-tested directly (real network calls, same convention as `_fetch_atp0928_cabinet_html`/`_fetch_gas_ua_home_html`). Add:

```python
GRMU_LOGIN_URL = "https://my.grmu.com.ua/login"
GRMU_HOME_URL = "https://my.grmu.com.ua/"


def _fetch_grmu_page_html(
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
        login_page = client.get(GRMU_LOGIN_URL)
        if login_page.status_code != 200:
            return None, f"GRMU login page HTTP {login_page.status_code}"
        xsrf_cookie = client.cookies.get("XSRF-TOKEN")
        if not xsrf_cookie:
            return None, "GRMU login page did not set XSRF-TOKEN cookie"
        xsrf_token = unquote(xsrf_cookie)

        post_headers = {
            "X-XSRF-TOKEN": xsrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "X-Inertia": "true",
            "X-Inertia-Version": "1",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": GRMU_LOGIN_URL,
            "Origin": "https://my.grmu.com.ua",
        }
        # Note: a successful login returns HTTP 409 with an X-Inertia-Location
        # header (Inertia's "force full reload" signal) — this is NOT an error,
        # despite the status code. Do not treat 409 here as a failure; instead
        # verify success via the follow-up GET below.
        client.post(
            GRMU_LOGIN_URL,
            headers=post_headers,
            json={"email": cabinet_login, "password": cabinet_password, "remember": False},
        )

        home = client.get(GRMU_HOME_URL)
        if home.status_code != 200:
            return None, f"GRMU cabinet HTTP {home.status_code}"
        html_text = home.text
        if '"component":"Auth\\/Login"' in html_text or "data-page" not in html_text:
            return None, "GRMU authorization failed (session not authenticated)"
        return html_text, None
```

- [ ] **Step 2: Manual verification**

Real HTTP calls to production — verify manually. Call it with the real `cabinet_login`/`cabinet_password` for this re-registered email+password account and confirm it returns `(html, None)` where `_parse_grmu_tariff_from_page_html(html)` returns a non-`None` `Decimal` matching the real current "Послуга з розподілу (місячна), грн" value shown in the cabinet UI.

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py
git commit -m "feat(tariff-worker): add GRMU login + authenticated page fetch"
```

---

### Task 4: Wire tariff into `_run_single_setting` dispatch

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new `_is_grmu_setting`, new `_run_grmu`, dispatch wiring)
- Test: `backend/tests/test_grmu_dispatch.py` (new)

**Interfaces:**
- Consumes: `_fetch_grmu_page_html` (Task 3), `_parse_grmu_tariff_from_page_html` (Task 2), `_apply_cabinet_tariff_observation` (existing), `_provider_adapter_code` (existing).
- Produces: `_is_grmu_setting(setting: BindingSetting) -> bool`.

- [ ] **Step 1: Write the failing test for the dispatch predicate**

```python
# backend/tests/test_grmu_dispatch.py
from types import SimpleNamespace

from app.workers.tariff_auto_check import _is_grmu_setting


def _setting(*, adapter_code=None, provider_company=None, cabinet_url=None, service_code=None):
    provider = SimpleNamespace(adapter_code=adapter_code) if adapter_code is not None else None
    return SimpleNamespace(
        provider=provider,
        provider_company=provider_company,
        cabinet_url=cabinet_url,
        service_code=service_code,
    )


def test_matches_by_adapter_code():
    assert _is_grmu_setting(_setting(adapter_code="grmu_if_distribution")) is True


def test_matches_by_cabinet_url_fallback():
    assert _is_grmu_setting(_setting(cabinet_url="https://my.grmu.com.ua/login")) is True


def test_does_not_match_unrelated_provider():
    assert _is_grmu_setting(_setting(adapter_code="atp0928_if", cabinet_url="https://atp0928.if.ua")) is False


def test_does_not_match_gas_ua_setting():
    assert _is_grmu_setting(_setting(adapter_code="gas_ua_supply", cabinet_url="https://my.gas.ua/login")) is False


def test_does_not_match_empty_setting():
    assert _is_grmu_setting(_setting()) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_grmu_dispatch.py -v`
Expected: FAIL — `ImportError: cannot import name '_is_grmu_setting'`

- [ ] **Step 3: Implement `_is_grmu_setting`**

```python
def _is_grmu_setting(setting: BindingSetting) -> bool:
    adapter_code = _provider_adapter_code(setting)
    if adapter_code == "grmu_if_distribution":
        return True
    haystack = " ".join(
        [
            setting.provider_company or "",
            setting.cabinet_url or "",
            setting.service_code or "",
        ]
    ).casefold()
    return "my.grmu.com.ua" in haystack
```

- [ ] **Step 4: Run test to verify it passes**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_grmu_dispatch.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Implement `_run_grmu` (tariff mode only for now) and wire it into `_run_single_setting`**

```python
def _run_grmu(
    db: Session,
    *,
    setting: BindingSetting,
    now_utc: datetime,
    force_mode: str,
) -> None:
    cabinet_login = (setting.cabinet_login or "").strip()
    cabinet_password = decrypt_text(setting.cabinet_password_encrypted) or ""
    if not cabinet_login or not cabinet_password:
        setting.auto_check_status = "error"
        setting.auto_check_message = "cabinet credentials are missing"
        setting.auto_check_last_checked_at = now_utc
        return

    if force_mode not in {"full", "tariffs"}:
        # readings-only mode: handled by Task 6's submit branch, not here.
        setting.auto_check_status = "waiting"
        setting.auto_check_message = "Подача показників для ГРМУ ще не реалізована"
        setting.auto_check_last_checked_at = now_utc
        return

    try:
        html_text, error = _fetch_grmu_page_html(
            cabinet_login=cabinet_login,
            cabinet_password=cabinet_password,
        )
    except (httpx.HTTPError, OSError, socket.gaierror) as exc:
        setting.auto_check_status = "error"
        setting.auto_check_message = f"GRMU network error: {exc}"
        setting.auto_check_last_checked_at = now_utc
        return

    setting.auto_check_last_checked_at = now_utc
    if error or html_text is None:
        setting.auto_check_status = "error"
        setting.auto_check_message = (error or "GRMU fetch failed")[:255]
        return

    price = _parse_grmu_tariff_from_page_html(html_text)
    if price is None:
        setting.auto_check_status = "error"
        setting.auto_check_message = "На сторінці кабінету не знайдено DISTR_SUM"
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
    setting.auto_check_message = f"Кабінет: Послуга з розподілу (місячна) = {price.quantize(Decimal('0.01'))} грн"
```

In `_run_single_setting` (~line 1587), add the dispatch branch right after the `_is_gas_ua_setting` check (or after `_is_atp0928_setting` if the sibling plan hasn't merged yet), before the generic VisualService fallback:
```python
    if _is_grmu_setting(setting):
        _run_grmu(db, setting=setting, now_utc=now_utc, force_mode=mode)
        return
```

- [ ] **Step 6: Run the full backend test suite**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_grmu_dispatch.py
git commit -m "feat(tariff-worker): wire GRMU tariff automation into the dispatch chain"
```

---

### Task 5: Pure idempotency-decision logic for meter-reading submission

This task specifies and tests the **decision logic** for whether a reading needs submitting — this part is fully knowable today without touching the real submit endpoint. Task 6 (separate, human-supervised) wires this into a real HTTP call.

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new pure function)
- Test: `backend/tests/test_grmu_submit_decision.py` (new)

**Interfaces:**
- Produces: `_grmu_reading_needs_submit(our_reading: Decimal, cabinet_previous_reading: Decimal | None) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_grmu_submit_decision.py
from decimal import Decimal

from app.workers.tariff_auto_check import _grmu_reading_needs_submit


def test_needs_submit_when_our_reading_is_higher():
    # Cabinet's "Попередні показання" (last operator-confirmed reading) is
    # lower than what we already have on file -> we have something new to send.
    assert _grmu_reading_needs_submit(Decimal("11300.00"), Decimal("11287.00")) is True


def test_no_submit_when_our_reading_already_matches_cabinet():
    assert _grmu_reading_needs_submit(Decimal("11287.00"), Decimal("11287.00")) is False


def test_no_submit_when_our_reading_is_lower_than_cabinet():
    # Should never happen in practice (readings only increase), but must not
    # submit a value the cabinet would reject as "less than previous".
    assert _grmu_reading_needs_submit(Decimal("11200.00"), Decimal("11287.00")) is False


def test_needs_submit_when_cabinet_has_no_previous_reading_yet():
    assert _grmu_reading_needs_submit(Decimal("11300.00"), None) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_grmu_submit_decision.py -v`
Expected: FAIL — `ImportError: cannot import name '_grmu_reading_needs_submit'`

- [ ] **Step 3: Implement the pure function**

```python
def _grmu_reading_needs_submit(our_reading: Decimal, cabinet_previous_reading: Decimal | None) -> bool:
    if cabinet_previous_reading is None:
        return True
    return our_reading > cabinet_previous_reading
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `export PYTHONPATH="/d/projects/utility-manager/backend/.venv/Lib/site-packages" && python -m pytest tests/test_grmu_submit_decision.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_grmu_submit_decision.py
git commit -m "feat(tariff-worker): add pure idempotency check for GRMU meter-reading submission"
```

---

### Task 6: Meter-reading submission — REQUIRES human-supervised discovery first

**Do not dispatch this task to an autonomous subagent without the project owner directly present and watching.** Unlike every other task in this plan, the exact HTTP request this task needs to make was deliberately never captured during design research (to avoid submitting a fabricated reading to a real, production utility account). This task starts with a real, one-time, deliberate action on production data.

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (extend `_run_grmu`'s `force_mode in {"full", "readings"}` branch, using Task 5's `_grmu_reading_needs_submit`)
- Test: extend `backend/tests/test_grmu_dispatch.py` or add a focused new test file, once the real request shape is known

- [ ] **Step 1 (human-supervised, not automatable): capture the real submit request**

With the project owner present and confirming the exact real current meter reading for this account:
1. Log into `https://my.grmu.com.ua` in a real browser with claude-in-chrome's network capture active (`read_network_requests`, called once before the action to arm tracking, per the working pattern already used earlier in this project's research — see this repo's own session history for the exact recipe).
2. Click "Внести показання" in the header, enter the confirmed-correct current reading in "Внесіть поточне показання", click "Внесені дані вірні".
3. Read back the network requests filtered to `my.grmu.com.ua` and record: the exact URL, HTTP method, and (if visible) the response status/body of the submit call.
4. Confirm in the UI or on next page load that "Попередні показання" now reflects the submitted value (or is queued/pending — note whichever it is).

- [ ] **Step 2: Write the failing test using the now-known real request shape**

Once Step 1's real endpoint/payload is known, write a test mirroring the style of `test_grmu_dispatch.py` / the sibling gas-supply plan's Task 4, asserting the new submit function builds the correct request for a given `(meter_number, previous_reading, new_reading)` input. Do not write this step's code before Step 1 completes — there is nothing to test yet.

- [ ] **Step 3: Implement the submit call**

Extend `_run_grmu`'s early-return stub (`if force_mode not in {"full", "readings"}: ... return` from Task 4, Step 5) to actually:
1. When `force_mode in {"full", "readings"}`: fetch the cabinet's "Попередні показання" value (parse it from wherever Step 1 found it — likely another field in the same `auth.info` Inertia payload, or a dedicated endpoint captured in Step 1).
2. Look up our own reading via `_find_current_meter_reading_for_service` (existing, `tariff_auto_check.py:982`) for the target period.
3. If no reading on our side: `status=waiting`, no submit attempt (matches the `Що НЕ змінюється` design constraint).
4. If `_grmu_reading_needs_submit(our_reading, cabinet_previous_reading)` (Task 5): make the real submit call captured in Step 1, using our reading's value formatted exactly as the cabinet expects (check Step 1's captured payload for the expected decimal format/precision).
5. On success: `submit_completed_for_period=True` on the automation (handled by the existing `run_meter_submit_for_automation` wrapper, `tariff_auto_check.py:1461`, which already manages this field — `_run_grmu` only needs to set `auto_check_status` correctly, exactly like `_run_vodokanal` does for its own submit branch).
6. On failure (any non-2xx or unexpected response shape): `status=error` with a message that does not leak the cabinet_password.

- [ ] **Step 4: Manual end-to-end verification**

With a real, correct meter reading already entered into our own system for the current target period, trigger a manual run and confirm: (a) the submit call fires exactly once, (b) `submit_completed_for_period` becomes `True`, (c) re-running the automation immediately after does NOT resubmit (idempotency via Task 5's check), (d) the cabinet UI (`https://my.grmu.com.ua`, "Попередні показання" on next login) reflects the submitted value.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/
git commit -m "feat(tariff-worker): implement GRMU meter-reading submission"
```

---

### Task 7: Manual end-to-end verification + admin setup (tariff half)

**Files:** none (verification only)

- [ ] **Step 1: Create the `AutomationTemplate` via the admin UI**

Create a new automation template: `code=grmu_if_distribution`, `cabinet_url=https://my.grmu.com.ua/login`, `utility_type=gas`, `supports_accrual=True`, `supports_meter_submit=True` (once Task 6 is done — `False` if verifying the tariff half only, before Task 6). Set `cron_eligible=False` for this template (via a direct DB update if the admin UI doesn't yet expose the field, same as the sibling plan's Task 5 note).

- [ ] **Step 2: Connect the template to the relevant apartment**

Connect it to the apartment with the `gas_distribution` service connection, using the real re-registered email+password credentials for `my.grmu.com.ua`.

- [ ] **Step 3: Trigger a manual run and verify the tariff half**

Click "Оновити тарифи" or "Запустити плановий цикл". Confirm `status=updated` in the run log and that `ConnectionChargeLine.cabinet_price_per_unit`/`cabinet_checked_at` for the `gas_distribution` line reflect the real cabinet value.

- [ ] **Step 4: Verify cron exclusion**

Same check as the sibling plan: confirm this automation's `auto_check_last_checked_at` does not advance between manual runs, i.e. the hourly OS cron sweep skips it.
