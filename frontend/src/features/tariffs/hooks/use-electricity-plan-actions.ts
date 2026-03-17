import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { MeterItem } from "@/shared/api/types";

type ElectricityPlanForm = {
  plan_mode: "single" | "day_night" | "tri_zone";
  meter_id: string;
  effective_from: string;
  single_service_name: string;
  day_service_name: string;
  night_service_name: string;
  peak_service_name: string;
  semi_peak_service_name: string;
  off_peak_service_name: string;
  single_price_per_unit: string;
  day_price_per_unit: string;
  night_price_per_unit: string;
  peak_price_per_unit: string;
  semi_peak_price_per_unit: string;
  off_peak_price_per_unit: string;
  single_initial_reading: string;
  day_initial_reading: string;
  night_initial_reading: string;
  peak_initial_reading: string;
  semi_peak_initial_reading: string;
  off_peak_initial_reading: string;
};

export function useElectricityPlanActions({
  tok,
  apartmentId,
  period,
  meters,
  pushToast,
  reload,
}: {
  tok: string | null;
  apartmentId: number | null | undefined;
  period: { year: number; month: number };
  meters: MeterItem[];
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  reload: () => Promise<unknown>;
}) {
  const [electricityPlanForm, setElectricityPlanForm] = useState<ElectricityPlanForm>({
    plan_mode: "single",
    meter_id: "",
    effective_from: `${period.year}-${String(period.month).padStart(2, "0")}-01`,
    single_service_name: "Електроенергія",
    day_service_name: "Електроенергія денний тариф",
    night_service_name: "Електроенергія нічний тариф",
    peak_service_name: "Електроенергія піковий тариф",
    semi_peak_service_name: "Електроенергія напівпіковий тариф",
    off_peak_service_name: "Електроенергія нічний тариф",
    single_price_per_unit: "",
    day_price_per_unit: "",
    night_price_per_unit: "",
    peak_price_per_unit: "",
    semi_peak_price_per_unit: "",
    off_peak_price_per_unit: "",
    single_initial_reading: "",
    day_initial_reading: "",
    night_initial_reading: "",
    peak_initial_reading: "",
    semi_peak_initial_reading: "",
    off_peak_initial_reading: "",
  });

  const electricityMeters = useMemo(
    () => meters.filter((m) => m.utility_type === "electricity" && (m.is_active ?? true)),
    [meters],
  );

  const primaryElectricityMeterId = electricityMeters[0]?.id ? String(electricityMeters[0].id) : "";
  const primaryElectricityInitialReading =
    electricityMeters[0]?.initial_reading !== undefined ? String(electricityMeters[0]?.initial_reading ?? "") : "";

  useEffect(() => {
    const nextEffectiveFrom = `${period.year}-${String(period.month).padStart(2, "0")}-01`;
    setElectricityPlanForm((current) => {
      const nextMeterId = current.meter_id || primaryElectricityMeterId;
      const nextInitialReading = current.single_initial_reading || primaryElectricityInitialReading;
      if (
        current.effective_from === nextEffectiveFrom &&
        current.meter_id === nextMeterId &&
        current.single_initial_reading === nextInitialReading
      ) {
        return current;
      }
      return {
        ...current,
        effective_from: nextEffectiveFrom,
        meter_id: nextMeterId,
        single_initial_reading: nextInitialReading,
      };
    });
  }, [period.year, period.month, primaryElectricityMeterId, primaryElectricityInitialReading]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!apartmentId) throw new Error("Нерухомість не обрана.");
      if (!electricityPlanForm.meter_id) throw new Error("Оберіть електролічильник.");
      const body: Record<string, unknown> = {
        plan_mode: electricityPlanForm.plan_mode,
        meter_id: Number(electricityPlanForm.meter_id),
        effective_from: electricityPlanForm.effective_from,
        single_service_name: electricityPlanForm.single_service_name,
        day_service_name: electricityPlanForm.day_service_name,
        night_service_name: electricityPlanForm.night_service_name,
      };
      if (electricityPlanForm.plan_mode === "single") {
        if (!electricityPlanForm.single_price_per_unit.trim()) {
          throw new Error("Вкажіть тариф для однотарифного режиму.");
        }
        body.single_price_per_unit = Number(electricityPlanForm.single_price_per_unit || 0);
        body.single_initial_reading =
          electricityPlanForm.single_initial_reading.trim() === ""
            ? null
            : Number(electricityPlanForm.single_initial_reading);
      } else if (electricityPlanForm.plan_mode === "day_night") {
        if (!electricityPlanForm.day_price_per_unit.trim() || !electricityPlanForm.night_price_per_unit.trim()) {
          throw new Error("Вкажіть тарифи day і night.");
        }
        if (!electricityPlanForm.day_initial_reading.trim() || !electricityPlanForm.night_initial_reading.trim()) {
          throw new Error("Вкажіть стартові показники day і night.");
        }
        body.day_price_per_unit = Number(electricityPlanForm.day_price_per_unit || 0);
        body.night_price_per_unit = Number(electricityPlanForm.night_price_per_unit || 0);
        body.day_initial_reading =
          electricityPlanForm.day_initial_reading.trim() === ""
            ? null
            : Number(electricityPlanForm.day_initial_reading);
        body.night_initial_reading =
          electricityPlanForm.night_initial_reading.trim() === ""
            ? null
            : Number(electricityPlanForm.night_initial_reading);
      } else {
        if (
          !electricityPlanForm.peak_price_per_unit.trim() ||
          !electricityPlanForm.semi_peak_price_per_unit.trim() ||
          !electricityPlanForm.off_peak_price_per_unit.trim()
        ) {
          throw new Error("Вкажіть тарифи peak / semi_peak / off_peak.");
        }
        if (
          !electricityPlanForm.peak_initial_reading.trim() ||
          !electricityPlanForm.semi_peak_initial_reading.trim() ||
          !electricityPlanForm.off_peak_initial_reading.trim()
        ) {
          throw new Error("Вкажіть стартові показники peak / semi_peak / off_peak.");
        }
        body.peak_service_name = electricityPlanForm.peak_service_name;
        body.semi_peak_service_name = electricityPlanForm.semi_peak_service_name;
        body.off_peak_service_name = electricityPlanForm.off_peak_service_name;
        body.peak_price_per_unit = Number(electricityPlanForm.peak_price_per_unit || 0);
        body.semi_peak_price_per_unit = Number(electricityPlanForm.semi_peak_price_per_unit || 0);
        body.off_peak_price_per_unit = Number(electricityPlanForm.off_peak_price_per_unit || 0);
        body.peak_initial_reading = Number(electricityPlanForm.peak_initial_reading);
        body.semi_peak_initial_reading = Number(electricityPlanForm.semi_peak_initial_reading);
        body.off_peak_initial_reading = Number(electricityPlanForm.off_peak_initial_reading);
      }
      await api(`/admin/apartments/${apartmentId}/electricity-plan`, tok, {
        method: "PUT",
        body: JSON.stringify(body),
      });
    },
    onSuccess: async () => {
      pushToast("План електрики оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити план електрики", "error"),
  });

  const saveElectricityPlan = async () => {
    await mutation.mutateAsync();
  };

  const deleteElectricityPlan = async (planId: number) => {
    if (!apartmentId) throw new Error("Нерухомість не обрана.");
    await api(`/admin/apartments/${apartmentId}/electricity-plans/${planId}`, tok, {
      method: "DELETE",
    });
    pushToast("Режим електрики видалено", "success");
    await reload();
  };

  return {
    electricityPlanForm,
    setElectricityPlanForm,
    electricityMeters,
    saveElectricityPlan,
    deleteElectricityPlan,
  };
}
