# ГУК/Квартплата: оцінка тарифу + дорахунок недобору — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the admin get a usable Квартплата price for the current billing month (1–5 числа) even though the GUC/VisualService cabinet doesn't post the real accrual until after the 10th, by borrowing the previous month's confirmed cabinet value as a flagged estimate, surfacing a catch-up suggestion when an older estimate turns out to have undercharged the tenant, and adding a one-click "Оновити тарифи" trigger to the Розрахунок tab — all without ever auto-writing the real billed price.

**Architecture:** Backend: a new `cabinet_price_is_estimated` flag on `ConnectionChargeLine` lets the existing VisualService auto-check worker fall back to the previous month's cabinet value (instead of leaving the row empty) when the target month isn't posted yet; a new per-apartment `cabinet_markup_percent` field on `Apartment` replaces the hardcoded 10% floor multiplier. Frontend: the catch-up comparison (was the previous confirmed month undercharged?) is computed purely client-side from data already loaded for the Розрахунок tab — nothing new is persisted for it. A new button reuses the existing global `run-cycle` automation endpoint.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React + TypeScript + Vitest (frontend), pytest (backend tests).

## Global Constraints

- No automation may ever write `ConnectionChargeLine.price_per_unit` directly — only `cabinet_price_per_unit`, `cabinet_checked_at`, and (new) `cabinet_price_is_estimated`. The admin always applies price changes manually.
- `effective_from` on every `ConnectionChargeLine` is always the 1st of its month — any date-shifting logic can rely on this.
- Any new DB column must be registered so it runs on every backend startup (`run_startup_migrations()` in `backend/app/db/migrations.py`) — production has no separate migration step, and skipping this 500s the app on deploy (this happened for real with `cabinet_price_per_unit`, commits `cb1ec0f`→`5d0fbc4`).
- Touch only the GUC/VisualService provider's business logic (`tariff_auto_check.py`'s generic branch). ATP-0928 and Vodokanal are untouched except that they now read the markup percent from a field instead of a hardcoded constant.
- This codebase's testing convention for this worker: pure helper functions get unit tests (plain object construction, no DB session); DB-orchestration code and UI wiring are verified manually against dev/prod. Follow that convention — don't invent test infrastructure that doesn't exist elsewhere in the repo.

---

### Task 1: `ConnectionChargeLine.cabinet_price_is_estimated` flag

**Files:**
- Modify: `backend/app/models/entities.py:561` (after `cabinet_checked_at`)
- Modify: `backend/app/db/migrations.py:354` (inside `_ensure_connection_charge_lines_table`, after the `cabinet_checked_at` column block)
- Modify: `backend/app/workers/tariff_auto_check.py:597-604` (`_apply_cabinet_tariff_observation`)
- Test: `backend/tests/test_cabinet_tariff_observation.py`

**Interfaces:**
- Produces: `ConnectionChargeLine.cabinet_price_is_estimated: bool` (default `False`); `_apply_cabinet_tariff_observation(current_line, *, candidate_value: Decimal, checked_at: datetime, is_estimated: bool = False) -> None`.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `backend/tests/test_cabinet_tariff_observation.py` with:

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
    assert line.cabinet_price_is_estimated is False


def test_records_cabinet_value_even_when_lower_than_current_price():
    line = ConnectionChargeLine(price_per_unit=Decimal("200.00"))
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(line, candidate_value=Decimal("50"), checked_at=checked_at)

    assert line.price_per_unit == Decimal("200.00")
    assert line.cabinet_price_per_unit == Decimal("50.0000")
    assert line.cabinet_checked_at == checked_at
    assert line.cabinet_price_is_estimated is False


def test_records_estimated_value_and_flags_it():
    line = ConnectionChargeLine(price_per_unit=Decimal("200.00"))
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(
        line, candidate_value=Decimal("120.5"), checked_at=checked_at, is_estimated=True
    )

    assert line.cabinet_price_per_unit == Decimal("120.5000")
    assert line.cabinet_price_is_estimated is True


def test_real_observation_clears_previous_estimated_flag():
    line = ConnectionChargeLine(price_per_unit=Decimal("200.00"))
    line.cabinet_price_is_estimated = True
    checked_at = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    _apply_cabinet_tariff_observation(line, candidate_value=Decimal("130.0"), checked_at=checked_at)

    assert line.cabinet_price_per_unit == Decimal("130.0000")
    assert line.cabinet_price_is_estimated is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.\.venv\Scripts\python -m pytest tests/test_cabinet_tariff_observation.py -v`
Expected: FAIL — `AttributeError`/`TypeError` because `cabinet_price_is_estimated` and the `is_estimated` parameter don't exist yet.

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/entities.py`, in `class ConnectionChargeLine`, right after the existing line:
```python
    cabinet_checked_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
```
add:
```python
    cabinet_price_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Register the migration**

In `backend/app/db/migrations.py`, inside `_ensure_connection_charge_lines_table`, right after the existing block:
```python
    if not _has_column(db, "connection_charge_lines", "cabinet_checked_at"):
        db.execute(text("ALTER TABLE connection_charge_lines ADD COLUMN cabinet_checked_at DATETIME NULL"))
        db.commit()
```
add:
```python
    if not _has_column(db, "connection_charge_lines", "cabinet_price_is_estimated"):
        db.execute(
            text(
                "ALTER TABLE connection_charge_lines ADD COLUMN cabinet_price_is_estimated "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        db.commit()
```

- [ ] **Step 5: Update `_apply_cabinet_tariff_observation`**

In `backend/app/workers/tariff_auto_check.py`, replace:
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
with:
```python
def _apply_cabinet_tariff_observation(
    current_line: ConnectionChargeLine,
    *,
    candidate_value: Decimal,
    checked_at: datetime,
    is_estimated: bool = False,
) -> None:
    current_line.cabinet_price_per_unit = candidate_value.quantize(Decimal("0.0001"))
    current_line.cabinet_checked_at = checked_at
    current_line.cabinet_price_is_estimated = is_estimated
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.\.venv\Scripts\python -m pytest tests/test_cabinet_tariff_observation.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/entities.py backend/app/db/migrations.py backend/app/workers/tariff_auto_check.py backend/tests/test_cabinet_tariff_observation.py
git commit -m "feat(tariff-worker): add cabinet_price_is_estimated flag to ConnectionChargeLine"
```

---

### Task 2: Borrow the previous month's cabinet value when the target month is empty

**Files:**
- Modify: `backend/app/workers/tariff_auto_check.py` (new helper near `_apply_cabinet_tariff_observation`, wiring in `_run_single_setting`'s `waiting` branch at ~line 1665)
- Test: `backend/tests/test_cabinet_estimate_from_previous_month.py` (new)

**Interfaces:**
- Consumes: `ConnectionChargeLine.cabinet_price_per_unit` (Task 1), `_apply_cabinet_tariff_observation(..., is_estimated=True)` (Task 1), `_service_charge_line_for_period(db, *, apartment_id, service_name, period_start, connection_id=None, service_catalog_id=None) -> ConnectionChargeLine | None` (existing, `tariff_auto_check.py:550`), `_prev_month(y, m) -> tuple[int, int]` and `_month_start(year, month) -> datetime` (existing).
- Produces: `_borrow_estimate_from_previous_line(previous_line: ConnectionChargeLine | None) -> Decimal | None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cabinet_estimate_from_previous_month.py`:

```python
from decimal import Decimal

from app.models import ConnectionChargeLine
from app.workers.tariff_auto_check import _borrow_estimate_from_previous_line


def test_returns_none_when_no_previous_line():
    assert _borrow_estimate_from_previous_line(None) is None


def test_returns_none_when_previous_line_has_no_cabinet_value():
    previous_line = ConnectionChargeLine(price_per_unit=Decimal("100.00"))
    assert _borrow_estimate_from_previous_line(previous_line) is None


def test_borrows_previous_line_cabinet_value():
    previous_line = ConnectionChargeLine(price_per_unit=Decimal("100.00"))
    previous_line.cabinet_price_per_unit = Decimal("334.4950")
    assert _borrow_estimate_from_previous_line(previous_line) == Decimal("334.4950")


def test_borrows_even_when_previous_line_was_itself_an_estimate():
    previous_line = ConnectionChargeLine(price_per_unit=Decimal("100.00"))
    previous_line.cabinet_price_per_unit = Decimal("300.0000")
    previous_line.cabinet_price_is_estimated = True
    assert _borrow_estimate_from_previous_line(previous_line) == Decimal("300.0000")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python -m pytest tests/test_cabinet_estimate_from_previous_month.py -v`
Expected: FAIL — `ImportError: cannot import name '_borrow_estimate_from_previous_line'`

- [ ] **Step 3: Add the pure helper**

In `backend/app/workers/tariff_auto_check.py`, right after `_apply_cabinet_tariff_observation`, add:

```python
def _borrow_estimate_from_previous_line(previous_line: ConnectionChargeLine | None) -> Decimal | None:
    if previous_line is None:
        return None
    return previous_line.cabinet_price_per_unit
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python -m pytest tests/test_cabinet_estimate_from_previous_month.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Wire the fallback into the `waiting` branch**

In `backend/app/workers/tariff_auto_check.py`, inside `_run_single_setting`, replace:
```python
    if check.status == "waiting":
        setting.auto_check_status = "waiting"
        return
```
with:
```python
    if check.status == "waiting":
        setting.auto_check_status = "waiting"
        previous_year, previous_month = _prev_month(target_year, target_month)
        previous_period_start = _month_start(previous_year, previous_month).date()
        previous_line = _service_charge_line_for_period(
            db,
            apartment_id=setting.apartment_id,
            service_name=setting.service_name,
            period_start=previous_period_start,
            connection_id=setting.connection_id,
            service_catalog_id=setting.service_catalog_id,
        )
        estimate = _borrow_estimate_from_previous_line(previous_line)
        if estimate is not None:
            period_start = _month_start(target_year, target_month).date()
            current_line = _service_charge_line_for_period(
                db,
                apartment_id=setting.apartment_id,
                service_name=setting.service_name,
                period_start=period_start,
                connection_id=setting.connection_id,
                service_catalog_id=setting.service_catalog_id,
            )
            if current_line is not None:
                _apply_cabinet_tariff_observation(
                    current_line,
                    candidate_value=estimate,
                    checked_at=now_utc,
                    is_estimated=True,
                )
                setting.auto_check_message = (
                    f"Кабінет ще не провів {target_month:02d}.{target_year}; "
                    "підставлено оцінку з попереднього місяця"
                )[:255]
        return
```

This is DB-orchestration code (loads live `ConnectionChargeLine` rows through a real session) — consistent with the rest of this function, it has no dedicated automated test. Verify it manually in Step 6.

- [ ] **Step 6: Manual verification**

Against the dev container (or prod, per the established workflow for this worker): with the current month's GUC accrual still unposted, trigger the automation cycle (`POST /admin/automations/run-cycle`) and confirm in the DB / via `/admin/apartments/{id}/service-connections` that the current month's `ConnectionChargeLine.cabinet_price_per_unit` now equals the previous month's, with `cabinet_price_is_estimated = true`. Then, once GUC posts the real value on a later run, confirm it overwrites the estimate and `cabinet_price_is_estimated` flips back to `false`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workers/tariff_auto_check.py backend/tests/test_cabinet_estimate_from_previous_month.py
git commit -m "feat(tariff-worker): borrow previous month's cabinet price when GUC hasn't posted yet"
```

---

### Task 3: `Apartment.cabinet_markup_percent` field (per-object markup)

**Files:**
- Modify: `backend/app/models/entities.py:142` (after `timezone`, in `class Apartment`)
- Modify: `backend/app/db/migrations.py:47-60` (`_ensure_apartment_profile_columns` dict)
- Modify: `backend/app/schemas.py` — `ApartmentCreate` (line 46), `ApartmentOut` (line 73), `ApartmentDetailOut` (line 903)
- Modify: `backend/app/api/admin/_shared.py:262` (`_apply_apartment_profile`)
- Modify: `backend/app/api/admin/dashboard.py:127` (`ApartmentDetailOut` builder)

**Interfaces:**
- Produces: `Apartment.cabinet_markup_percent: Decimal | None`; the same field name flows through `ApartmentCreate`, `ApartmentOut`, `ApartmentDetailOut`.

- [ ] **Step 1: Add the column to the model**

In `backend/app/models/entities.py`, in `class Apartment`, right after:
```python
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
```
add:
```python
    cabinet_markup_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
```

- [ ] **Step 2: Register the migration**

In `backend/app/db/migrations.py`, in `_ensure_apartment_profile_columns`, add a new entry to the `apartment_columns` dict (order doesn't matter, place it after `"room_count"` for readability):
```python
        "cabinet_markup_percent": "ALTER TABLE apartments ADD COLUMN cabinet_markup_percent NUMERIC(5, 2) NULL",
```

- [ ] **Step 3: Add the field to the schemas**

In `backend/app/schemas.py`:

In `class ApartmentCreate`, right after:
```python
    timezone: str = Field(default="Europe/Kyiv", min_length=3, max_length=64)
```
add:
```python
    cabinet_markup_percent: Decimal | None = Field(default=None, ge=0, le=100)
```

In `class ApartmentOut`, right after:
```python
    timezone: str = "Europe/Kyiv"
```
add:
```python
    cabinet_markup_percent: Decimal | None = None
```

In `class ApartmentDetailOut`, right after:
```python
    timezone: str = "Europe/Kyiv"
```
add:
```python
    cabinet_markup_percent: Decimal | None = None
```

- [ ] **Step 4: Persist it on create/update**

In `backend/app/api/admin/_shared.py`, in `_apply_apartment_profile`, right after:
```python
    apartment.timezone = payload.timezone or "Europe/Kyiv"
```
add:
```python
    apartment.cabinet_markup_percent = payload.cabinet_markup_percent
```

- [ ] **Step 5: Serialize it into `ApartmentDetailOut`**

In `backend/app/api/admin/dashboard.py`, in the `ApartmentDetailOut(...)` construction, right after:
```python
        timezone=apartment.timezone or "Europe/Kyiv",
```
add:
```python
        cabinet_markup_percent=apartment.cabinet_markup_percent,
```

- [ ] **Step 6: Manual verification**

Start the backend, `PUT /admin/apartments/{id}` with `cabinet_markup_percent: 10`, then `GET /admin/apartments` and `GET` the apartment's dashboard detail — confirm `10.00` (or `"10.00"`) comes back in both. Confirm an apartment that never had the field set returns `null`, not an error.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/entities.py backend/app/db/migrations.py backend/app/schemas.py backend/app/api/admin/_shared.py backend/app/api/admin/dashboard.py
git commit -m "feat(apartments): add per-object cabinet_markup_percent field"
```

---

### Task 4: Configurable markup + catch-up pure functions in `cabinet-tariff.ts`

**Files:**
- Modify: `frontend/src/features/calculation/cabinet-tariff.ts`
- Modify: `frontend/src/features/calculation/cabinet-tariff.test.ts`

**Interfaces:**
- Produces: `evaluateCabinetTariff(myPrice: number, cabinet: CabinetTariffInfo, markupPercent: number, now?: Date) -> CabinetTariffStatus` (markup is now a required parameter, no more hardcoded `1.1`); `ChargeLineForCatchUp` interface; `CatchUpSuggestion { sourcePeriod: string; amount: number }`; `computeCatchUpSuggestion(targetLine: ChargeLineForCatchUp, connectionLines: ChargeLineForCatchUp[]) -> CatchUpSuggestion | null`.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `frontend/src/features/calculation/cabinet-tariff.test.ts` with:

```ts
import { describe, expect, it } from "vitest";
import { computeCatchUpSuggestion, evaluateCabinetTariff } from "./cabinet-tariff";
import type { ChargeLineForCatchUp } from "./cabinet-tariff";

describe("evaluateCabinetTariff", () => {
  const now = new Date("2026-09-03T00:00:00Z");

  it("is fresh when checked 15 days ago or less", () => {
    const checkedAt = new Date("2026-08-19T00:00:00Z").toISOString(); // exactly 15 days
    const result = evaluateCabinetTariff(200, { price: 100, checkedAt }, 10, now);
    expect(result.freshness).toBe("fresh");
  });

  it("is stale when checked more than 15 days ago", () => {
    const checkedAt = new Date("2026-08-18T00:00:00Z").toISOString(); // 16 days
    const result = evaluateCabinetTariff(200, { price: 100, checkedAt }, 10, now);
    expect(result.freshness).toBe("stale");
  });

  it("flags a floor violation when my price is below cabinet * (1 + markup%)", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(109, { price: 100, checkedAt }, 10, now);
    expect(result.floorViolation).toBe(true);
  });

  it("does not flag a floor violation when my price meets the floor", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(110, { price: 100, checkedAt }, 10, now);
    expect(result.floorViolation).toBe(false);
  });

  it("suggests cabinet price x (1 + markup%), rounded up to the cent", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(185, { price: 74.9 * 3, checkedAt }, 10, now);
    // 74.90 * 3 = 224.70; * 1.10 = 247.17 exactly, so ceil-to-cent must not push it to 247.18
    expect(result.suggestedPrice).toBe(247.17);
  });

  it("rounds a suggested price up when the floor lands mid-cent", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(50, { price: 33.33, checkedAt }, 10, now);
    // 33.33 * 1.10 = 36.663 -> must round UP to 36.67, never down to 36.66
    expect(result.suggestedPrice).toBe(36.67);
  });

  it("never flags a floor violation when markup is 0%", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(100, { price: 100, checkedAt }, 0, now);
    expect(result.floorViolation).toBe(false);
    expect(result.suggestedPrice).toBe(100);
  });

  it("applies a custom markup percent, e.g. 5%", () => {
    const checkedAt = now.toISOString();
    const result = evaluateCabinetTariff(104, { price: 100, checkedAt }, 5, now);
    expect(result.floorViolation).toBe(true);
    expect(result.suggestedPrice).toBe(105);
  });
});

describe("computeCatchUpSuggestion", () => {
  function line(overrides: Partial<ChargeLineForCatchUp>): ChargeLineForCatchUp {
    return {
      id: 1,
      effective_from: "2026-08-01",
      price_per_unit: "300.00",
      cabinet_price_per_unit: null,
      cabinet_price_is_estimated: false,
      ...overrides,
    };
  }

  it("returns null when the target line is not estimated", () => {
    const target = line({ id: 1, effective_from: "2026-08-01", cabinet_price_is_estimated: false });
    expect(computeCatchUpSuggestion(target, [target])).toBeNull();
  });

  it("returns null when there is no line two months back", () => {
    const target = line({ id: 1, effective_from: "2026-08-01", cabinet_price_is_estimated: true });
    expect(computeCatchUpSuggestion(target, [target])).toBeNull();
  });

  it("returns null when the T-2 line is itself an estimate", () => {
    const target = line({ id: 1, effective_from: "2026-08-01", cabinet_price_is_estimated: true });
    const sourceLine = line({
      id: 2,
      effective_from: "2026-06-01",
      price_per_unit: "300.00",
      cabinet_price_per_unit: "334.50",
      cabinet_price_is_estimated: true,
    });
    expect(computeCatchUpSuggestion(target, [target, sourceLine])).toBeNull();
  });

  it("returns null when the T-2 line has no confirmed cabinet value", () => {
    const target = line({ id: 1, effective_from: "2026-08-01", cabinet_price_is_estimated: true });
    const sourceLine = line({
      id: 2,
      effective_from: "2026-06-01",
      price_per_unit: "300.00",
      cabinet_price_per_unit: null,
      cabinet_price_is_estimated: false,
    });
    expect(computeCatchUpSuggestion(target, [target, sourceLine])).toBeNull();
  });

  it("returns null when we did not undercharge the T-2 month", () => {
    const target = line({ id: 1, effective_from: "2026-08-01", cabinet_price_is_estimated: true });
    const sourceLine = line({
      id: 2,
      effective_from: "2026-06-01",
      price_per_unit: "340.00",
      cabinet_price_per_unit: "334.50",
      cabinet_price_is_estimated: false,
    });
    expect(computeCatchUpSuggestion(target, [target, sourceLine])).toBeNull();
  });

  it("suggests the shortfall when the T-2 month's confirmed cost came in higher than billed", () => {
    const target = line({ id: 1, effective_from: "2026-08-01", cabinet_price_is_estimated: true });
    const sourceLine = line({
      id: 2,
      effective_from: "2026-06-01",
      price_per_unit: "300.00",
      cabinet_price_per_unit: "334.50",
      cabinet_price_is_estimated: false,
    });
    const result = computeCatchUpSuggestion(target, [target, sourceLine]);
    expect(result).toEqual({ sourcePeriod: "2026-06", amount: 34.5 });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/features/calculation/cabinet-tariff.test.ts`
Expected: FAIL — `evaluateCabinetTariff` called with the wrong arity, `computeCatchUpSuggestion` doesn't exist.

- [ ] **Step 3: Replace `cabinet-tariff.ts` with the updated implementation**

Replace the full contents of `frontend/src/features/calculation/cabinet-tariff.ts` with:

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
const MS_PER_DAY = 1000 * 60 * 60 * 24;

// Guards against float noise (e.g. 224.7 * 1.1 === 247.17000000000002 in JS)
// spuriously pushing an exact cent value up to the next one.
function ceilToCents(value: number): number {
  return Math.ceil(value * 100 - 1e-9) / 100;
}

// Same float-noise guard as ceilToCents: 100 * 1.1 === 110.00000000000001 in JS,
// which would otherwise flag an exact floor match (110 vs 110) as a violation.
const FLOAT_EPSILON = 1e-9;

export function evaluateCabinetTariff(
  myPrice: number,
  cabinet: CabinetTariffInfo,
  markupPercent: number,
  now: Date = new Date(),
): CabinetTariffStatus {
  const ageDays = (now.getTime() - new Date(cabinet.checkedAt).getTime()) / MS_PER_DAY;
  const multiplier = 1 + markupPercent / 100;
  return {
    freshness: ageDays <= FRESHNESS_WINDOW_DAYS ? "fresh" : "stale",
    floorViolation: myPrice < cabinet.price * multiplier - FLOAT_EPSILON,
    suggestedPrice: ceilToCents(cabinet.price * multiplier),
  };
}

export interface ChargeLineForCatchUp {
  id: number;
  effective_from: string;
  price_per_unit: string;
  cabinet_price_per_unit?: string | null;
  cabinet_price_is_estimated?: boolean | null;
}

export interface CatchUpSuggestion {
  sourcePeriod: string;
  amount: number;
}

function shiftMonthsBack(isoDate: string, months: number): string {
  const [year, month] = isoDate.slice(0, 7).split("-").map(Number);
  const totalMonths = year * 12 + (month - 1) - months;
  const shiftedYear = Math.floor(totalMonths / 12);
  const shiftedMonth = (totalMonths % 12) + 1;
  return `${String(shiftedYear).padStart(4, "0")}-${String(shiftedMonth).padStart(2, "0")}-01`;
}

// Purely derived, nothing persisted: if `targetLine` is an estimate (borrowed
// from the previous month because the cabinet hadn't posted yet), check
// whether the line two months earlier turned out to have been undercharged
// once its real cabinet value was confirmed, and suggest adding that shortfall.
export function computeCatchUpSuggestion(
  targetLine: ChargeLineForCatchUp,
  connectionLines: ChargeLineForCatchUp[],
): CatchUpSuggestion | null {
  if (!targetLine.cabinet_price_is_estimated) return null;
  const sourceDate = shiftMonthsBack(targetLine.effective_from, 2);
  const sourceLine = connectionLines.find((candidate) => candidate.effective_from.slice(0, 10) === sourceDate);
  if (!sourceLine || sourceLine.cabinet_price_is_estimated) return null;
  if (sourceLine.cabinet_price_per_unit == null) return null;
  const shortfall = Number(sourceLine.cabinet_price_per_unit) - Number(sourceLine.price_per_unit);
  if (shortfall <= 0) return null;
  return { sourcePeriod: sourceDate.slice(0, 7), amount: shortfall };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/features/calculation/cabinet-tariff.test.ts`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/calculation/cabinet-tariff.ts frontend/src/features/calculation/cabinet-tariff.test.ts
git commit -m "feat(calculation): make floor markup configurable, add catch-up suggestion helper"
```

Note: this leaves the one call site in `CalculationTab.tsx` (`evaluateCabinetTariff(Number(r.unit_price), cabinet)`) passing the wrong number of arguments — it's fixed in Task 6, which rewrites that whole block anyway. The frontend won't typecheck between this task and Task 6; that's expected for this plan's ordering.

---

### Task 5: Apartment profile form — markup % field

**Files:**
- Modify: `frontend/src/shared/api/types.ts:345` (`ApartmentProfileForm`)
- Modify: `frontend/src/features/dashboard/hooks/use-dashboard-state-sync.ts:70` (`setAp({...})`)
- Modify: `frontend/src/features/properties/hooks/use-property-actions.ts:22` (`apartmentPayload`)
- Modify: `frontend/src/features/properties/components/PropertyDrawer.tsx:192` (`resetPropertyForm`) and `:384` (form JSX)
- Modify: `frontend/src/features/properties/components/PropertyTab.tsx:424` (form JSX)

**Interfaces:**
- Consumes: `Apartment.cabinet_markup_percent` (Task 3, arrives on `detail`/`d` as `cabinet_markup_percent`).
- Produces: `ApartmentProfileForm.cabinet_markup_percent: string`.

- [ ] **Step 1: Add the field to the form type**

In `frontend/src/shared/api/types.ts`, in `interface ApartmentProfileForm`, right after:
```ts
  room_count: string;
```
add:
```ts
  cabinet_markup_percent: string;
```

- [ ] **Step 2: Populate it when loading an apartment**

In `frontend/src/features/dashboard/hooks/use-dashboard-state-sync.ts`, in the `setAp({...})` call, right after:
```ts
      room_count: d.room_count !== null && d.room_count !== undefined ? String(d.room_count) : "",
```
add:
```ts
      cabinet_markup_percent:
        d.cabinet_markup_percent !== null && d.cabinet_markup_percent !== undefined
          ? String(d.cabinet_markup_percent)
          : "",
```

- [ ] **Step 3: Include it when saving**

In `frontend/src/features/properties/hooks/use-property-actions.ts`, in `apartmentPayload`, right after:
```ts
    room_count: ap.room_count !== "" ? Number(ap.room_count) : null,
```
add:
```ts
    cabinet_markup_percent: ap.cabinet_markup_percent !== "" ? Number(ap.cabinet_markup_percent) : null,
```

- [ ] **Step 4: Reset it in the drawer's blank-form default**

In `frontend/src/features/properties/components/PropertyDrawer.tsx`, in `resetPropertyForm`, right after:
```ts
      room_count: "",
```
add:
```ts
      cabinet_markup_percent: "",
```

- [ ] **Step 5: Render the input in both property forms**

In `frontend/src/features/properties/components/PropertyDrawer.tsx`, right after the "К-сть кімнат" `<In .../>` block (the one with `value={ap.room_count}`), add:
```tsx
            <In
              label="Націнка над тарифом з кабінету, %"
              tip="Мінімальний відсоток, на який моя ціна має перевищувати тариф з кабінету постачальника"
              type="number"
              min="0"
              max="100"
              step="0.01"
              placeholder="10"
              value={ap.cabinet_markup_percent}
              onChange={(e) => setAp((s) => ({ ...s, cabinet_markup_percent: e.target.value }))}
            />
```

In `frontend/src/features/properties/components/PropertyTab.tsx`, add the identical block right after its own "К-сть кімнат" `<In .../>` block (the one with `value={ap.room_count}`).

- [ ] **Step 6: Manual verification**

Run the app (`npm run dev` in `frontend/`, backend running), open an apartment's property form (both the drawer and the Property tab), set "Націнка над тарифом з кабінету, %" to `10`, save, reload the page, and confirm the value is still `10` in both forms.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/shared/api/types.ts frontend/src/features/dashboard/hooks/use-dashboard-state-sync.ts frontend/src/features/properties/hooks/use-property-actions.ts frontend/src/features/properties/components/PropertyDrawer.tsx frontend/src/features/properties/components/PropertyTab.tsx
git commit -m "feat(properties): add per-object cabinet markup percent field to property forms"
```

---

### Task 6: Wire estimated/catch-up badges into the Розрахунок tab

**Files:**
- Modify: `frontend/src/shared/api/types.ts:224` (`ConnectionChargeLineItem`)
- Modify: `frontend/src/features/dashboard/hooks/use-dashboard-data.ts:26` (`DetailBundle.d`)
- Modify: `frontend/src/features/layout/components/DashboardContent.tsx:1`, `:139-149` (imports, `cabinetTariffByLineId`)
- Modify: `frontend/src/features/calculation/components/CalculationTab.tsx:6`, `:16-22`, `:73`, `:373-396` (imports, `DetailLike`, prop type, badge block)

**Interfaces:**
- Consumes: `ConnectionChargeLine.cabinet_price_is_estimated` (Task 1, via API), `Apartment.cabinet_markup_percent` (Task 3, via API), `evaluateCabinetTariff`/`computeCatchUpSuggestion`/`CatchUpSuggestion` (Task 4).

- [ ] **Step 1: Expose `cabinet_price_is_estimated` on the frontend type**

In `frontend/src/shared/api/types.ts`, in `interface ConnectionChargeLineItem`, right after:
```ts
  cabinet_checked_at?: string | null;
```
add:
```ts
  cabinet_price_is_estimated?: boolean | null;
```

- [ ] **Step 2: Expose `cabinet_markup_percent` on the detail-bundle type**

In `frontend/src/features/dashboard/hooks/use-dashboard-data.ts`, in `type DetailBundle`'s `d` shape, right after:
```ts
    utility_balance: Record<string, string>;
```
add:
```ts
    cabinet_markup_percent?: string | number | null;
```

- [ ] **Step 3: Compute `isEstimated`/`catchUp` in `DashboardContent.tsx`**

At the top of `frontend/src/features/layout/components/DashboardContent.tsx`, change:
```ts
import { CalculationTab } from "@/features/calculation/components/CalculationTab";
```
to:
```ts
import { CalculationTab } from "@/features/calculation/components/CalculationTab";
import { computeCatchUpSuggestion, type CatchUpSuggestion } from "@/features/calculation/cabinet-tariff";
```

Replace:
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
with:
```ts
  const cabinetTariffByLineId = useMemo(() => {
    const map: Record<
      number,
      { price: number; checkedAt: string; isEstimated: boolean; catchUp: CatchUpSuggestion | null }
    > = {};
    for (const conn of serviceConnections) {
      for (const line of conn.charge_lines) {
        if (line.cabinet_price_per_unit != null && line.cabinet_checked_at) {
          map[line.id] = {
            price: Number(line.cabinet_price_per_unit),
            checkedAt: line.cabinet_checked_at,
            isEstimated: Boolean(line.cabinet_price_is_estimated),
            catchUp: computeCatchUpSuggestion(line, conn.charge_lines),
          };
        }
      }
    }
    return map;
  }, [serviceConnections]);
```

- [ ] **Step 4: Update `CalculationTab.tsx`'s types and imports**

Change:
```ts
import { evaluateCabinetTariff } from "../cabinet-tariff";
```
to:
```ts
import { evaluateCabinetTariff, type CatchUpSuggestion } from "../cabinet-tariff";
```

In `interface DetailLike`, right after:
```ts
  utility_balance: {
    previous_month_debt: string;
    current_balance: string;
  };
```
add:
```ts
  cabinet_markup_percent?: string | number | null;
```

Change:
```ts
  cabinetTariffByLineId: Record<number, { price: number; checkedAt: string }>;
```
to:
```ts
  cabinetTariffByLineId: Record<
    number,
    { price: number; checkedAt: string; isEstimated: boolean; catchUp: CatchUpSuggestion | null }
  >;
```

- [ ] **Step 5: Rewrite the badge block**

Replace the block starting at `{r.line_id != null && cabinetTariffByLineId[r.line_id] ? (() => {` through its closing `})() : null}` with:

```tsx
                    {r.line_id != null && cabinetTariffByLineId[r.line_id] ? (() => {
                      const cabinet = cabinetTariffByLineId[r.line_id];
                      const markupPercent = Number(detail.cabinet_markup_percent) || 0;
                      const effectivePrice = cabinet.price + (cabinet.catchUp?.amount ?? 0);
                      const status = evaluateCabinetTariff(
                        Number(r.unit_price),
                        { price: effectivePrice, checkedAt: cabinet.checkedAt },
                        markupPercent,
                      );
                      return (
                        <div className="helper">
                          <span
                            className={`status-pill ${
                              cabinet.isEstimated ? "draft" : status.freshness === "fresh" ? "ok" : "error"
                            }`}
                          >
                            {cabinet.isEstimated ? "Оцінка з попер. місяця: " : "Кабінет: "}
                            {money(cabinet.price)}
                          </span>
                          {cabinet.catchUp ? (
                            <div className="helper">
                              З {cabinet.catchUp.sourcePeriod} фактично вийшло на {money(cabinet.catchUp.amount)} грн
                              більше — рекомендовано додати.
                            </div>
                          ) : null}
                          {status.floorViolation ? (
                            <button
                              type="button"
                              className="status-pill draft"
                              title="Мій тариф має бути не нижчим за тариф з кабінету плюс налаштована націнка. Клік — підставити рекомендоване значення."
                              onClick={() => {
                                if (!e) start(r);
                                setDraft((s) => ({ ...s, unit_price: String(status.suggestedPrice) }));
                              }}
                            >
                              ⚠ нижче норми · рекомендовано {money(status.suggestedPrice)}
                            </button>
                          ) : null}
                        </div>
                      );
                    })() : null}
```

- [ ] **Step 6: Typecheck**

Run (from `frontend/`): `npm run typecheck`
Expected: no errors involving `CalculationTab.tsx`, `DashboardContent.tsx`, `cabinet-tariff.ts`, or the modified type files.

- [ ] **Step 7: Manual verification**

With Task 2's fallback active on a real apartment/GUC connection (or by manually setting `cabinet_price_is_estimated = true` on a test row in the dev DB): open the Розрахунок tab, confirm the badge reads "Оцінка з попер. місяця: X" instead of "Кабінет: X", and that when a T-2 shortfall exists the catch-up note renders with the right amount and period, and clicking the recommendation fills the tariff input.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/shared/api/types.ts frontend/src/features/dashboard/hooks/use-dashboard-data.ts frontend/src/features/layout/components/DashboardContent.tsx frontend/src/features/calculation/components/CalculationTab.tsx
git commit -m "feat(calculation): show estimated-cabinet-price badge and catch-up suggestion"
```

---

### Task 7: "Оновити тарифи" button on the Розрахунок tab

**Files:**
- Modify: `frontend/src/features/calculation/components/CalculationTab.tsx:59` (props interface), `:106` (destructuring), `:220` (local state), `:423` (button JSX)
- Modify: `frontend/src/features/layout/components/DashboardContent.tsx:366` (prop passthrough)

**Interfaces:**
- Consumes: `runAutomationCycle: () => Promise<void>` (already implemented, `frontend/src/features/admin/AdminApp.tsx:820`, already threaded into `DashboardContent.tsx` at line 94 and used by `AutomationsTab`).

- [ ] **Step 1: Add the prop to `CalculationTab`**

In `frontend/src/features/calculation/components/CalculationTab.tsx`, in `interface CalculationTabProps`, right after:
```ts
  confirmMonth: () => Promise<void>;
```
add:
```ts
  runAutomationCycle: () => Promise<void>;
```

In the destructured props, right after:
```ts
  confirmMonth,
```
add:
```ts
  runAutomationCycle,
```

- [ ] **Step 2: Add local loading state**

Right after:
```ts
  const [reopenSaving, setReopenSaving] = useState(false);
```
add:
```ts
  const [updatingTariffs, setUpdatingTariffs] = useState(false);
```

- [ ] **Step 3: Render the button**

Right after:
```tsx
          <button onClick={recalcMonth}>Заповнити місяць послугами</button>
```
add:
```tsx
          <button
            className="secondary"
            disabled={updatingTariffs}
            onClick={async () => {
              setUpdatingTariffs(true);
              try {
                await runAutomationCycle();
              } finally {
                setUpdatingTariffs(false);
              }
            }}
          >
            {updatingTariffs ? "Оновлення..." : "Оновити тарифи"}
          </button>
```

- [ ] **Step 4: Pass the prop from `DashboardContent.tsx`**

In `frontend/src/features/layout/components/DashboardContent.tsx`, in the `<CalculationTab .../>` call, right after:
```tsx
              cabinetTariffByLineId={cabinetTariffByLineId}
```
add:
```tsx
              runAutomationCycle={runAutomationCycle}
```

- [ ] **Step 5: Typecheck**

Run (from `frontend/`): `npm run typecheck`
Expected: no errors.

- [ ] **Step 6: Manual verification**

Open the Розрахунок tab, click "Оновити тарифи", confirm it shows "Оновлення...", disables itself, runs to completion, and produces the same success/error toast as the "Запустити плановий цикл" button on the Автоматизації tab (they call the same function).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/calculation/components/CalculationTab.tsx frontend/src/features/layout/components/DashboardContent.tsx
git commit -m "feat(calculation): add Оновити тарифи button to the Розрахунок tab"
```

---

## Final full-stack verification

After all 7 tasks:
- [ ] Backend: `cd backend && .\.venv\Scripts\python -m pytest -q` — all tests pass.
- [ ] Frontend: `cd frontend && npm test` — all tests pass. `npm run build` succeeds.
- [ ] Migration idempotency (no automated test exists for this in the repo — verify by restarting): start the backend container twice in a row against the same dev DB and confirm `run_startup_migrations()` doesn't error on either the `connection_charge_lines.cabinet_price_is_estimated` or `apartments.cabinet_markup_percent` columns the second time around.
- [ ] Live check against the real GUC cabinet (`portal-guc.tis.if.ua`, login `0320`) on a day when the target month is still unposted: run the automation cycle from the new button, confirm the estimated badge appears, and that the admin can still manually override/apply the tariff exactly as before — nothing is auto-applied.
