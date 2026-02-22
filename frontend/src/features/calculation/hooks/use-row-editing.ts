import { useEffect, useRef, useState } from "react";
import type { CalculationRow } from "@/shared/api/types";

type RowDraft = {
  previous_reading?: string;
  current_reading?: string;
  unit_price?: string;
};

export function useRowEditing({ asInt }: { asInt: (v: unknown) => string }) {
  const [editSrv, setEditSrv] = useState<string | null>(null);
  const [draft, setDraft] = useState<RowDraft>({});
  const editRef = useRef<HTMLTableRowElement | null>(null);

  useEffect(() => {
    if (!editSrv) return;
    const h = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (target && editRef.current && !editRef.current.contains(target)) {
        setEditSrv(null);
        setDraft({});
      }
    };
    window.addEventListener("mousedown", h);
    return () => window.removeEventListener("mousedown", h);
  }, [editSrv]);

  const start = (row: CalculationRow) => {
    setEditSrv(row.service_name);
    setDraft({
      previous_reading: asInt(row.previous_reading),
      current_reading: asInt(row.current_reading),
      unit_price: Number(row.unit_price || 0).toFixed(2),
    });
  };

  const changed = (row: CalculationRow) =>
    editSrv === row.service_name &&
    (String(draft.current_reading ?? "") !== asInt(row.current_reading) ||
      String(draft.previous_reading ?? "") !== asInt(row.previous_reading) ||
      Number(draft.unit_price ?? row.unit_price) !== Number(row.unit_price));

  return { editSrv, setEditSrv, draft, setDraft, editRef, start, changed };
}
