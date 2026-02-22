import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";

type OwnerChargeDraft = {
  kind: "owner_cost" | "reimbursement";
  category: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  event_date: string;
};

type MaintenanceDraft = {
  maintenance_type: "planned" | "unplanned";
  title: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  performed_at: string;
};

export function useOwnerActions({
  tok,
  apartmentId,
  period,
  own,
  mnt,
  ocModal,
  ocForm,
  mrModal,
  mrForm,
  setOcModal,
  setOcForm,
  setMrModal,
  setMrForm,
  pushToast,
  confirmRun,
  reload,
}: {
  tok: string | null;
  apartmentId?: number;
  period: { year: number; month: number };
  own: OwnerChargeDraft;
  mnt: MaintenanceDraft;
  ocModal: any;
  ocForm: any;
  mrModal: any;
  mrForm: any;
  setOcModal: (v: any) => void;
  setOcForm: (v: any) => void;
  setMrModal: (v: any) => void;
  setMrForm: (v: any) => void;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  confirmRun: (title: string, message: string, action: () => Promise<void>) => void;
  reload: () => Promise<unknown>;
}) {
  const addOwnerMutation = useMutation({
    mutationFn: async () =>
      api("/admin/owner-charges", tok, {
        method: "POST",
        body: JSON.stringify({
          apartment_id: apartmentId,
          year: period.year,
          month: period.month,
          kind: own.kind,
          category: own.category,
          description: own.description || null,
          amount: Number(own.amount),
          currency: own.currency,
          event_date: own.event_date,
        }),
      }),
    onSuccess: async () => {
      pushToast("Витрату/відшкодування додано", "success");
      await reload();
    },
    onError: (e: Error) =>
      pushToast(e.message || "Не вдалося зберегти витрату/відшкодування", "error"),
  });

  const addMaintMutation = useMutation({
    mutationFn: async () =>
      api("/admin/maintenance", tok, {
        method: "POST",
        body: JSON.stringify({
          apartment_id: apartmentId,
          maintenance_type: mnt.maintenance_type,
          title: mnt.title,
          description: mnt.description || null,
          amount: mnt.amount ? Number(mnt.amount) : null,
          currency: mnt.currency,
          performed_at: mnt.performed_at || null,
        }),
      }),
    onSuccess: async () => {
      pushToast("Запис обслуговування додано", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося зберегти обслуговування", "error"),
  });

  const saveOcMutation = useMutation({
    mutationFn: async (data: any) =>
      api(`/admin/owner-charges/${ocModal.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          year: Number(data.year),
          month: Number(data.month),
          kind: data.kind,
          category: data.category,
          description: data.description || null,
          amount: Number(data.amount),
          currency: data.currency,
          event_date: data.event_date,
        }),
      }),
    onSuccess: async () => {
      setOcModal(null);
      setOcForm(null);
      pushToast("Запис витрати/відшкодування оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити запис", "error"),
  });

  const deleteOcMutation = useMutation({
    mutationFn: async () => api(`/admin/owner-charges/${ocModal.id}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      setOcModal(null);
      setOcForm(null);
      await reload();
      pushToast("Запис видалено", "success");
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити запис", "error"),
  });

  const saveMrMutation = useMutation({
    mutationFn: async (data: any) =>
      api(`/admin/maintenance/${mrModal.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          maintenance_type: data.maintenance_type,
          title: data.title,
          description: data.description || null,
          contractor: null,
          amount: data.amount === "" ? null : Number(data.amount),
          currency: data.currency,
          scheduled_for: null,
          performed_at: data.performed_at || null,
          next_service_at: null,
          note: null,
        }),
      }),
    onSuccess: async () => {
      setMrModal(null);
      setMrForm(null);
      pushToast("Запис обслуговування оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити обслуговування", "error"),
  });

  const deleteMrMutation = useMutation({
    mutationFn: async () => api(`/admin/maintenance/${mrModal.id}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      setMrModal(null);
      setMrForm(null);
      await reload();
      pushToast("Запис видалено", "success");
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити запис", "error"),
  });

  const openOc = (item: any) => {
    setOcModal(item);
    setOcForm({
      year: item.year,
      month: item.month,
      kind: item.kind,
      category: item.category || "",
      description: item.description || "",
      amount: item.amount,
      currency: item.currency || "UAH",
      event_date: (item.event_date || "").slice(0, 10),
    });
  };

  const openMr = (item: any) => {
    setMrModal(item);
    setMrForm({
      maintenance_type: item.maintenance_type,
      title: item.title || "",
      description: item.description || "",
      amount: item.amount ?? "",
      currency: item.currency || "UAH",
      performed_at: (item.performed_at || "").slice(0, 10),
    });
  };

  const addOwner = async () => {
    await addOwnerMutation.mutateAsync();
  };

  const addMaint = async () => {
    await addMaintMutation.mutateAsync();
  };

  const saveOc = async (payload: any = null) => {
    const data = payload || ocForm;
    await saveOcMutation.mutateAsync(data);
  };

  const delOc = async () => {
    if (!ocModal) return;
    confirmRun("Видалити витрату/відшкодування", "Підтвердьте видалення запису.", async () => {
      await deleteOcMutation.mutateAsync();
    });
  };

  const saveMr = async (payload: any = null) => {
    const data = payload || mrForm;
    await saveMrMutation.mutateAsync(data);
  };

  const delMr = async () => {
    if (!mrModal) return;
    confirmRun("Видалити ремонт/обслуговування", "Підтвердьте видалення запису.", async () => {
      await deleteMrMutation.mutateAsync();
    });
  };

  return { addOwner, addMaint, saveOc, delOc, saveMr, delMr, openOc, openMr };
}
