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

// Same float-noise guard as ceilToCents: 100 * 1.1 === 110.00000000000001 in JS,
// which would otherwise flag an exact floor match (110 vs 110) as a violation.
const FLOAT_EPSILON = 1e-9;

export function evaluateCabinetTariff(
  myPrice: number,
  cabinet: CabinetTariffInfo,
  now: Date = new Date(),
): CabinetTariffStatus {
  const ageDays = (now.getTime() - new Date(cabinet.checkedAt).getTime()) / MS_PER_DAY;
  return {
    freshness: ageDays <= FRESHNESS_WINDOW_DAYS ? "fresh" : "stale",
    floorViolation: myPrice < cabinet.price * FLOOR_MULTIPLIER - FLOAT_EPSILON,
    suggestedPrice: ceilToCents(cabinet.price * FLOOR_MULTIPLIER),
  };
}
