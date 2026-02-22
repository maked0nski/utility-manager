import { defaultServiceOrderScore } from "@/features/calculation/utils/service-order";

type NumericLike = number | string | null | undefined;

interface ApartmentBalanceLike {
  utility_balance?: NumericLike;
  rent_balance?: NumericLike;
  total_balance?: NumericLike;
}

interface SortCfg {
  key:
    | "default"
    | "service_name"
    | "previous_reading"
    | "current_reading"
    | "difference"
    | "unit_price"
    | "amount";
  dir: "asc" | "desc";
}

interface BillingRow {
  service_name: string;
  previous_reading?: NumericLike;
  current_reading?: NumericLike;
  difference?: NumericLike;
  unit_price?: NumericLike;
  amount?: NumericLike;
}

export const calculatePortfolioTotals = (apartments: ApartmentBalanceLike[] = []) =>
  apartments.reduce(
    (a, x) => ({
      utility: a.utility + Number(x.utility_balance || 0),
      rent: a.rent + Number(x.rent_balance || 0),
      total: a.total + Number(x.total_balance || 0),
    }),
    { utility: 0, rent: 0, total: 0 },
  );

export const calculateAccrualTotal = (rows: BillingRow[] = []) =>
  rows.reduce((sum, r) => sum + Number(r.amount || 0), 0);

export const sortBillingRows = (rows: BillingRow[] = [], sortCfg: SortCfg): BillingRow[] => {
  const nextRows = [...rows];
  const cmpNum = (a: NumericLike, b: NumericLike) => {
    const na = a === null || a === undefined || a === "" ? null : Number(a);
    const nb = b === null || b === undefined || b === "" ? null : Number(b);
    if (na === null && nb === null) return 0;
    if (na === null) return 1;
    if (nb === null) return -1;
    return na - nb;
  };
  const cmpStr = (a: string | null | undefined, b: string | null | undefined) =>
    String(a || "").localeCompare(String(b || ""), "uk", { sensitivity: "base" });

  nextRows.sort((a, b) => {
    if (sortCfg.key === "default") {
      const o = defaultServiceOrderScore(a) - defaultServiceOrderScore(b);
      if (o !== 0) return o;
      return cmpStr(a.service_name, b.service_name);
    }
    let c = 0;
    if (sortCfg.key === "service_name") c = cmpStr(a.service_name, b.service_name);
    if (sortCfg.key === "previous_reading") c = cmpNum(a.previous_reading, b.previous_reading);
    if (sortCfg.key === "current_reading") c = cmpNum(a.current_reading, b.current_reading);
    if (sortCfg.key === "difference") c = cmpNum(a.difference, b.difference);
    if (sortCfg.key === "unit_price") c = cmpNum(a.unit_price, b.unit_price);
    if (sortCfg.key === "amount") c = cmpNum(a.amount, b.amount);
    if (c === 0) c = cmpStr(a.service_name, b.service_name);
    return sortCfg.dir === "asc" ? c : -c;
  });

  return nextRows;
};
