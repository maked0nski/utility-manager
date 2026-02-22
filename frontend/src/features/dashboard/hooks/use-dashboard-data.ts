import { useCallback, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { SELECTED_APARTMENT_KEY } from "@/shared/constants/app";
import type { BillingHistoryItem } from "@/shared/api/types";

type Period = { year: number; month: number };
type ApartmentSummary = {
  apartment_id: number;
  code?: string;
  address?: string;
  total_balance?: string | number;
};
type DetailBundle = {
  d: { address?: string; apartment_id: number; utility_balance: Record<string, string>; tenant?: unknown };
  t: unknown[];
  meters: Array<{ id: number; service_name: string; serial_number?: string | null }>;
  o: unknown[];
  m: unknown[];
  allTenants: unknown[];
  h: BillingHistoryItem[];
};

interface UseDashboardDataParams {
  tok: string | null;
  sel: ApartmentSummary | null;
  setSel: (v: ApartmentSummary | null) => void;
  period: Period;
  selectedApartmentId: number | null;
  setSelectedApartmentId: (v: number | null) => void;
  adminsModal: boolean;
  setErr: (message: string) => void;
  pushToast: (message: string, kind?: "success" | "error") => void;
}

export function useDashboardData({
  tok,
  sel,
  setSel,
  period,
  selectedApartmentId,
  setSelectedApartmentId,
  adminsModal,
  setErr,
  pushToast,
}: UseDashboardDataParams) {
  const queryClient = useQueryClient();

  const apartmentsQuery = useQuery<ApartmentSummary[], Error>({
    queryKey: ["dashboard-apartments", tok],
    enabled: !!tok,
    queryFn: async () => api<ApartmentSummary[]>("/admin/dashboard/apartments", tok),
  });

  const detailBundleQuery = useQuery<DetailBundle, Error>({
    queryKey: ["apartment-detail-bundle", tok, sel?.apartment_id, period.year, period.month],
    enabled: !!tok && !!sel?.apartment_id,
    queryFn: async () => {
      const id = sel?.apartment_id;
      if (!id) throw new Error("Apartment is not selected");
      const [d, t, meters, o, m, allTenants, h] = await Promise.all([
        api(`/admin/dashboard/apartments/${id}?year=${period.year}&month=${period.month}`, tok),
        api(`/admin/apartments/${id}/tariffs?year=${period.year}&month=${period.month}`, tok),
        api(`/admin/apartments/${id}/meters`, tok),
        api(`/admin/apartments/${id}/owner-charges`, tok),
        api(`/admin/apartments/${id}/maintenance`, tok),
        api("/admin/tenants", tok),
        api(`/admin/billing/history?apartment_id=${id}&year=${period.year}&month=${period.month}&limit=100`, tok),
      ]);
      return { d, t, meters, o, m, allTenants, h } as DetailBundle;
    },
  });

  const adminUsersQuery = useQuery<unknown[], Error>({
    queryKey: ["admin-users", tok],
    enabled: !!tok && adminsModal,
    queryFn: async () => api<unknown[]>("/auth/admin/users", tok),
  });

  const invalidateApartmentQueries = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["dashboard-apartments", tok] });
    await queryClient.invalidateQueries({
      queryKey: ["apartment-detail-bundle", tok, sel?.apartment_id, period.year, period.month],
    });
  }, [queryClient, tok, sel?.apartment_id, period.year, period.month]);

  const reload = useCallback(async () => {
    await apartmentsQuery.refetch();
    if (sel?.apartment_id) await detailBundleQuery.refetch();
  }, [apartmentsQuery, detailBundleQuery, sel?.apartment_id]);

  useEffect(() => {
    const apartments = apartmentsQuery.data;
    if (!apartments) return;
    if (!sel && apartments.length) {
      const savedId =
        selectedApartmentId || Number(localStorage.getItem(SELECTED_APARTMENT_KEY) || 0);
      const byBalance = [...apartments].sort(
        (a, b) => Math.abs(Number(b.total_balance || 0)) - Math.abs(Number(a.total_balance || 0)),
      );
      const preferred =
        apartments.find((x) => x.apartment_id === savedId) || byBalance[0] || apartments[0];
      setSel(preferred);
    }
  }, [apartmentsQuery.data, sel, setSel, selectedApartmentId]);

  useEffect(() => {
    if (apartmentsQuery.error) {
      setErr(apartmentsQuery.error.message || "Не вдалося завантажити нерухомість.");
    }
  }, [apartmentsQuery.error, setErr]);

  useEffect(() => {
    if (detailBundleQuery.error) {
      setErr(detailBundleQuery.error.message || "Не вдалося завантажити деталі об'єкта.");
    }
  }, [detailBundleQuery.error, setErr]);

  useEffect(() => {
    if (!adminsModal || !adminUsersQuery.error) return;
    pushToast(adminUsersQuery.error.message || "Немає доступу до керування користувачами.", "error");
  }, [adminsModal, adminUsersQuery.error, pushToast]);

  useEffect(() => {
    if (!sel?.apartment_id) return;
    localStorage.setItem(SELECTED_APARTMENT_KEY, String(sel.apartment_id));
    setSelectedApartmentId(sel.apartment_id);
  }, [sel?.apartment_id, setSelectedApartmentId]);

  return {
    apartmentsQuery,
    detailBundleQuery,
    adminUsersQuery,
    apartments: apartmentsQuery.data || [],
    invalidateApartmentQueries,
    reload,
  };
}
