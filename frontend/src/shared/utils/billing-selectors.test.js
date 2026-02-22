import { describe, expect, it } from "vitest";
import {
  calculateAccrualTotal,
  calculatePortfolioTotals,
  sortBillingRows,
} from "@/shared/utils/billing-selectors";

describe("billing selectors", () => {
  it("calculates portfolio totals", () => {
    const totals = calculatePortfolioTotals([
      { utility_balance: "10.5", rent_balance: "-2", total_balance: "8.5" },
      { utility_balance: "4.5", rent_balance: "2", total_balance: "6.5" },
    ]);
    expect(totals).toEqual({ utility: 15, rent: 0, total: 15 });
  });

  it("calculates accrual total", () => {
    const total = calculateAccrualTotal([{ amount: "12.40" }, { amount: 7.6 }, { amount: null }]);
    expect(total).toBe(20);
  });

  it("sorts rows by default service order", () => {
    const rows = [
      { service_name: "Інтернет" },
      { service_name: "Квартплата" },
      { service_name: "Газопостачання" },
    ];
    const sorted = sortBillingRows(rows, { key: "default", dir: "asc" });
    expect(sorted.map((x) => x.service_name)).toEqual([
      "Квартплата",
      "Газопостачання",
      "Інтернет",
    ]);
  });
});
