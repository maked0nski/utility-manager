import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { Dispatch, SetStateAction } from "react";
import type {
  CalculationRow,
  MeterSubmitDispatchResult,
  MeterSubmitEvaluateResult,
} from "@/shared/api/types";

type Period = { year: number; month: number };
type DraftData = {
  previous_reading?: string;
  current_reading?: string;
  unit_price?: string;
};
type UtilityPaymentForm = {
  amount: string | number;
  paid_at: string;
  note?: string | null;
};
type SaveUtilityPaymentPayload = {
  apartment_id: number;
  amount: number;
  paid_at: string;
  note: string | null;
};

interface UseBillingActionsParams {
  tok: string | null;
  apartmentId?: number;
  period: Period;
  pay: UtilityPaymentForm;
  draft: DraftData;
  setEditSrv: (v: string | null) => void;
  setDraft: Dispatch<SetStateAction<DraftData>>;
  setPayModal: (v: boolean) => void;
  pushToast: (message: string, kind?: "success" | "error") => void;
  confirmRun: (title: string, message: string, action: () => void | Promise<void>) => void;
  reload: () => Promise<unknown>;
  invalidateApartmentQueries: () => Promise<void>;
  calcLocked?: boolean;
}

export function useBillingActions({
  tok,
  apartmentId,
  period,
  pay,
  draft,
  setEditSrv,
  setDraft,
  setPayModal,
  pushToast,
  confirmRun,
  reload,
  invalidateApartmentQueries,
  calcLocked,
}: UseBillingActionsParams) {
  const saveUtilityPaymentMutation = useMutation({
    mutationFn: async (payload: SaveUtilityPaymentPayload) =>
      api("/admin/payments/utilities", tok, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: async () => {
      pushToast("Оплату збережено", "success");
      await invalidateApartmentQueries();
    },
    onError: (e: Error) => pushToast(e.message || "Помилка збереження оплати", "error"),
  });

  const saveRowMutation = useMutation({
    mutationFn: async (row: CalculationRow) => {
      if (
        row.meter_id &&
        draft.current_reading !== undefined &&
        draft.current_reading !== "" &&
        row.previous_reading !== null &&
        row.previous_reading !== undefined &&
        Number(draft.current_reading) < Number(row.previous_reading)
      ) {
        throw new Error(`Поточний показник не може бути меншим за попередній (${row.previous_reading}).`);
      }
      if (row.line_id && draft.unit_price !== undefined) {
        await api(`/admin/charge-lines/${row.line_id}/apply-from-period`, tok, {
          method: "POST",
          body: JSON.stringify({
            year: period.year,
            month: period.month,
            price_per_unit: Number(Number(draft.unit_price).toFixed(2)),
            unit_name: row.unit_name,
          }),
        });
      }
      if (
        row.meter_id &&
        row.can_edit_previous &&
        draft.previous_reading !== undefined &&
        draft.previous_reading !== ""
      ) {
        await api(`/admin/meters/${row.meter_id}/initial-reading`, tok, {
          method: "PUT",
          body: JSON.stringify({ value: Number(draft.previous_reading) }),
        });
      }
      if (row.meter_id && draft.current_reading !== undefined && draft.current_reading !== "") {
        await api("/admin/readings", tok, {
          method: "POST",
          body: JSON.stringify({
            meter_id: row.meter_id,
            register_name: row.meter_register || "total",
            year: period.year,
            month: period.month,
            value: Number(draft.current_reading),
          }),
        });
        if (apartmentId) {
          const registerName = row.meter_register || "total";
          const evalResult = await api<MeterSubmitEvaluateResult>(
            `/admin/automations/meter-submit/evaluate?apartment_id=${encodeURIComponent(
              String(apartmentId),
            )}&meter_id=${encodeURIComponent(String(row.meter_id))}&register_name=${encodeURIComponent(
              registerName,
            )}&year=${encodeURIComponent(String(period.year))}&month=${encodeURIComponent(String(period.month))}`,
            tok,
          );
          if (evalResult.can_submit) {
            confirmRun(
              "Передати показник постачальнику",
              `Ви зберегли показник для "${row.service_name}". Передати його через automation "${
                evalResult.template_name || "постачальника"
              }"?`,
              async () => {
                const dispatchResult = await api<MeterSubmitDispatchResult>("/admin/automations/meter-submit/dispatch", tok, {
                  method: "POST",
                  body: JSON.stringify({
                    apartment_id: apartmentId,
                    meter_id: row.meter_id,
                    register_name: registerName,
                    year: period.year,
                    month: period.month,
                  }),
                });
                if (dispatchResult.dispatched) {
                  pushToast(dispatchResult.message || "Показник передано постачальнику", "success");
                  await invalidateApartmentQueries();
                } else {
                  pushToast(dispatchResult.message || "Показник не передано", "error");
                }
              },
            );
          }
        }
      }
    },
    onSuccess: async () => {
      setEditSrv(null);
      setDraft({});
      pushToast("Рядок розрахунку оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити рядок", "error"),
  });

  const recalcMonthMutation = useMutation({
    mutationFn: async () =>
      api("/admin/billing/recalculate", tok, {
        method: "POST",
        body: JSON.stringify({ apartment_id: apartmentId, year: period.year, month: period.month }),
      }),
    onSuccess: async () => {
      pushToast("Місяць перераховано", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося перерахувати місяць", "error"),
  });

  const toggleLockMonthMutation = useMutation({
    mutationFn: async () => {
      const path = calcLocked ? "/admin/billing/unlock" : "/admin/billing/lock";
      await api(path, tok, {
        method: "POST",
        body: JSON.stringify({ apartment_id: apartmentId, year: period.year, month: period.month }),
      });
    },
    onSuccess: async () => {
      pushToast(calcLocked ? "Період розблоковано" : "Період підтверджено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося змінити статус періоду", "error"),
  });

  const saveRow = async (row: CalculationRow) => {
    await saveRowMutation.mutateAsync(row);
  };

  const savePay = async (payload: UtilityPaymentForm | null = null) => {
    const data = payload || pay;
    if (!apartmentId) throw new Error("Apartment is not selected");
    await saveUtilityPaymentMutation.mutateAsync({
      apartment_id: apartmentId,
      amount: Number(data.amount || 0),
      paid_at: data.paid_at,
      note: data.note || null,
    });
    setPayModal(false);
  };

  const recalcMonth = async () => {
    await recalcMonthMutation.mutateAsync();
  };

  const toggleLockMonth = async () => {
    await toggleLockMonthMutation.mutateAsync();
  };

  return {
    savePay,
    saveRow,
    recalcMonth,
    toggleLockMonth,
    saveUtilityPaymentMutation,
  };
}
