import { useEffect } from "react";
import { formatPhone, monthStart } from "@/shared/utils/format";
import { todayIso } from "@/shared/utils/date";
import type { BillingHistoryItem } from "@/shared/api/types";

type SetState<T> = (value: T | ((prev: T) => T)) => void;

export function useDashboardStateSync({
  detailBundleData,
  setDetail,
  setHistory,
  setTar,
  setOc,
  setMr,
  setTenants,
  setAp,
  setPay,
  setTenant,
  period,
  setNewTar,
  setNewTenant,
  setAssignExisting,
}: {
  detailBundleData?: any;
  setDetail: SetState<any>;
  setHistory: SetState<BillingHistoryItem[]>;
  setTar: SetState<any>;
  setOc: SetState<any>;
  setMr: SetState<any>;
  setTenants: SetState<any>;
  setAp: SetState<any>;
  setPay: SetState<any>;
  setTenant: SetState<any>;
  period: { year: number; month: number };
  setNewTar: SetState<any>;
  setNewTenant: SetState<any>;
  setAssignExisting: SetState<any>;
}) {
  useEffect(() => {
    if (!detailBundleData) return;
    const { d, t, o, m, allTenants, h } = detailBundleData;
    setDetail(d);
    setHistory(h || []);
    setTar(t);
    setOc(o);
    setMr(m);
    setTenants(allTenants || []);
    setAp({ address: d.address || "" });
    setPay({
      amount: d.utility_balance.month_payments || "",
      paid_at: d.utility_balance.month_payment_date || todayIso(),
      note: d.utility_balance.month_payment_note || "",
    });
    if (d.tenant) {
      setTenant({
        full_name: d.tenant.full_name || "",
        primary_phone: formatPhone(d.tenant.phone || ""),
        phones: (d.tenant.phones || []).map((x: string) => formatPhone(x)).join(", "),
        contacts_text: (d.tenant.contacts || [])
          .map(
            (c: { name?: string; relation?: string; phone?: string; note?: string }) =>
              `${c.name}|${c.relation || ""}|${formatPhone(c.phone || "")}|${c.note || ""}`,
          )
          .join("\n"),
        bank_statement_name: d.tenant.bank_statement_name || "",
        rent_amount: d.tenant.rent_amount || "",
        rent_currency: d.tenant.rent_currency || "UAH",
        passport_number: d.tenant.passport_number || "",
        passport_issued_by: d.tenant.passport_issued_by || "",
        passport_issue_date: d.tenant.passport_issue_date || "",
        passport_expiry_date: d.tenant.passport_expiry_date || "",
      });
    } else {
      setTenant({
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
    }
  }, [detailBundleData, setAp, setDetail, setHistory, setMr, setOc, setPay, setTar, setTenant, setTenants]);

  useEffect(() => {
    const start = monthStart(period.year, period.month);
    setNewTar((s: any) => ({
      ...s,
      effective_from: start,
      disable_from_month: `${period.year}-${String(period.month).padStart(2, "0")}`,
    }));
    setNewTenant((s: any) => ({ ...s, start_date: start }));
    setAssignExisting((s: any) => ({ ...s, start_date: start }));
  }, [period.year, period.month, setAssignExisting, setNewTar, setNewTenant]);
}
