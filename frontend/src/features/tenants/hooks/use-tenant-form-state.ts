import { useState } from "react";
import { todayIso } from "@/shared/utils/date";

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

export function useTenantFormState() {
  const [tenant, setTenant] = useState<TenantForm>({
    full_name: "",
    primary_phone: "",
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
  const [tenants, setTenants] = useState<Array<{ id: number; full_name: string }>>([]);
  const [newTenant, setNewTenant] = useState<NewTenantForm>({
    full_name: "",
    phone: "",
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

  return {
    tenant,
    setTenant,
    tenants,
    setTenants,
    newTenant,
    setNewTenant,
    assignExisting,
    setAssignExisting,
  };
}
