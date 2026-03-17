import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { monthStart, normalizePhone } from "@/shared/utils/format";
import type { Dispatch, SetStateAction } from "react";

type TenantForm = {
  full_name: string;
  primary_phone: string;
  email: string;
  phones: string;
  contacts_text: string;
  bank_statement_name: string;
  rent_amount: string;
  rent_currency: "UAH" | "USD" | "EUR";
  passport_number: string;
  passport_issued_by: string;
  passport_issue_date: string;
  passport_expiry_date: string;
};

type NewTenantForm = {
  full_name: string;
  phone: string;
  email: string;
  access_code: string;
  start_date: string;
  rent_amount: string;
  rent_currency: "UAH" | "USD" | "EUR";
  bank_statement_name: string;
};

type TenantProfilePayload = {
  full_name: string;
  primary_phone: string;
  email: string;
  phones: string;
  contacts_text: string;
  bank_statement_name: string;
  rent_amount: string;
  rent_currency: "UAH" | "USD" | "EUR";
  passport_number: string;
  passport_issued_by: string;
  passport_issue_date: string;
  passport_expiry_date: string;
  portal_enabled: boolean;
  can_submit_meter_readings: boolean;
  portal_password: string;
};

export function useTenantActions({
  tok,
  detail,
  sel,
  period,
  tenant,
  assignExisting,
  newTenant,
  setErr,
  setNewTenant,
  pushToast,
  reload,
}: {
  tok: string | null;
  detail: any;
  sel: { apartment_id: number } | null;
  period: { year: number; month: number };
  tenant: TenantForm;
  assignExisting: { tenant_id: string; start_date: string };
  newTenant: NewTenantForm;
  setErr: (message: string) => void;
  setNewTenant: Dispatch<SetStateAction<NewTenantForm>>;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  reload: () => Promise<unknown>;
}) {
  const saveTenantMutation = useMutation({
    mutationFn: async () => {
      if (!detail?.tenant) return;
      const contacts = tenant.contacts_text
        .split("\n")
        .map((x: string) => x.trim())
        .filter(Boolean)
        .map((line: string) => {
          const [name, relation, phone, note] = line.split("|");
          return {
            name: (name || "").trim(),
            relation: (relation || "").trim(),
            phone: normalizePhone(phone),
            note: (note || "").trim(),
          };
        })
        .filter((x: { name: string }) => x.name);

      await api(`/admin/tenants/${detail.tenant.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          full_name: tenant.full_name,
          primary_phone: normalizePhone(tenant.primary_phone) || null,
          email: tenant.email.trim() || null,
          phones: tenant.phones
            .split(",")
            .map((x: string) => normalizePhone(x))
            .filter(Boolean),
          contacts,
          bank_statement_name: tenant.bank_statement_name || null,
          rent_amount: tenant.rent_amount === "" ? null : Number(tenant.rent_amount),
          rent_currency: tenant.rent_currency || "UAH",
          passport_number: tenant.passport_number || null,
          passport_issued_by: tenant.passport_issued_by || null,
          passport_issue_date: tenant.passport_issue_date || null,
          passport_expiry_date: tenant.passport_expiry_date || null,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Дані орендаря збережено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося зберегти дані орендаря", "error"),
  });

  const assignTenantMutation = useMutation({
    mutationFn: async () => {
      if (!assignExisting.tenant_id) {
        throw new Error("Оберіть орендаря для призначення.");
      }
      if (!sel?.apartment_id) throw new Error("Нерухомість не обрана.");
      await api("/admin/tenancies", tok, {
        method: "POST",
        body: JSON.stringify({
          apartment_id: sel.apartment_id,
          tenant_id: Number(assignExisting.tenant_id),
          start_date: assignExisting.start_date || monthStart(period.year, period.month),
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Орендаря призначено", "success");
      await reload();
    },
    onError: (e: Error) => {
      const message = e.message || "Не вдалося призначити орендаря";
      setErr(message);
      pushToast(message, "error");
    },
  });

  const createTenantAndAssignMutation = useMutation({
    mutationFn: async () => {
      if (!newTenant.full_name.trim()) {
        throw new Error("Вкажіть ПІБ орендаря.");
      }
      if (!sel?.apartment_id) throw new Error("Нерухомість не обрана.");
      const accessCode = newTenant.access_code.trim() || `TENANT-${Date.now()}`;
      const created = await api<{ id: number }>("/admin/tenants", tok, {
        method: "POST",
        body: JSON.stringify({
          full_name: newTenant.full_name.trim(),
          phone: normalizePhone(newTenant.phone) || null,
          email: newTenant.email.trim() || null,
          access_code: accessCode,
        }),
      });
      await api(`/admin/tenants/${created.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          full_name: newTenant.full_name.trim(),
          primary_phone: normalizePhone(newTenant.phone) || null,
          email: newTenant.email.trim() || null,
          phones: [],
          contacts: [],
          bank_statement_name: newTenant.bank_statement_name || null,
          rent_amount: newTenant.rent_amount === "" ? null : Number(newTenant.rent_amount),
          rent_currency: newTenant.rent_currency || "UAH",
          passport_number: null,
          passport_issued_by: null,
          passport_issue_date: null,
          passport_expiry_date: null,
        }),
      });
      await api("/admin/tenancies", tok, {
        method: "POST",
        body: JSON.stringify({
          apartment_id: sel.apartment_id,
          tenant_id: created.id,
          start_date: newTenant.start_date || monthStart(period.year, period.month),
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Орендаря створено і призначено", "success");
      setNewTenant({
        full_name: "",
        phone: "",
        email: "",
        access_code: "",
        start_date: monthStart(period.year, period.month),
        rent_amount: "",
        rent_currency: "UAH",
        bank_statement_name: "",
      });
      await reload();
    },
    onError: (e: Error) => {
      const message = e.message || "Не вдалося створити орендаря";
      setErr(message);
      pushToast(message, "error");
    },
  });

  const createTenantOnlyMutation = useMutation({
    mutationFn: async () => {
      if (!newTenant.full_name.trim()) {
        throw new Error("Вкажіть ПІБ орендаря.");
      }
      const accessCode = newTenant.access_code.trim() || `TENANT-${Date.now()}`;
      const created = await api<{ id: number }>("/admin/tenants", tok, {
        method: "POST",
        body: JSON.stringify({
          full_name: newTenant.full_name.trim(),
          phone: normalizePhone(newTenant.phone) || null,
          email: newTenant.email.trim() || null,
          access_code: accessCode,
        }),
      });
      await api(`/admin/tenants/${created.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          full_name: newTenant.full_name.trim(),
          primary_phone: normalizePhone(newTenant.phone) || null,
          email: newTenant.email.trim() || null,
          phones: [],
          contacts: [],
          bank_statement_name: newTenant.bank_statement_name || null,
          rent_amount: newTenant.rent_amount === "" ? null : Number(newTenant.rent_amount),
          rent_currency: newTenant.rent_currency || "UAH",
          passport_number: null,
          passport_issued_by: null,
          passport_issue_date: null,
          passport_expiry_date: null,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Орендаря створено", "success");
      setNewTenant({
        full_name: "",
        phone: "",
        email: "",
        access_code: "",
        start_date: monthStart(period.year, period.month),
        rent_amount: "",
        rent_currency: "UAH",
        bank_statement_name: "",
      });
      await reload();
    },
    onError: (e: Error) => {
      const message = e.message || "Не вдалося створити орендаря";
      setErr(message);
      pushToast(message, "error");
    },
  });

  const updateTenantByIdMutation = useMutation({
    mutationFn: async ({
      tenantId,
      payload,
    }: {
      tenantId: number;
      payload: TenantProfilePayload;
    }) => {
      const contacts = payload.contacts_text
        .split("\n")
        .map((x: string) => x.trim())
        .filter(Boolean)
        .map((line: string) => {
          const [name, relation, phone, note] = line.split("|");
          return {
            name: (name || "").trim(),
            relation: (relation || "").trim(),
            phone: normalizePhone(phone),
            note: (note || "").trim(),
          };
        })
        .filter((x: { name: string }) => x.name);
      await api(`/admin/tenants/${tenantId}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          full_name: payload.full_name.trim(),
          primary_phone: normalizePhone(payload.primary_phone) || null,
          email: payload.email.trim() || null,
          phones: payload.phones
            .split(",")
            .map((x: string) => normalizePhone(x))
            .filter(Boolean),
          contacts,
          bank_statement_name: payload.bank_statement_name || null,
          rent_amount: payload.rent_amount === "" ? null : Number(payload.rent_amount),
          rent_currency: payload.rent_currency || "UAH",
          passport_number: payload.passport_number || null,
          passport_issued_by: payload.passport_issued_by || null,
          passport_issue_date: payload.passport_issue_date || null,
          passport_expiry_date: payload.passport_expiry_date || null,
          portal_enabled: payload.portal_enabled,
          can_submit_meter_readings: payload.can_submit_meter_readings,
          portal_password: payload.portal_password.trim() || null,
        }),
      });
    },
    onSuccess: async () => {
      pushToast("Дані орендаря оновлено", "success");
      await reload();
    },
    onError: (e: Error) => {
      const message = e.message || "Не вдалося оновити орендаря";
      setErr(message);
      pushToast(message, "error");
    },
  });

  const endTenancyMutation = useMutation({
    mutationFn: async ({ tenancyId, endDate }: { tenancyId: number; endDate: string }) => {
      const formData = new FormData();
      formData.set("end_date", endDate);
      await api(`/admin/tenancies/${tenancyId}/end`, tok, {
        method: "PUT",
        body: formData,
      });
    },
    onSuccess: async () => {
      pushToast("Оренду завершено", "success");
      await reload();
    },
    onError: (e: Error) => {
      const message = e.message || "Не вдалося завершити оренду";
      setErr(message);
      pushToast(message, "error");
    },
  });

  const deleteTenantByIdMutation = useMutation({
    mutationFn: async (tenantId: number) =>
      api(`/admin/tenants/${tenantId}`, tok, {
        method: "DELETE",
      }),
    onSuccess: async () => {
      pushToast("Орендаря видалено", "success");
      await reload();
    },
    onError: (e: Error) => {
      const message = e.message || "Не вдалося видалити орендаря";
      setErr(message);
      pushToast(message, "error");
    },
  });

  const saveTenant = async () => {
    await saveTenantMutation.mutateAsync();
  };

  const assignTenant = async () => {
    await assignTenantMutation.mutateAsync();
  };

  const createTenantAndAssign = async () => {
    await createTenantAndAssignMutation.mutateAsync();
  };

  const createTenantOnly = async () => {
    await createTenantOnlyMutation.mutateAsync();
  };

  const updateTenantById = async (tenantId: number, payload: TenantProfilePayload) => {
    await updateTenantByIdMutation.mutateAsync({ tenantId, payload });
  };

  const saveRentalTerms = async (payload: {
    tenantId: number;
    fullName: string;
    primaryPhone: string;
    email: string;
    rentAmount: string;
    rentCurrency: "UAH" | "USD" | "EUR";
  }) => {
    const currentTenant = detail?.tenant || {};
    const contacts = (currentTenant.contacts || [])
      .map((x: any) => `${x.name || ""}|${x.relation || ""}|${x.phone || ""}|${x.note || ""}`)
      .join("\n");
    await updateTenantByIdMutation.mutateAsync({
      tenantId: payload.tenantId,
      payload: {
        full_name: payload.fullName,
        primary_phone: payload.primaryPhone,
        email: payload.email,
        phones: (currentTenant.phones || []).join(", "),
        contacts_text: contacts,
        bank_statement_name: currentTenant.bank_statement_name || "",
        rent_amount: payload.rentAmount,
        rent_currency: payload.rentCurrency,
        passport_number: currentTenant.passport_number || "",
        passport_issued_by: currentTenant.passport_issued_by || "",
        passport_issue_date: currentTenant.passport_issue_date || "",
        passport_expiry_date: currentTenant.passport_expiry_date || "",
        portal_enabled: Boolean(currentTenant.portal_enabled),
        can_submit_meter_readings: Boolean(currentTenant.can_submit_meter_readings),
        portal_password: "",
      },
    });
  };

  const endTenancy = async (tenancyId: number, endDate: string) => {
    await endTenancyMutation.mutateAsync({ tenancyId, endDate });
  };

  const deleteTenantById = async (tenantId: number) => {
    await deleteTenantByIdMutation.mutateAsync(tenantId);
  };

  return {
    saveTenant,
    assignTenant,
    createTenantAndAssign,
    createTenantOnly,
    updateTenantById,
    saveRentalTerms,
    endTenancy,
    deleteTenantById,
  };
}
