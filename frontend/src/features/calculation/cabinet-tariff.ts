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
  effective_to?: string | null;
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

// Mirrors the backend's interval semantics for "the line active on a given
// date" (see `_charge_line_active_on` in tariff_auto_check.py): a line covers
// `targetDate` when its effective_from is on or before it and its
// effective_to (if any) is on or after it.
function isLineActiveOn(line: ChargeLineForCatchUp, targetDate: string): boolean {
  const from = line.effective_from.slice(0, 10);
  if (from > targetDate) return false;
  if (line.effective_to) {
    const to = line.effective_to.slice(0, 10);
    if (to < targetDate) return false;
  }
  return true;
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
  const sourceLine = connectionLines.find(
    (candidate) => candidate.id !== targetLine.id && isLineActiveOn(candidate, sourceDate),
  );
  if (!sourceLine || sourceLine.cabinet_price_is_estimated) return null;
  if (sourceLine.cabinet_price_per_unit == null) return null;
  const shortfall = Number(sourceLine.cabinet_price_per_unit) - Number(sourceLine.price_per_unit);
  if (shortfall <= 0) return null;
  return { sourcePeriod: sourceDate.slice(0, 7), amount: shortfall };
}
