import { useState } from "react";
import { todayIso } from "@/shared/utils/date";

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

type TenancyHistoryItem = {
  id: number;
  start_date: string;
  end_date: string | null;
  tenant: { id: number; full_name: string } | null;
};

export function useTenantFormState() {
  const [tenant, setTenant] = useState<TenantForm>({
    full_name: "",
    primary_phone: "",
    email: "",
    phones: "",
    contacts_text: "",
    bank_statement_name: "",
    rent_amount: "",
    rent_currency: "UAH",
    passport_number: "",
    passport_issued_by: "",
    passport_issue_date: "",
    passport_expiry_date: "",
  });
  const [tenants, setTenants] = useState<
    Array<{
      id: number;
      full_name: string;
      phone?: string | null;
      email?: string | null;
      access_code?: string;
      bank_statement_name?: string | null;
      rent_amount?: string | number | null;
      rent_currency?: "UAH" | "USD" | "EUR";
      passport_number?: string | null;
      passport_issued_by?: string | null;
      passport_issue_date?: string | null;
      passport_expiry_date?: string | null;
      phones?: string[];
      contacts?: Array<{ id?: number; name: string; relation?: string | null; phone?: string | null; note?: string | null }>;
      is_active_now?: boolean;
    }>
  >([]);
  const [newTenant, setNewTenant] = useState<NewTenantForm>({
    full_name: "",
    phone: "",
    email: "",
    access_code: "",
    start_date: todayIso(),
    rent_amount: "",
    rent_currency: "UAH",
    bank_statement_name: "",
  });
  const [assignExisting, setAssignExisting] = useState<{
    tenant_id: string;
    start_date: string;
  }>({
    tenant_id: "",
    start_date: todayIso(),
  });
  const [tenancies, setTenancies] = useState<TenancyHistoryItem[]>([]);
  const [tenancyEndDate, setTenancyEndDate] = useState(todayIso());

  return {
    tenant,
    setTenant,
    tenants,
    setTenants,
    newTenant,
    setNewTenant,
    assignExisting,
    setAssignExisting,
    tenancies,
    setTenancies,
    tenancyEndDate,
    setTenancyEndDate,
  };
}
