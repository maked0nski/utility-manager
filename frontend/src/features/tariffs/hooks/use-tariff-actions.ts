import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { inferUtilityType } from "@/shared/utils/format";
import type { Dispatch, SetStateAction } from "react";

type NewTariffForm = {
  service_name: string;
  charge_mode: "fixed" | "metered";
  price_per_unit: string;
  unit_name: "kWh" | "m3" | "month";
  effective_from: string;
  initial_meter_reading: string;
  meter_serial_number: string;
  service_status: "active" | "inactive";
  disable_from_month: string;
  personal_account: string;
  meter_id: string;
  meter_register: string;
  source_service_name: string;
};

type TariffEditPayload = {
  price_per_unit: string | number;
  unit_name: "kWh" | "m3" | "month";
  provider_company?: string;
  personal_account?: string;
  cabinet_url?: string;
  cabinet_login?: string;
  cabinet_password?: string;
  service_status: "active" | "inactive";
  disable_from_month?: string;
  meter_id?: string;
  meter_register?: string;
  source_service_name?: string;
};

export function useTariffActions({
  tok,
  sel,
  period,
  newTar,
  setNewTar,
  tModal,
  setTModal,
  tForm,
  setTForm,
  pushToast,
  confirmRun,
  invalidateApartmentQueries,
  reload,
}: {
  tok: string | null;
  sel: { apartment_id: number } | null;
  period: { year: number; month: number };
  newTar: NewTariffForm;
  setNewTar: Dispatch<SetStateAction<NewTariffForm>>;
  tModal: any;
  setTModal: (v: any) => void;
  tForm: TariffEditPayload | null;
  setTForm: (v: any) => void;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  confirmRun: (title: string, message: string, action: () => Promise<void>) => void;
  invalidateApartmentQueries: () => Promise<void>;
  reload: () => Promise<unknown>;
}) {
  const deleteTariffMutation = useMutation({
    mutationFn: async (tariffId: number) =>
      api(`/admin/tariffs/${tariffId}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      pushToast("Тариф видалено", "success");
      await invalidateApartmentQueries();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити тариф", "error"),
  });

  const createTariffMutation = useMutation({
    mutationFn: async () => {
      if (!sel?.apartment_id) throw new Error("Нерухомість не обрана.");
      const payload = {
        apartment_id: sel.apartment_id,
        service_name: newTar.service_name,
        charge_mode: newTar.charge_mode,
        utility_type:
          newTar.charge_mode === "metered" ? inferUtilityType(newTar.service_name) : null,
        price_per_unit: Number(Number(newTar.price_per_unit || 0).toFixed(2)),
        unit_name: newTar.unit_name,
        effective_from: newTar.effective_from,
        initial_meter_reading:
          newTar.charge_mode === "metered" && newTar.initial_meter_reading !== ""
            ? Number(newTar.initial_meter_reading)
            : null,
        meter_serial_number:
          newTar.charge_mode === "metered" ? newTar.meter_serial_number || null : null,
        meter_id:
          newTar.charge_mode === "metered" && newTar.source_service_name === "" && newTar.meter_id !== ""
            ? Number(newTar.meter_id)
            : null,
        meter_register: newTar.charge_mode === "metered" ? (newTar.meter_register || "total") : "total",
        source_service_name:
          newTar.charge_mode === "metered" && newTar.source_service_name !== ""
            ? newTar.source_service_name
            : null,
      };
      await api("/admin/tariffs", tok, { method: "POST", body: JSON.stringify(payload) });
      await api(`/admin/apartments/${sel.apartment_id}/tariffs/settings`, tok, {
        method: "PUT",
        body: JSON.stringify({
          service_name: newTar.service_name,
          personal_account: newTar.personal_account || null,
          last_tariff_check_at: new Date().toISOString(),
        }),
      });
      if (newTar.service_status === "inactive") {
        await api(
          `/admin/apartments/${sel.apartment_id}/services/${encodeURIComponent(newTar.service_name)}/activation`,
          tok,
          {
            method: "PUT",
            body: JSON.stringify({
              inactive_from: `${
                newTar.disable_from_month || `${period.year}-${String(period.month).padStart(2, "0")}`
              }-01`,
            }),
          },
        );
      }
    },
    onSuccess: async () => {
      setNewTar((s) => ({ ...s, personal_account: "" }));
      pushToast("Тариф створено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося створити тариф", "error"),
  });

  const saveTariffMutation = useMutation({
    mutationFn: async (data: TariffEditPayload) => {
      if (!sel?.apartment_id || !tModal) throw new Error("Тариф не обраний.");
      await api(`/admin/tariffs/${tModal.tariff_id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          price_per_unit: Number(Number(data.price_per_unit).toFixed(2)),
          unit_name: data.unit_name,
        }),
      });
      await api(`/admin/tariffs/${tModal.tariff_id}/binding`, tok, {
        method: "PUT",
        body: JSON.stringify({
          meter_id:
            data.source_service_name && data.source_service_name !== ""
              ? null
              : data.meter_id && data.meter_id !== ""
                ? Number(data.meter_id)
                : null,
          meter_register: data.meter_register || "total",
          source_service_name: data.source_service_name || null,
        }),
      });
      await api(`/admin/apartments/${sel.apartment_id}/tariffs/settings`, tok, {
        method: "PUT",
        body: JSON.stringify({
          service_name: tModal.service_name,
          provider_company: data.provider_company || null,
          personal_account: data.personal_account || null,
          cabinet_url: data.cabinet_url || null,
          cabinet_login: data.cabinet_login || null,
          cabinet_password: data.cabinet_password || null,
          last_tariff_check_at: new Date().toISOString(),
        }),
      });
      const inactiveFrom =
        data.service_status === "inactive"
          ? `${data.disable_from_month || `${period.year}-${String(period.month).padStart(2, "0")}`}-01`
          : null;
      await api(
        `/admin/apartments/${sel.apartment_id}/services/${encodeURIComponent(tModal.service_name)}/activation`,
        tok,
        { method: "PUT", body: JSON.stringify({ inactive_from: inactiveFrom }) },
      );
    },
    onSuccess: async () => {
      setTModal(null);
      setTForm(null);
      pushToast("Тариф оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити тариф", "error"),
  });

  const createTariff = async () => {
    await createTariffMutation.mutateAsync();
  };

  const openT = (row: any) => {
    setTModal(row);
    setTForm({
      price_per_unit: row.price_per_unit,
      unit_name: row.unit_name,
      provider_company: row.provider_company || "",
      personal_account: row.personal_account || "",
      cabinet_url: row.cabinet_url || "",
      cabinet_login: row.cabinet_login || "",
      cabinet_password: row.cabinet_password || "",
      service_status: row.is_active_for_period ? "active" : "inactive",
      disable_from_month: row.inactive_from
        ? String(row.inactive_from).slice(0, 7)
        : `${period.year}-${String(period.month).padStart(2, "0")}`,
      meter_id: row.meter_id ? String(row.meter_id) : "",
      meter_register: row.meter_register || "total",
      source_service_name: row.source_service_name || "",
    });
  };

  const saveT = async (payload: TariffEditPayload | null = null) => {
    const data = payload || tForm;
    if (!data) throw new Error("Немає даних тарифу для збереження.");
    await saveTariffMutation.mutateAsync(data);
  };

  const delT = async () => {
    if (!tModal) return;
    confirmRun(
      "Видалити тариф",
      `Підтвердьте видалення тарифу "${tModal.service_name}"`,
      async () => {
        await deleteTariffMutation.mutateAsync(tModal.tariff_id);
        setTModal(null);
        setTForm(null);
      },
    );
  };

  return { createTariff, openT, saveT, delT };
}
