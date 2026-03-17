import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type {
  ApartmentEquipmentForm,
  ApartmentEquipmentItem,
} from "@/shared/api/types";
import type { Dispatch, SetStateAction } from "react";

function toPayload(form: ApartmentEquipmentForm) {
  return {
    name: form.name.trim(),
    category: form.category.trim() || "other",
    model_name: form.model_name.trim() || null,
    serial_number: form.serial_number.trim() || null,
    installed_at: form.installed_at || null,
    manual_url: form.manual_url.trim() || null,
    service_interval_days:
      form.service_interval_days.trim() !== ""
        ? Number(form.service_interval_days)
        : null,
    last_service_at: form.last_service_at || null,
    next_service_at: form.next_service_at || null,
    note: form.note.trim() || null,
    is_active: Boolean(form.is_active),
  };
}

export function useEquipmentActions({
  tok,
  apartmentId,
  equipmentForm,
  editingEquipmentId,
  setEquipmentForm,
  setEditingEquipmentId,
  pushToast,
  confirmRun,
  reload,
}: {
  tok: string | null;
  apartmentId: number | null | undefined;
  equipmentForm: ApartmentEquipmentForm;
  editingEquipmentId: number | null;
  setEquipmentForm: Dispatch<SetStateAction<ApartmentEquipmentForm>>;
  setEditingEquipmentId: Dispatch<SetStateAction<number | null>>;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  confirmRun: (title: string, message: string, action: () => Promise<void>) => void;
  reload: () => Promise<unknown>;
}) {
  const createMutation = useMutation({
    mutationFn: async () => {
      if (!apartmentId) throw new Error("Нерухомість не обрана.");
      const payload = toPayload(equipmentForm);
      if (!payload.name) throw new Error("Вкажіть назву обладнання.");
      await api(`/admin/apartments/${apartmentId}/equipment`, tok, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async () => {
      pushToast("Обладнання додано", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося додати обладнання", "error"),
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!apartmentId || !editingEquipmentId) throw new Error("Обладнання не обрано.");
      const payload = toPayload(equipmentForm);
      if (!payload.name) throw new Error("Вкажіть назву обладнання.");
      await api(`/admin/apartments/${apartmentId}/equipment/${editingEquipmentId}`, tok, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async () => {
      pushToast("Обладнання оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити обладнання", "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: async (equipmentId: number) => {
      if (!apartmentId) throw new Error("Нерухомість не обрана.");
      await api(`/admin/apartments/${apartmentId}/equipment/${equipmentId}`, tok, {
        method: "DELETE",
      });
    },
    onSuccess: async () => {
      pushToast("Обладнання видалено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити обладнання", "error"),
  });

  const resetEquipmentForm = () => {
    setEditingEquipmentId(null);
    setEquipmentForm({
      name: "",
      category: "other",
      model_name: "",
      serial_number: "",
      installed_at: "",
      manual_url: "",
      service_interval_days: "",
      last_service_at: "",
      next_service_at: "",
      note: "",
      is_active: true,
    });
  };

  const startEditEquipment = (item: ApartmentEquipmentItem) => {
    setEditingEquipmentId(item.id);
    setEquipmentForm({
      name: item.name || "",
      category: item.category || "other",
      model_name: item.model_name || "",
      serial_number: item.serial_number || "",
      installed_at: item.installed_at || "",
      manual_url: item.manual_url || "",
      service_interval_days:
        item.service_interval_days !== null && item.service_interval_days !== undefined
          ? String(item.service_interval_days)
          : "",
      last_service_at: item.last_service_at || "",
      next_service_at: item.next_service_at || "",
      note: item.note || "",
      is_active: item.is_active,
    });
  };

  const askDeleteEquipment = (item: ApartmentEquipmentItem) => {
    confirmRun(
      "Видалити обладнання",
      `Підтвердьте видалення обладнання "${item.name}"`,
      async () => {
        await deleteMutation.mutateAsync(item.id);
        if (editingEquipmentId === item.id) resetEquipmentForm();
      },
    );
  };

  const submitEquipment = async () => {
    if (editingEquipmentId) {
      await updateMutation.mutateAsync();
    } else {
      await createMutation.mutateAsync();
    }
    resetEquipmentForm();
  };

  return {
    submitEquipment,
    startEditEquipment,
    askDeleteEquipment,
    resetEquipmentForm,
  };
}
