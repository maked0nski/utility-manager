import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { MeterItem, MeterReplacementForm, MeterUpsertForm } from "@/shared/api/types";

type ConfirmRun = (title: string, message: string, action: () => void | Promise<void>) => void;

function humanizeMeterApiError(error: Error, fallback: string): string {
  const msg = (error?.message || "").toLowerCase();
  if (msg.includes("used in tariffs")) {
    return "Лічильник прив'язаний до тарифів. Спершу змініть або видаліть ці тарифи.";
  }
  if (msg.includes("not found")) {
    return "Лічильник або об'єкт не знайдено.";
  }
  if (msg.includes("conflict")) {
    return "Конфлікт даних. Оновіть сторінку і повторіть дію.";
  }
  return error.message || fallback;
}

function parseReading(input: string): number {
  const normalized = (input || "").trim().replace(",", ".");
  const value = Number(normalized);
  return Number.isFinite(value) ? value : Number.NaN;
}

export function useMeterActions({
  tok,
  apartmentId,
  meterForm,
  editingMeterId,
  replacingMeterId,
  replacementForm,
  setMeterForm,
  setEditingMeterId,
  setReplacingMeterId,
  setReplacementForm,
  pushToast,
  confirmRun,
  reload,
}: {
  tok: string | null;
  apartmentId: number | null | undefined;
  meterForm: MeterUpsertForm;
  editingMeterId: number | null;
  replacingMeterId: number | null;
  replacementForm: MeterReplacementForm;
  setMeterForm: (v: MeterUpsertForm) => void;
  setEditingMeterId: (v: number | null) => void;
  setReplacingMeterId: (v: number | null) => void;
  setReplacementForm: (v: MeterReplacementForm) => void;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  confirmRun: ConfirmRun;
  reload: () => Promise<unknown>;
}) {
  const resetMeterForm = () => {
    setEditingMeterId(null);
    setMeterForm({
      meter_type_id: "",
      serial_number: "",
      installed_at: "",
    });
  };

  const resetReplacementForm = () => {
    setReplacingMeterId(null);
    setReplacementForm({
      serial_number: "",
      initial_reading: "",
      installed_at: "",
    });
  };

  const createMeterMutation = useMutation({
    mutationFn: async () => {
      if (!apartmentId) throw new Error("Оберіть об'єкт.");
      return api("/admin/meters", tok, {
        method: "POST",
        body: JSON.stringify({
          apartment_id: apartmentId,
          meter_type_id: Number(meterForm.meter_type_id),
          serial_number: meterForm.serial_number || null,
          installed_at: meterForm.installed_at,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Лічильник додано", "success");
      resetMeterForm();
      await reload();
    },
    onError: (e: Error) => pushToast(humanizeMeterApiError(e, "Не вдалося додати лічильник"), "error"),
  });

  const updateMeterMutation = useMutation({
    mutationFn: async () => {
      if (!editingMeterId) throw new Error("Лічильник не обрано.");
      return api(`/admin/meters/${editingMeterId}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          meter_type_id: Number(meterForm.meter_type_id),
          serial_number: meterForm.serial_number || null,
          installed_at: meterForm.installed_at,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Лічильник оновлено", "success");
      resetMeterForm();
      await reload();
    },
    onError: (e: Error) => pushToast(humanizeMeterApiError(e, "Не вдалося оновити лічильник"), "error"),
  });

  const deleteMeterMutation = useMutation({
    mutationFn: async (meterId: number) => api(`/admin/meters/${meterId}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      pushToast("Лічильник видалено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(humanizeMeterApiError(e, "Не вдалося видалити лічильник"), "error"),
  });

  const replaceMeterMutation = useMutation({
    mutationFn: async () => {
      if (!replacingMeterId) throw new Error("Лічильник не обрано для заміни.");
      const reading = parseReading(replacementForm.initial_reading);
      return api(`/admin/meters/${replacingMeterId}/replace`, tok, {
        method: "POST",
        body: JSON.stringify({
          serial_number: replacementForm.serial_number || null,
          initial_reading: reading,
          installed_at: replacementForm.installed_at,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Лічильник замінено. Історію збережено.", "success");
      resetReplacementForm();
      await reload();
    },
    onError: (e: Error) =>
      pushToast(humanizeMeterApiError(e, "Не вдалося замінити лічильник"), "error"),
  });

  const submitMeter = async () => {
    if (!meterForm.meter_type_id.trim()) {
      pushToast("Оберіть тип лічильника", "error");
      return false;
    }
    if (!meterForm.installed_at.trim()) {
      pushToast("Вкажіть дату встановлення", "error");
      return false;
    }
    if (editingMeterId) {
      await updateMeterMutation.mutateAsync();
      return true;
    }
    await createMeterMutation.mutateAsync();
    return true;
  };

  const startEditMeter = (meter: MeterItem) => {
    setEditingMeterId(meter.id);
    setMeterForm({
      meter_type_id: meter.meter_type_id ? String(meter.meter_type_id) : "",
      serial_number: meter.serial_number || "",
      installed_at: meter.installed_at || "",
    });
  };

  const askDeleteMeter = (meter: MeterItem) => {
      const meterLabel = meter.display_name || meter.meter_type_name || "Лічильник";
    confirmRun(
      "Видалити лічильник",
      `Підтвердьте видалення лічильника "${meterLabel}"`,
      async () => {
        await deleteMeterMutation.mutateAsync(meter.id);
      },
    );
  };

  const startReplaceMeter = (meter: MeterItem) => {
    setReplacingMeterId(meter.id);
    setReplacementForm({
      serial_number: "",
      initial_reading: "",
      installed_at: "",
    });
  };

  const submitReplacement = async () => {
    if (!replacementForm.initial_reading.trim()) {
      pushToast("Вкажіть стартовий показник нового лічильника", "error");
      return;
    }
    const reading = parseReading(replacementForm.initial_reading);
    if (!Number.isFinite(reading) || reading < 0) {
      pushToast("Стартовий показник має бути невід'ємним числом", "error");
      return;
    }
    if (!replacementForm.installed_at.trim()) {
      pushToast("Вкажіть дату встановлення нового лічильника", "error");
      return;
    }
    await replaceMeterMutation.mutateAsync();
  };

  return {
    submitMeter,
    startEditMeter,
    askDeleteMeter,
    startReplaceMeter,
    submitReplacement,
    resetReplacementForm,
    resetMeterForm,
    deleteMeterMutation,
    createMeterMutation,
    updateMeterMutation,
  };
}
