import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { monthStart, normalizePhone } from "@/shared/utils/format";
import type { Dispatch, SetStateAction } from "react";

type TenantForm = {
  full_name: string;
  primary_phone: string;
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
  access_code: string;
  start_date: string;
  rent_amount: string;
  rent_currency: "UAH" | "USD" | "EUR";
  bank_statement_name: string;
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
    onError: (e: Error) => setErr(e.message || "Не вдалося призначити орендаря"),
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
          access_code: accessCode,
        }),
      });
      await api(`/admin/tenants/${created.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({
          full_name: newTenant.full_name.trim(),
          primary_phone: normalizePhone(newTenant.phone) || null,
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
        access_code: "",
        start_date: monthStart(period.year, period.month),
        rent_amount: "",
        rent_currency: "UAH",
        bank_statement_name: "",
      });
      await reload();
    },
    onError: (e: Error) => setErr(e.message || "Не вдалося створити орендаря"),
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

  return { saveTenant, assignTenant, createTenantAndAssign };
}
