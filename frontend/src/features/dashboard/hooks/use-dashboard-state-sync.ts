import { useEffect } from "react";
import { formatPhone, monthStart } from "@/shared/utils/format";
import { todayIso } from "@/shared/utils/date";
import type { BillingHistoryItem } from "@/shared/api/types";

type SetState<T> = (value: T | ((prev: T) => T)) => void;

export function useDashboardStateSync({
  detailBundleData,
  setDetail,
  setHistory,
  setOc,
  setMr,
  setEquipment,
  setPayments,
  setTenants,
  setTenancies,
  setAp,
  setPay,
  setTenant,
  period,
  setNewTenant,
  setAssignExisting,
}: {
  detailBundleData?: any;
  setDetail: SetState<any>;
  setHistory: SetState<BillingHistoryItem[]>;
  setOc: SetState<any>;
  setMr: SetState<any>;
  setEquipment: SetState<any>;
  setPayments: SetState<any>;
  setTenants: SetState<any>;
  setTenancies: SetState<any>;
  setAp: SetState<any>;
  setPay: SetState<any>;
  setTenant: SetState<any>;
  period: { year: number; month: number };
  setNewTenant: SetState<any>;
  setAssignExisting: SetState<any>;
}) {
  useEffect(() => {
    if (!detailBundleData) return;
    const { d, equipment, payments, tenancies, o, m, allTenants, h } = detailBundleData;
    setDetail(d);
    setHistory(h || []);
    setOc(o);
    setMr(m);
    setEquipment(equipment || []);
    setPayments(payments || []);
    setTenants(allTenants || []);
    setTenancies(tenancies || []);
    setAp({
      country: d.country || "Україна",
      region: d.region || "",
      locality: d.locality || "",
      street: d.street || "",
      house_number: d.house_number || "",
      apartment_number: d.apartment_number || "",
      postal_code: d.postal_code || "",
      address: d.address || "",
      short_address: d.short_address || "",
      registered_residents:
        d.registered_residents !== null && d.registered_residents !== undefined
          ? String(d.registered_residents)
          : "1",
      area_m2: d.area_m2 !== null && d.area_m2 !== undefined ? String(d.area_m2) : "",
      living_area_m2: d.living_area_m2 !== null && d.living_area_m2 !== undefined ? String(d.living_area_m2) : "",
      entrance: d.entrance || "",
      floor: d.floor || "",
      room_count: d.room_count !== null && d.room_count !== undefined ? String(d.room_count) : "",
      latitude: d.latitude !== null && d.latitude !== undefined ? String(d.latitude) : "",
      longitude: d.longitude !== null && d.longitude !== undefined ? String(d.longitude) : "",
      google_maps_url: d.google_maps_url || "",
      location_note: d.location_note || "",
      object_notes: d.object_notes || "",
    });
    setPay({
      amount: d.utility_balance.month_payments || "",
      paid_at: d.utility_balance.month_payment_date || todayIso(),
      note: d.utility_balance.month_payment_note || "",
    });
    if (d.tenant) {
      setTenant({
        full_name: d.tenant.full_name || "",
        primary_phone: formatPhone(d.tenant.phone || ""),
        email: d.tenant.email || "",
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
    }
  }, [detailBundleData, setAp, setDetail, setEquipment, setHistory, setMr, setOc, setPay, setPayments, setTenant, setTenancies, setTenants]);

  useEffect(() => {
    const start = monthStart(period.year, period.month);
    setNewTenant((s: any) => ({ ...s, start_date: start }));
    setAssignExisting((s: any) => ({ ...s, start_date: start }));
  }, [period.year, period.month, setAssignExisting, setNewTenant]);
}
