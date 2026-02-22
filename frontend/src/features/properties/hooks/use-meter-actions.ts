import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { MeterItem, MeterUpsertForm } from "@/shared/api/types";

type ConfirmRun = (title: string, message: string, action: () => void | Promise<void>) => void;

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
          initial_reading: Number(meterForm.initial_reading),
          installed_at: meterForm.installed_at,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Лічильник додано", "success");
      resetMeterForm();
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося додати лічильник", "error"),
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
          initial_reading: Number(meterForm.initial_reading),
          installed_at: meterForm.installed_at,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Лічильник оновлено", "success");
      resetMeterForm();
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити лічильник", "error"),
  });

  const deleteMeterMutation = useMutation({
    mutationFn: async (meterId: number) => api(`/admin/meters/${meterId}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      pushToast("Лічильник видалено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити лічильник", "error"),
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
