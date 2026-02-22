import { useEffect, useMemo, useState } from "react";
import { sortBillingRows } from "@/shared/utils/billing-selectors";
import type { CalculationRow } from "@/shared/api/types";

const SORT_CFG_KEY = "um_sort_cfg";

type SortCfg = {
  key:
    | "default"
    | "service_name"
    | "previous_reading"
    | "current_reading"
    | "difference"
    | "unit_price"
    | "amount";
  dir: "asc" | "desc";
};

export function useSortedRows(rows: CalculationRow[]) {
  const [sortCfg, setSortCfg] = useState<SortCfg>(() => {
    try {
      const saved = localStorage.getItem(SORT_CFG_KEY);
      return saved ? (JSON.parse(saved) as SortCfg) : { key: "default", dir: "asc" };
    } catch {
      return { key: "default", dir: "asc" };
    }
  });

  const sortedRows = useMemo(() => {
    return sortBillingRows(rows || [], sortCfg);
  }, [rows, sortCfg]);

  useEffect(() => {
    localStorage.setItem(SORT_CFG_KEY, JSON.stringify(sortCfg));
  }, [sortCfg]);

  const toggleSort = (key: SortCfg["key"]) => {
    setSortCfg((prev) => {
      if (prev.key === key) return { key, dir: prev.dir === "asc" ? "desc" : "asc" };
      return { key, dir: "asc" };
    });
  };

  const sortIcon = (key: SortCfg["key"]) => {
    if (sortCfg.key !== key) return "";
    return sortCfg.dir === "asc" ? " ▲" : " ▼";
  };

  const resetSortDefault = () => setSortCfg({ key: "default", dir: "asc" });

  return { sortCfg, sortedRows, toggleSort, sortIcon, resetSortDefault };
}
