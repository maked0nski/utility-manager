import { describe, expect, it } from "vitest";
import { calcCurrentBalance, calcNextPreviousDebt } from "@/shared/utils/monthly-cycle";

describe("monthly cycle smoke", () => {
  it("runs month scenario: charges -> payment -> confirm", () => {
    const januaryBalance = calcCurrentBalance({
      previousDebt: -0.5,
      monthCharges: 2281.46,
      monthPayments: 0,
    });
    expect(januaryBalance).toBeCloseTo(2280.96, 2);

    const februaryPrevious = calcNextPreviousDebt({
      currentBalance: januaryBalance,
      isLocked: true,
    });
    expect(februaryPrevious).toBeCloseTo(2280.96, 2);
  });
});
