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
