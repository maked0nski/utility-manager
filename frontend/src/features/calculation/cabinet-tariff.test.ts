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
