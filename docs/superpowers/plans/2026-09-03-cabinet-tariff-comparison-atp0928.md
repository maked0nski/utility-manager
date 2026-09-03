# Тариф з кабінету (АТП-0928) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop auto-writing the ATP-0928 cabinet tariff into billing prices; instead store it separately, show it next to the admin's own tariff on "Розрахунок" with a freshness color and a floor-violation warning — and, along the way, stop returning automation cabinet passwords to the browser in plaintext.

**Architecture:** Two new nullable columns on `ConnectionChargeLine` hold the last-observed cabinet price and when it was checked. The ATP-0928 worker (`_run_atp0928`) writes only those two columns via a small pure helper — `price_per_unit` is never touched automatically anymore. The value is exposed through the existing charge-line API and joined client-side (by `line_id`) into the "Розрахунок" table, where a pure helper computes freshness (≤15 days = fresh) and the 10% floor check. Vodokanal's own auto-write (`_run_vodokanal`) is deliberately left untouched — see "Out of scope".

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), React + TypeScript + Vitest (frontend), pytest (backend tests).

## Global Constraints

- One provider at a time: this plan implements and verifies ATP-0928 only. Vodokanal's equivalent worker change is a separate follow-up plan, done only after ATP-0928 is confirmed working live (per user instruction — no exceptions).
- Cabinet tariff data must never reach `CalculationRow`/`BillingMonthSnapshotItem`/`BillingStatementItem` or any printed/report path — it is joined client-side from `ConnectionChargeLineItem` only, never added to the snapshot/statement row type.
- `price_per_unit` on `ConnectionChargeLine` must never be modified automatically by the ATP-0928 worker after this plan — only by an admin, through the existing manual edit flow.
- Cabinet passwords must never be sent to the browser in plaintext, in any automation list/detail response, from this point on.
- Freshness threshold is exactly 15 days; floor is exactly 10% (`price_per_unit >= cabinet_price_per_unit * 1.10`).

Spec: `docs/superpowers/specs/2026-09-03-cabinet-tariff-comparison-design.md`

---

## Task 1: Stop returning cabinet passwords in plaintext

The automation list/detail endpoints currently decrypt and return the real password on every fetch (`backend/app/api/admin/automations.py:512,554`), and the edit modal in `AutomationsTab.tsx` prefills that real value into its password input. This is what let a real ATP-0928 password become visible in the browser during testing. Replace it with a boolean flag; the frontend switches to a write-only "leave blank to keep unchanged" password field.

**Files:**
- Modify: `backend/app/schemas.py:1007` (`AutomationRowOut`), `backend/app/schemas.py:1098` (`ApartmentAutomationOut`)
- Modify: `backend/app/api/admin/automations.py:512`, `backend/app/api/admin/automations.py:554`
- Modify: `backend/tests/test_p0_stability.py` (if it asserts on `cabinet_password` — check first)
- Modify: `frontend/src/shared/api/types.ts:489` (`AutomationItem`)
- Modify: `frontend/src/features/tariffs/components/AutomationsTab.tsx:189,334,1099-1111`

**Interfaces:**
- Produces: `AutomationItem.cabinet_password_set: boolean` (frontend), `AutomationRowOut.cabinet_password_set: bool` / `ApartmentAutomationOut.cabinet_password_set: bool` (backend) — replaces `cabinet_password: str | None`.
- Consumes: nothing from earlier tasks (this is the first task).

- [ ] **Step 1: Check for existing test assertions on `cabinet_password`**

Run: `grep -n "cabinet_password" backend/tests/*.py`
Expected: no matches, or note any that assert on the plaintext field so Step 6 can update them.

- [ ] **Step 2: Update backend schemas**

In `backend/app/schemas.py`, change line 1007 (inside `AutomationRowOut`):

```python
    cabinet_password_set: bool = False
```

(replacing `cabinet_password: str | None = None`). Change line 1098 (inside `ApartmentAutomationOut`) the same way. Leave `ApartmentAutomationUpsert.cabinet_password: str | None = None` (line 1073) untouched — that's the write-only input field and already has correct "omit to keep unchanged" semantics on the backend (`automations.py:183-184`).

- [ ] **Step 3: Stop decrypting the password into the response**

In `backend/app/api/admin/automations.py`, change line 512 (inside `_automation_row_out`):

```python
        cabinet_password_set=bool(automation.cabinet_password_encrypted),
```

Change line 554 (inside `_apartment_automation_out`) the same way, using `row.cabinet_password_encrypted`. Leave line 806's `decrypt_text(automation.cabinet_password_encrypted)` untouched — that's an internal check before actually running the automation, never sent to the client.

- [ ] **Step 4: Run backend tests**

Run: `docker exec um_api pytest -q`
Expected: all tests pass (no test currently depends on the removed field, per Step 1).

- [ ] **Step 5: Update the frontend type**

In `frontend/src/shared/api/types.ts`, replace line 489:

```ts
  cabinet_password_set?: boolean;
```

- [ ] **Step 6: Update `missingDataMessage` to use the boolean flag**

In `frontend/src/features/tariffs/components/AutomationsTab.tsx`, replace line 189:

```ts
  const missingPassword = !row.cabinet_password_set;
```

- [ ] **Step 7: Stop prefilling the real password into the edit draft**

Replace line 334 (inside `ensureDraft`):

```ts
      cabinet_password: "",
```

(was `row.cabinet_password || ""`). The draft's `cabinet_password` field now always starts empty and only carries a value when the admin types a **new** password to set.

- [ ] **Step 8: Rework the Пароль field in the edit modal**

Replace the block at lines 1099-1111 (the `Пароль` `<div className="field">` inside the `editingRow` modal, added in the previous session's fix):

```tsx
              <div className="field">
                <label className="field-label">Пароль</label>
                <div className="helper">
                  {ensureDraft(editingRow).cabinet_password
                    ? "Буде збережено новий пароль після натискання «Зберегти»."
                    : editingRow.cabinet_password_set
                      ? "Пароль встановлено. Залиште поле порожнім, щоб не змінювати."
                      : "Пароль не встановлено."}
                </div>
                <div className="row-actions">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="Новий пароль"
                    value={ensureDraft(editingRow).cabinet_password}
                    onChange={(e) => updateDraft(editingRow, { cabinet_password: e.target.value })}
                  />
                  <button type="button" className="secondary" onClick={() => setShowPassword((v) => !v)}>
                    {showPassword ? "Сховати" : "Показати"}
                  </button>
                </div>
              </div>
```

`showPassword` already defaults to `false` (`AutomationsTab.tsx:283`), so the field is hidden by default and only ever shows what the admin is currently typing — never a value fetched from the server.

- [ ] **Step 9: Typecheck and lint**

Run (from `frontend/`): `npm run typecheck && npm run lint -- --max-warnings=0`
Expected: both clean.

- [ ] **Step 10: Rebuild frontend and verify live**

Run: `docker compose build frontend && docker compose up -d frontend` (from repo root)
Open the ATP-0928 automation's edit modal (Автоматизації → Підключення до об'єктів → Налаштувати). Confirm: Пароль field is empty by default, shows "Пароль встановлено..." helper text, and the password is never visible on page load (only after typing a new one and clicking "Показати"). Confirm "Показати" on the field no longer reveals the real stored password (there's nothing to reveal — it's write-only now).

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas.py backend/app/api/admin/automations.py frontend/src/shared/api/types.ts frontend/src/features/tariffs/components/AutomationsTab.tsx
git commit -m "fix(automations): stop returning cabinet passwords in plaintext"
```

---

## Task 2: Add `cabinet_price_per_unit` / `cabinet_checked_at` to `ConnectionChargeLine`

**Files:**
- Modify: `backend/app/models/entities.py:542-565` (`ConnectionChargeLine`)
- Create: `backend/alembic/versions/20260903_13_charge_line_cabinet_tariff.py`

**Interfaces:**
- Produces: `ConnectionChargeLine.cabinet_price_per_unit: Decimal | None`, `ConnectionChargeLine.cabinet_checked_at: datetime | None` — used by Task 3 and Task 5.

- [ ] **Step 1: Add the two columns to the model**

In `backend/app/models/entities.py`, inside `class ConnectionChargeLine` (after line 559, `is_active`, before `created_at` at line 560):

```python
    cabinet_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    cabinet_checked_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
```

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/20260903_13_charge_line_cabinet_tariff.py`:

```python
"""connection charge line cabinet tariff fields

Revision ID: 20260903_13
Revises: 20260307_12
Create Date: 2026-09-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_13"
down_revision = "20260307_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("connection_charge_lines") as batch_op:
        batch_op.add_column(sa.Column("cabinet_price_per_unit", sa.Numeric(12, 4), nullable=True))
        batch_op.add_column(sa.Column("cabinet_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("connection_charge_lines") as batch_op:
        batch_op.drop_column("cabinet_checked_at")
        batch_op.drop_column("cabinet_price_per_unit")
```

Confirm `20260307_12` is actually the current head before using it as `down_revision`:

Run: `docker exec um_api alembic heads`
Expected: `20260307_12 (head)`. If a different revision is head, use that instead.

- [ ] **Step 3: Apply the migration**

Run: `docker exec um_api alembic upgrade head`
Expected: output ends with `... -> 20260903_13, connection charge line cabinet tariff fields`.

- [ ] **Step 4: Verify the columns exist**

Run: `docker exec um_api python -c "from sqlalchemy import inspect; from app.db.session import engine; cols = [c['name'] for c in inspect(engine).get_columns('connection_charge_lines')]; print('cabinet_price_per_unit' in cols, 'cabinet_checked_at' in cols)"`
Expected: `True True`

- [ ] **Step 5: Run backend tests**

Run: `docker exec um_api pytest -q`
Expected: all pass (no behavior changed yet, only schema).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/entities.py backend/alembic/versions/20260903_13_charge_line_cabinet_tariff.py
git commit -m "feat(db): add cabinet_price_per_unit/cabinet_checked_at to connection_charge_lines"
```

---

## Task 3: Pure helper to record a cabinet tariff observation

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (add helper near `_upsert_service_charge_line_price`, i.e. after line 697)
- Create: `backend/tests/test_cabinet_tariff_observation.py`

**Interfaces:**
- Consumes: `ConnectionChargeLine` (Task 2's new fields).
- Produces: `_apply_cabinet_tariff_observation(current_line: ConnectionChargeLine, *, candidate_value: Decimal, checked_at: datetime) -> None` — used by Task 4.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cabinet_tariff_observation.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal

from app.models import ConnectionChargeLine
from app.workers.tariff_auto_check import _apply_cabinet_tariff_observation


def test_records_cabinet_value_without_touching_price_per_unit():
    line = ConnectionChargeLine(price_per_unit=Decimal("111.00"))
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(line, candidate_value=Decimal("120.5"), checked_at=checked_at)

    assert line.price_per_unit == Decimal("111.00")
    assert line.cabinet_price_per_unit == Decimal("120.5000")
    assert line.cabinet_checked_at == checked_at


def test_records_cabinet_value_even_when_lower_than_current_price():
    line = ConnectionChargeLine(price_per_unit=Decimal("200.00"))
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(line, candidate_value=Decimal("50"), checked_at=checked_at)

    assert line.price_per_unit == Decimal("200.00")
    assert line.cabinet_price_per_unit == Decimal("50.0000")
    assert line.cabinet_checked_at == checked_at
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec um_api pytest tests/test_cabinet_tariff_observation.py -v`
Expected: FAIL with `ImportError: cannot import name '_apply_cabinet_tariff_observation'`

- [ ] **Step 3: Implement the helper**

In `backend/app/workers/tariff_auto_check.py`, add after `_upsert_service_charge_line_price` (after line 697):

```python
def _apply_cabinet_tariff_observation(
    current_line: ConnectionChargeLine,
    *,
    candidate_value: Decimal,
    checked_at: datetime,
) -> None:
    current_line.cabinet_price_per_unit = candidate_value.quantize(Decimal("0.0001"))
    current_line.cabinet_checked_at = checked_at
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec um_api pytest tests/test_cabinet_tariff_observation.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_cabinet_tariff_observation.py
git commit -m "feat(tariff-worker): add pure helper to record cabinet tariff observations"
```

---

## Task 4: Wire the helper into `_run_atp0928`, remove the auto-write

Replaces the "Business rule: if DB total >= cabinet-derived total, keep unchanged" branch
(currently at `tariff_auto_check.py:964-1009`) with an unconditional cabinet-observation record,
and never calls `_upsert_service_charge_line_price` from this worker again.

> **Note:** this code moved since the plan was first written — an earlier same-session fix
> (commit `96e19ac`) replaced a hardcoded `residents_multiplier` with `current_line_quantity`
> (via `line_quantity(...)`, the real billing engine's quantity resolution) when computing
> `current_total`/`candidate_per_person`, because this apartment's "Вивіз сміття" line is a flat
> fixed charge, not priced per registered resident. The snippets below reflect the file as it
> exists now — use `current_line_quantity`, not `residents_multiplier`, and do not reintroduce
> the old hardcoded multiplier.

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py:964-1009`
- Modify: `frontend/src/features/tariffs/components/AutomationsTab.tsx:75` (status label)

**Interfaces:**
- Consumes: `_apply_cabinet_tariff_observation` (Task 3).

- [ ] **Step 1: Replace the auto-write branch**

In `backend/app/workers/tariff_auto_check.py`, replace lines 964-1009:

```python
            else:
                current_line_quantity = line_quantity(
                    apartment, current_line.quantity_source, Decimal(current_line.quantity_multiplier)
                )
                if current_line_quantity <= 0:
                    current_line_quantity = Decimal("1")
                current_per_person = Decimal(current_line.price_per_unit)
                current_total = (current_per_person * current_line_quantity).quantize(Decimal("0.01"))
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
                    candidate_per_person = (candidate_total_rounded / current_line_quantity).quantize(Decimal("0.0001"))
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
```

with:

```python
            else:
                current_line_quantity = line_quantity(
                    apartment, current_line.quantity_source, Decimal(current_line.quantity_multiplier)
                )
                if current_line_quantity <= 0:
                    current_line_quantity = Decimal("1")
                current_per_person = Decimal(current_line.price_per_unit)
                current_total = (current_per_person * current_line_quantity).quantize(Decimal("0.01"))
                candidate_total_rounded = _round_up_to_half(candidate_total_raw).quantize(Decimal("0.01"))
                setting.auto_check_last_value_raw = candidate_total_raw.quantize(Decimal("0.0001"))
                setting.auto_check_last_value_rounded = candidate_total_rounded

                if public_tariff_per_person is not None and accrued_month_value is not None:
                    persons_estimate = (accrued_month_value / public_tariff_per_person) if public_tariff_per_person > 0 else Decimal("0")
                    message_parts.append(
                        f"Оцінка к-сті прописаних: {persons_estimate.quantize(Decimal('0.01'))}"
                    )
                message_parts.append(f"К-сть прописаних: {residents_count}")

                candidate_per_person = (candidate_total_rounded / current_line_quantity).quantize(Decimal("0.0001"))
                _apply_cabinet_tariff_observation(current_line, candidate_value=candidate_per_person, checked_at=now_utc)
                has_update = True
                setting.auto_check_completed_for_period = True
                if current_total >= candidate_total_rounded:
                    message_parts.append(
                        f"Тариф з кабінету: {candidate_per_person} (мій {current_per_person.quantize(Decimal('0.0001'))} — без змін)"
                    )
                else:
                    message_parts.append(
                        f"Тариф з кабінету: {candidate_per_person} (мій {current_per_person.quantize(Decimal('0.0001'))} — перевірте вручну)"
                    )
```

Note this also drops the `_recalc_from_period` call in this branch: it existed only because the auto-write used to change `price_per_unit`, which no longer happens, so there is nothing to recalculate.

- [ ] **Step 2: Update the frontend status label to match the new meaning**

`auto_check_status == "updated"` no longer means "your price changed automatically" — it now means "cabinet value observed this run". In `frontend/src/features/tariffs/components/AutomationsTab.tsx`, replace line 75:

```ts
  if (status === "updated") return { label: "Тариф з кабінету отримано", tone: "ok" };
```

- [ ] **Step 3: Run backend tests**

Run: `docker exec um_api pytest -q`
Expected: all pass, including the two new tests from Task 3.

- [ ] **Step 4: Confirm `_upsert_service_charge_line_price` has no remaining auto-check callers**

Run: `grep -n "_upsert_service_charge_line_price" backend/app/workers/tariff_auto_check.py`
Expected: only the function's own definition (line ~640) — no call sites remain in `_run_atp0928`. (The Vodokanal call site at the current line ~1373 area is expected to remain — see "Out of scope".)

- [ ] **Step 5: Typecheck and lint frontend**

Run (from `frontend/`): `npm run typecheck && npm run lint -- --max-warnings=0`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py frontend/src/features/tariffs/components/AutomationsTab.tsx
git commit -m "fix(tariff-worker): stop ATP-0928 auto-writing price_per_unit, record cabinet value instead"
```

---

## Task 5: Expose cabinet tariff fields through the charge-line API

**Files:**
- Modify: `backend/app/schemas.py:183-200` (`ConnectionChargeLineOut`)
- Modify: `frontend/src/shared/api/types.ts:207-224` (`ConnectionChargeLineItem`)

**Interfaces:**
- Consumes: `ConnectionChargeLine.cabinet_price_per_unit` / `.cabinet_checked_at` (Task 2).
- Produces: `ConnectionChargeLineItem.cabinet_price_per_unit: string | null`, `ConnectionChargeLineItem.cabinet_checked_at: string | null` — used by Task 6.

- [ ] **Step 1: Add the fields to the backend schema**

In `backend/app/schemas.py`, inside `ConnectionChargeLineOut` (after line 199, `is_active: bool`, before `created_at: datetime`):

```python
    cabinet_price_per_unit: Decimal | None = None
    cabinet_checked_at: datetime | None = None
```

`ConnectionChargeLineOut` already has `model_config = ConfigDict(from_attributes=True)`, so these are picked up automatically from the ORM object — no changes needed in whatever endpoint builds this response.

- [ ] **Step 2: Add the fields to the frontend type**

In `frontend/src/shared/api/types.ts`, inside `ConnectionChargeLineItem` (after line 222, `is_active: boolean`, before `created_at: string`):

```ts
  cabinet_price_per_unit?: string | null;
  cabinet_checked_at?: string | null;
```

- [ ] **Step 3: Verify the API returns the new fields**

Run (replace `<apartment_id>` with a real id, e.g. the one used earlier in manual testing): `docker exec um_api python -c "
import json
from app.db.session import SessionLocal
from app.models import ConnectionChargeLine
db = SessionLocal()
line = db.query(ConnectionChargeLine).first()
print(line.cabinet_price_per_unit, line.cabinet_checked_at)
"`
Expected: `None None` (Task 4 hasn't run against real data yet, so this just confirms the columns read without error).

- [ ] **Step 4: Typecheck backend and frontend**

Run: `docker exec um_api python -m py_compile app/schemas.py`
Run (from `frontend/`): `npm run typecheck`
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py frontend/src/shared/api/types.ts
git commit -m "feat(api): expose cabinet_price_per_unit/cabinet_checked_at on connection charge lines"
```

---

## Task 6: Show the cabinet tariff on "Розрахунок" with freshness color and floor warning

**Files:**
- Create: `frontend/src/features/calculation/cabinet-tariff.ts`
- Create: `frontend/src/features/calculation/cabinet-tariff.test.ts`
- Modify: `frontend/src/features/calculation/components/CalculationTab.tsx:1-72` (props), `:355-370` (tariff cell)
- Modify: `frontend/src/features/layout/components/DashboardContent.tsx` (build the lookup map, pass new prop)

**Interfaces:**
- Consumes: `ConnectionChargeLineItem.cabinet_price_per_unit` / `.cabinet_checked_at` (Task 5), `serviceConnections: ApartmentServiceConnectionItem[]` (already in `DashboardContext`).
- Produces: `evaluateCabinetTariff(myPrice: number, cabinet: { price: number; checkedAt: string }, now?: Date): { freshness: "fresh" | "stale"; floorViolation: boolean; suggestedPrice: number }`.

- [ ] **Step 1: Write the failing test for the pure comparison helper**

Create `frontend/src/features/calculation/cabinet-tariff.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { evaluateCabinetTariff } from "./cabinet-tariff";

describe("evaluateCabinetTariff", () => {
  const now = new Date("2026-09-03T00:00:00Z");

  it("is fresh when checked 15 days ago or less", () => {
    const checkedAt = new Date("2026-08-19T00:00:00Z").toISOString(); // exactly 15 days
    const result = evaluateCabinetTariff(200, { price: 100, checkedAt }, now);
    expect(result.freshness).toBe("fresh");
  });

  it("is stale when checked more than 15 days ago", () => {
    const checkedAt = new Date("2026-08-18T00:00:00Z").toISOString(); // 16 days
    const result = evaluateCabinetTariff(200, { price: 100, checkedAt }, now);
    expect(result.freshness).toBe("stale");
  });

  it("flags a floor violation when my price is below cabinet * 1.10", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(109, { price: 100, checkedAt }, now);
    expect(result.floorViolation).toBe(true);
  });

  it("does not flag a floor violation when my price meets the 10% floor", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(110, { price: 100, checkedAt }, now);
    expect(result.floorViolation).toBe(false);
  });

  it("suggests cabinet price x 1.10, rounded up to the cent", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(185, { price: 74.9 * 3, checkedAt }, now);
    // 74.90 * 3 = 224.70; * 1.10 = 247.17 exactly, so ceil-to-cent must not push it to 247.18
    expect(result.suggestedPrice).toBe(247.17);
  });

  it("rounds a suggested price up when the floor lands mid-cent", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(50, { price: 33.33, checkedAt }, now);
    // 33.33 * 1.10 = 36.663 -> must round UP to 36.67, never down to 36.66
    expect(result.suggestedPrice).toBe(36.67);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/features/calculation/cabinet-tariff.test.ts`
Expected: FAIL — `cabinet-tariff.ts` does not exist yet.

- [ ] **Step 3: Implement the helper**

Create `frontend/src/features/calculation/cabinet-tariff.ts`:

```ts
export interface CabinetTariffInfo {
  price: number;
  checkedAt: string;
}

export interface CabinetTariffStatus {
  freshness: "fresh" | "stale";
  floorViolation: boolean;
  suggestedPrice: number;
}

const FRESHNESS_WINDOW_DAYS = 15;
const FLOOR_MULTIPLIER = 1.1;
const MS_PER_DAY = 1000 * 60 * 60 * 24;

// Guards against float noise (e.g. 224.7 * 1.1 === 247.17000000000002 in JS)
// spuriously pushing an exact cent value up to the next one.
function ceilToCents(value: number): number {
  return Math.ceil(value * 100 - 1e-9) / 100;
}

export function evaluateCabinetTariff(
  myPrice: number,
  cabinet: CabinetTariffInfo,
  now: Date = new Date(),
): CabinetTariffStatus {
  const ageDays = (now.getTime() - new Date(cabinet.checkedAt).getTime()) / MS_PER_DAY;
  return {
    freshness: ageDays <= FRESHNESS_WINDOW_DAYS ? "fresh" : "stale",
    floorViolation: myPrice < cabinet.price * FLOOR_MULTIPLIER,
    suggestedPrice: ceilToCents(cabinet.price * FLOOR_MULTIPLIER),
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/features/calculation/cabinet-tariff.test.ts`
Expected: 6 passed

- [ ] **Step 5: Commit the pure helper**

```bash
git add frontend/src/features/calculation/cabinet-tariff.ts frontend/src/features/calculation/cabinet-tariff.test.ts
git commit -m "feat(calculation): add pure cabinet-tariff freshness/floor helper"
```

- [ ] **Step 6: Build the line_id lookup map in `DashboardContent`**

In `frontend/src/features/layout/components/DashboardContent.tsx`, near the top of the component (alongside other `useMemo`/derived values pulled from `useDashboardContext()`), add:

```ts
const cabinetTariffByLineId = useMemo(() => {
  const map: Record<number, { price: number; checkedAt: string }> = {};
  for (const conn of serviceConnections) {
    for (const line of conn.charge_lines) {
      if (line.cabinet_price_per_unit != null && line.cabinet_checked_at) {
        map[line.id] = { price: Number(line.cabinet_price_per_unit), checkedAt: line.cabinet_checked_at };
      }
    }
  }
  return map;
}, [serviceConnections]);
```

(`serviceConnections` is already destructured from `useDashboardContext()` in this file — confirm the exact destructuring line and add `cabinetTariffByLineId` right after it if it isn't already in scope there.)

- [ ] **Step 7: Pass the map into `CalculationTab`**

In the same file, find the `<CalculationTab ... />` invocation and add the new prop:

```tsx
        cabinetTariffByLineId={cabinetTariffByLineId}
```

- [ ] **Step 8: Accept the new prop in `CalculationTab`**

In `frontend/src/features/calculation/components/CalculationTab.tsx`, add the import (near line 5):

```ts
import { evaluateCabinetTariff } from "../cabinet-tariff";
```

Add to `CalculationTabProps` (after line 71, `batchReadingSaving?: boolean;`):

```ts
  cabinetTariffByLineId: Record<number, { price: number; checkedAt: string }>;
```

Destructure it in the component's props (alongside `batchReadingSaving` in the destructuring list near line 93-116).

- [ ] **Step 9: Render the badge and warning in the tariff cell**

Replace the tariff `<td>` at lines 355-370:

```tsx
                  <td>
                    {e && editable ? (
                      <In
                        tip="Тариф"
                        help="Службове редагування ціни для цього рядка поточного місяця."
                        placeholder="Тариф"
                        onKeyDown={() => {}}
                        value={draft.unit_price ?? ""}
                        onChange={(x: InputEvt) =>
                          setDraft((s) => ({ ...s, unit_price: x.target.value }))
                        }
                      />
                    ) : (
                      money(r.unit_price)
                    )}
                    {r.line_id != null && cabinetTariffByLineId[r.line_id] ? (() => {
                      const cabinet = cabinetTariffByLineId[r.line_id];
                      const status = evaluateCabinetTariff(Number(r.unit_price), cabinet);
                      return (
                        <div className="helper">
                          <span className={`status-pill ${status.freshness === "fresh" ? "ok" : "error"}`}>
                            Кабінет: {money(cabinet.price)}
                          </span>
                          {status.floorViolation ? (
                            <button
                              type="button"
                              className="status-pill draft"
                              title="Мій тариф має бути не менше ніж на 10% вищим за тариф з кабінету. Клік — підставити рекомендоване значення."
                              onClick={() => {
                                if (!e) start(r);
                                setDraft((s) => ({ ...s, unit_price: String(status.suggestedPrice) }));
                              }}
                            >
                              ⚠ нижче на 10%+ · рекомендовано {money(status.suggestedPrice)}
                            </button>
                          ) : null}
                        </div>
                      );
                    })() : null}
                  </td>
```

The suggested-price pill is a real `<button>` (not a `<span>`, unlike the freshness pill) specifically so it's clickable: clicking it enters edit mode for this row (if not already editing) and pre-fills the "Тариф" input with the recommended value, so the admin only has to press "Зберегти" — or adjust it first.

- [ ] **Step 10: Typecheck, lint, and run the full frontend test suite**

Run (from `frontend/`): `npm run typecheck && npm run lint -- --max-warnings=0 && npm run test`
Expected: all clean, all tests pass.

- [ ] **Step 11: Rebuild frontend and verify no leakage into snapshots/statements**

Run: `grep -rn "cabinet_price_per_unit\|cabinet_checked_at" frontend/src/shared/api/types.ts`
Expected: only the two occurrences added in Task 5, inside `ConnectionChargeLineItem` — none inside `CalculationRow`, `BillingMonthSnapshotItem`, or `BillingStatementItem`.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/features/layout/components/DashboardContent.tsx frontend/src/features/calculation/components/CalculationTab.tsx
git commit -m "feat(calculation): show cabinet tariff badge with freshness color and floor warning"
```

---

## Task 7: Manual end-to-end verification against the live ATP-0928 automation

No automated test exercises the real HTTP scraping flow in `_run_atp0928` (the codebase has zero coverage of that path today, and building an HTTP-mocked integration harness from scratch is out of scope for this plan — Task 3's unit test covers the actual behavior change directly). Verify manually instead, against the apartment/automation used throughout this session (Івасюка 11 кв 195 → Автоматизації → Автотранспортне підприємство 0928 ВАТ).

- [ ] **Step 1: Record the current price before running**

Open "Розрахунок" for the apartment, note the current tariff value for the service tied to this automation ("Вивіз сміття").

- [ ] **Step 2: Run the automation**

In Автоматизації → Підключення до об'єктів, open the ATP-0928 card and click "Запустити зараз" (or "Запустити" from the collapsed card).

- [ ] **Step 3: Confirm price_per_unit did not change**

Reload "Розрахунок". Expected: the tariff value is identical to Step 1, regardless of what the cabinet returned.

- [ ] **Step 4: Confirm the cabinet badge appears with the right color**

On the same row, expected: a "Кабінет: X" badge is now visible. If `cabinet_checked_at` is today (it will be, since you just ran it), the badge should be green (`status-pill ok`).

- [ ] **Step 5: Confirm the floor warning and suggested price behave correctly**

As of this plan's writing, "Вивіз сміття" for this apartment is genuinely below the floor
(185.00 vs. a real cabinet total of ~225.00, city tariff raised to 74.90 грн/особа × 3 as of
01.09.2026 — see the design spec's context section), so the warning pill should already appear
with no need to artificially lower the price first. Expected: "⚠ нижче на 10%+ · рекомендовано
247.17" (74.90 × 3 × 1.10, rounded up to the cent — confirm the exact cabinet total shown in the
badge and recompute by hand if the live figure differs). Click the pill; expected: the row enters
edit mode with "Тариф" pre-filled to 247.17. Do not click "Зберегти" unless you (the user) have
actually decided to raise the tariff now — cancel/reset the edit afterward if this is just a
verification pass.

- [ ] **Step 6: Confirm the run log message reads correctly**

Open the automation's run history (however it's currently surfaced — via `fetchAutomationLogs`/run log UI) and confirm the message reads "Тариф з кабінету: X (...)" rather than the old "Тариф оновлено: X -> Y" wording.

- [ ] **Step 7: Report back**

Report the four observations above (Steps 3-6) so this task can be marked verified before starting the Vodokanal follow-up plan.

---

## Out of scope (explicit)

- **Vodokanal's own auto-write** (`_run_vodokanal`, tariff branch around the current line 1344) is left untouched in this plan. It will keep silently raising `price_per_unit` when the cabinet value is higher, exactly as today. Do not touch it here — per the user's explicit instruction, each provider is implemented and verified on its own, and Vodokanal comes only after ATP-0928 is confirmed working. The design spec (`docs/superpowers/specs/2026-09-03-cabinet-tariff-comparison-design.md`) already documents the equivalent change for Vodokanal for when that plan is written.
- A stale/incorrect `missingDataMessage` warning noticed during manual testing for a different reason than the plaintext password (e.g. an empty `cabinet_url`) is not separately investigated here — Task 1 fixes the specific password-related false-positive path; if a URL/login-related false positive is still observed during Task 7, report it rather than silently patching around it.
