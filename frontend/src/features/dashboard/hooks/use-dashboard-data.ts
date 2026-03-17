import { useCallback, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { SELECTED_APARTMENT_KEY } from "@/shared/constants/app";
import type {
  ApartmentEquipmentItem,
  BillingHistoryItem,
  MeterItem,
  TenancyHistoryItem,
  UtilityPaymentItem,
} from "@/shared/api/types";

type Period = { year: number; month: number };
type ApartmentSummary = {
  apartment_id: number;
  code?: string;
  address?: string;
  short_address?: string;
  total_balance?: string | number;
};
type DetailBundle = {
  d: {
    address?: string;
    short_address?: string;
    apartment_id: number;
    utility_balance: Record<string, string>;
    tenant?: unknown;
  };
  meters: MeterItem[];
  equipment: ApartmentEquipmentItem[];
  tenancies: TenancyHistoryItem[];
  payments: UtilityPaymentItem[];
  o: unknown[];
  m: unknown[];
  allTenants: unknown[];
  h: BillingHistoryItem[];
};
type StaticDetailBundle = Omit<DetailBundle, "d" | "h">;
type PeriodDetailBundle = Pick<DetailBundle, "d" | "h">;

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
  const apartmentId = sel?.apartment_id ?? null;

  const apartmentsQuery = useQuery<ApartmentSummary[], Error>({
    queryKey: ["dashboard-apartments", tok],
    enabled: !!tok,
    queryFn: async () => api<ApartmentSummary[]>("/admin/dashboard/apartments", tok),
  });

  const detailBundleQuery = useQuery<StaticDetailBundle, Error>({
    queryKey: ["apartment-detail-bundle", tok, apartmentId],
    enabled: !!tok && !!apartmentId,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const id = apartmentId;
      if (!id) throw new Error("Apartment is not selected");
      const [meters, equipment, tenancies, payments, o, m, allTenants] = await Promise.all([
        api(`/admin/apartments/${id}/meters`, tok),
        api(`/admin/apartments/${id}/equipment`, tok),
        api(`/admin/apartments/${id}/tenancies`, tok),
        api(`/admin/apartments/${id}/utility-payments`, tok),
        api(`/admin/apartments/${id}/owner-charges`, tok),
        api(`/admin/apartments/${id}/maintenance`, tok),
        api("/admin/tenants", tok),
      ]);
      return { meters, equipment, tenancies, payments, o, m, allTenants } as StaticDetailBundle;
    },
  });

  const periodDetailQuery = useQuery<PeriodDetailBundle, Error>({
    queryKey: ["apartment-detail-bundle", tok, apartmentId, period.year, period.month],
    enabled: !!tok && !!apartmentId,
    placeholderData: (previousData) => previousData,
    queryFn: async () => {
      const id = apartmentId;
      if (!id) throw new Error("Apartment is not selected");
      const [d, h] = await Promise.all([
        api(`/admin/dashboard/apartments/${id}?year=${period.year}&month=${period.month}`, tok),
        api(`/admin/billing/history?apartment_id=${id}&year=${period.year}&month=${period.month}&limit=100`, tok),
      ]);
      return { d, h } as PeriodDetailBundle;
    },
  });

  const detailBundleData = useMemo(() => {
    if (!detailBundleQuery.data || !periodDetailQuery.data) return undefined;
    return {
      ...detailBundleQuery.data,
      ...periodDetailQuery.data,
    } as DetailBundle;
  }, [detailBundleQuery.data, periodDetailQuery.data]);

  useEffect(() => {
    if (!tok || !apartmentId || !periodDetailQuery.data) return;
    const neighbors = [
      period.month === 1 ? { year: period.year - 1, month: 12 } : { year: period.year, month: period.month - 1 },
      period.month === 12 ? { year: period.year + 1, month: 1 } : { year: period.year, month: period.month + 1 },
    ];
    for (const neighbor of neighbors) {
      void queryClient.prefetchQuery({
        queryKey: ["apartment-detail-bundle", tok, apartmentId, neighbor.year, neighbor.month],
        staleTime: 60 * 1000,
        queryFn: async () => {
          const [d, h] = await Promise.all([
            api(`/admin/dashboard/apartments/${apartmentId}?year=${neighbor.year}&month=${neighbor.month}`, tok),
            api(
              `/admin/billing/history?apartment_id=${apartmentId}&year=${neighbor.year}&month=${neighbor.month}&limit=100`,
              tok,
            ),
          ]);
          return { d, h } as PeriodDetailBundle;
        },
      });
    }
  }, [queryClient, tok, apartmentId, period.year, period.month, periodDetailQuery.data]);

  const adminUsersQuery = useQuery<unknown[], Error>({
    queryKey: ["admin-users", tok],
    enabled: !!tok && adminsModal,
    queryFn: async () => api<unknown[]>("/auth/admin/users", tok),
  });

  const invalidateApartmentQueries = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["dashboard-apartments", tok] });
    await queryClient.invalidateQueries({ queryKey: ["apartment-detail-bundle", tok, apartmentId] });
    await queryClient.invalidateQueries({
      queryKey: ["apartment-detail-bundle", tok, apartmentId, period.year, period.month],
    });
  }, [queryClient, tok, apartmentId, period.year, period.month]);

  const reload = useCallback(async () => {
    await apartmentsQuery.refetch();
    if (apartmentId) {
      await detailBundleQuery.refetch();
      await periodDetailQuery.refetch();
    }
  }, [apartmentsQuery, detailBundleQuery, periodDetailQuery, apartmentId]);

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
    if (detailBundleQuery.error || periodDetailQuery.error) {
      setErr(
        detailBundleQuery.error?.message ||
          periodDetailQuery.error?.message ||
          "Не вдалося завантажити деталі об'єкта.",
      );
    }
  }, [detailBundleQuery.error, periodDetailQuery.error, setErr]);

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
    detailBundleQuery: {
      data: detailBundleData,
      isFetching: detailBundleQuery.isFetching || periodDetailQuery.isFetching,
      error: detailBundleQuery.error || periodDetailQuery.error,
    },
    detailBundleData,
    adminUsersQuery,
    apartments: apartmentsQuery.data || [],
    invalidateApartmentQueries,
    reload,
  };
}
