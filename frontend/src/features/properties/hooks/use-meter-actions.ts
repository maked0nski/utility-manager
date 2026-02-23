import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { MeterItem, MeterUpsertForm } from "@/shared/api/types";

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
  setMeterForm,
  setEditingMeterId,
  pushToast,
  confirmRun,
  reload,
}: {
  tok: string | null;
  apartmentId: number | null | undefined;
  meterForm: MeterUpsertForm;
  editingMeterId: number | null;
  setMeterForm: (v: MeterUpsertForm) => void;
  setEditingMeterId: (v: number | null) => void;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  confirmRun: ConfirmRun;
  reload: () => Promise<unknown>;
}) {
  const resetMeterForm = () => {
    setEditingMeterId(null);
    setMeterForm({
      service_name: "",
      utility_type: "other",
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
          service_name: meterForm.service_name,
          utility_type: meterForm.utility_type,
          serial_number: meterForm.serial_number || null,
          initial_reading: parseReading(meterForm.initial_reading),
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
          service_name: meterForm.service_name,
          utility_type: meterForm.utility_type,
          serial_number: meterForm.serial_number || null,
          initial_reading: parseReading(meterForm.initial_reading),
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

  const submitMeter = async () => {
    if (!meterForm.service_name.trim()) {
      pushToast("Вкажіть назву послуги лічильника", "error");
      return;
    }
    if (!meterForm.initial_reading.trim()) {
      pushToast("Вкажіть початковий показник", "error");
      return;
    }
    const reading = parseReading(meterForm.initial_reading);
    if (!Number.isFinite(reading)) {
      pushToast("Початковий показник має бути числом", "error");
      return;
    }
    if (reading < 0) {
      pushToast("Початковий показник не може бути від'ємним", "error");
      return;
    }
    if (!meterForm.installed_at.trim()) {
      pushToast("Вкажіть дату встановлення", "error");
      return;
    }
    if (editingMeterId) {
      await updateMeterMutation.mutateAsync();
      return;
    }
    await createMeterMutation.mutateAsync();
  };

  const startEditMeter = (meter: MeterItem) => {
    setEditingMeterId(meter.id);
    setMeterForm({
      service_name: meter.service_name || "",
      utility_type: meter.utility_type || "other",
      serial_number: meter.serial_number || "",
      initial_reading: String(meter.initial_reading ?? ""),
      installed_at: meter.installed_at || "",
    });
  };

  const askDeleteMeter = (meter: MeterItem) => {
    confirmRun(
      "Видалити лічильник",
      `Підтвердьте видалення лічильника "${meter.service_name}"`,
      async () => {
        await deleteMeterMutation.mutateAsync(meter.id);
      },
    );
  };

  return {
    submitMeter,
    startEditMeter,
    askDeleteMeter,
    resetMeterForm,
    deleteMeterMutation,
    createMeterMutation,
    updateMeterMutation,
  };
}
