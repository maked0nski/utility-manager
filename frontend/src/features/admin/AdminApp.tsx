import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { asInt, dt, money, periodLabel } from "@/shared/utils/format";
import { calculateAccrualTotal, calculatePortfolioTotals } from "@/shared/utils/billing-selectors";
import { useBillingActions } from "@/features/calculation/hooks/use-billing-actions";
import { useRowEditing } from "@/features/calculation/hooks/use-row-editing";
import { useTenantActions } from "@/features/tenants/hooks/use-tenant-actions";
import { useTenantFormState } from "@/features/tenants/hooks/use-tenant-form-state";
import { useOwnerActions } from "@/features/expenses/hooks/use-owner-actions";
import { useOwnerFormState } from "@/features/expenses/hooks/use-owner-form-state";
import { useSession } from "@/shared/hooks/use-session";
import { usePeriod } from "@/shared/hooks/use-period";
import { useAppStore } from "@/shared/store/app-store";
import { LoginScreen } from "@/features/auth/components/LoginScreen";
import { AdminHeader } from "@/features/layout/components/AdminHeader";
import { useUiState } from "@/features/layout/hooks/use-ui-state";
import { useModalState } from "@/features/layout/hooks/use-modal-state";
import { useDashboardData } from "@/features/dashboard/hooks/use-dashboard-data";
import { useDashboardStateSync } from "@/features/dashboard/hooks/use-dashboard-state-sync";
import { useSortedRows } from "@/features/calculation/hooks/use-sorted-rows";
import { usePropertyActions } from "@/features/properties/hooks/use-property-actions";
import { useMeterActions } from "@/features/properties/hooks/use-meter-actions";
import { useEquipmentActions } from "@/features/properties/hooks/use-equipment-actions";
import { PropertyDrawer } from "@/features/properties/components/PropertyDrawer";
import { DashboardContent } from "@/features/layout/components/DashboardContent";
import { AppModals } from "@/features/layout/components/AppModals";
import { ProfileSettingsModal } from "@/features/layout/components/ProfileSettingsModal";
import { useAdminUserActions } from "@/features/auth/hooks/use-admin-user-actions";
import { useAuthActions } from "@/features/auth/hooks/use-auth-actions";
import { usePaymentActions } from "@/features/payments/hooks/use-payment-actions";
import { useTheme } from "@/shared/hooks/use-theme";
import { isPeriodAfterMaxAllowed } from "@/shared/utils/date";
import type {
  AutomationItem,
  AutomationCycleRunResult,
  AutomationCycleRunDetailResult,
  AutomationCyclePreviewResult,
  AutomationRunLogItem,
  AutomationTemplateItem,
  ApartmentEquipmentForm,
  ApartmentEquipmentItem,
  ApartmentProfileForm,
  ApartmentServiceConnectionItem,
  BillingHistoryItem,
  ChargeLineKind,
  MeterSubmitDispatchResult,
  MeterSubmitEvaluateResult,
  MeterExpectedRegistersResult,
  MeterReplacementForm,
  MeterTypeItem,
  MeterUpsertForm,
  ProviderItem,
  QuantitySource,
  ServiceCalculationKind,
  ServiceCatalogItem,
  UtilityType,
} from "@/shared/api/types";
import { api } from "@/shared/api/client";

type SelectedApartment = {
  apartment_id: number;
  code?: string;
  address?: string;
  short_address?: string;
  total_balance?: string | number;
};
type DetailLike = {
  tenant?: {
    id?: number;
    full_name?: string;
    phone?: string | null;
    email?: string | null;
  } | null;
  rows?: Array<{
    service_name: string;
    meter_id: number | null;
    previous_reading: string | null;
    current_reading: string | null;
    difference: string | null;
    unit_name: string;
    unit_price: string;
    amount: string;
    can_edit_previous?: boolean;
  }>;
  calc_locked?: boolean;
};

export function AdminApp() {
  const queryClient = useQueryClient();
  const { token: tok, saveToken, clearToken, sessionError, setSessionError } = useSession();
  const { theme, cycleTheme } = useTheme();
  const { period: p, setPeriod, shiftPeriod } = usePeriod();
  const selectedApartmentId = useAppStore((s) => s.selectedApartmentId);
  const setSelectedApartmentId = useAppStore((s) => s.setSelectedApartmentId);
  const {
    cred,
    setCred,
    initialAdmin,
    setInitialAdmin,
    boot,
    setBoot,
    tab,
    setTab,
    err,
    setErr,
    drawer,
    setDrawer,
    pay,
    setPay,
    pwd,
    setPwd,
  } = useUiState();
  const {
    payModal,
    setPayModal,
    pwdModal,
    setPwdModal,
    adminsModal,
    setAdminsModal,
    toasts,
    setToasts,
    confirm,
    setConfirm,
    pushToast,
  } = useModalState();
  const [sel, setSel] = useState<SelectedApartment | null>(null);
  const [detail, setDetail] = useState<DetailLike | null>(null);
  const [history, setHistory] = useState<BillingHistoryItem[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const {
    oc,
    setOc,
    mr,
    setMr,
    own,
    setOwn,
    mnt,
    setMnt,
    ocModal,
    setOcModal,
    ocForm,
    setOcForm,
    mrModal,
    setMrModal,
    mrForm,
    setMrForm,
  } = useOwnerFormState();
  const {
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
  } = useTenantFormState();
  const [rentalTerms, setRentalTerms] = useState<{ rent_amount: string; rent_currency: "UAH" | "USD" | "EUR" }>({
    rent_amount: "",
    rent_currency: "UAH",
  });
  const [ap, setAp] = useState<ApartmentProfileForm>({
    country: "Україна",
    region: "",
    locality: "",
    street: "",
    house_number: "",
    apartment_number: "",
    postal_code: "",
    address: "",
    short_address: "",
    registered_residents: "1",
    area_m2: "",
    living_area_m2: "",
    entrance: "",
    floor: "",
    room_count: "",
    latitude: "",
    longitude: "",
    google_maps_url: "",
    location_note: "",
    object_notes: "",
  });
  const [equipment, setEquipment] = useState<ApartmentEquipmentItem[]>([]);
  const [equipmentForm, setEquipmentForm] = useState<ApartmentEquipmentForm>({
    name: "",
    category: "other",
    model_name: "",
    serial_number: "",
    installed_at: "",
    manual_url: "",
    service_interval_days: "",
    last_service_at: "",
    next_service_at: "",
    note: "",
    is_active: true,
  });
  const [editingEquipmentId, setEditingEquipmentId] = useState<number | null>(null);
  const [meterForm, setMeterForm] = useState<MeterUpsertForm>({
    meter_type_id: "",
    serial_number: "",
    installed_at: "",
  });
  const [editingMeterId, setEditingMeterId] = useState<number | null>(null);
  const [replacingMeterId, setReplacingMeterId] = useState<number | null>(null);
  const [replacementForm, setReplacementForm] = useState<MeterReplacementForm>({
    serial_number: "",
    initial_reading: "",
    installed_at: "",
  });
  const [batchReadingModalOpen, setBatchReadingModalOpen] = useState(false);
  const [batchReadingMetas, setBatchReadingMetas] = useState<Record<string, MeterExpectedRegistersResult>>({});
  const [batchReadingDraft, setBatchReadingDraft] = useState<Record<string, Record<string, string>>>({});
  const [batchReadingSaving, setBatchReadingSaving] = useState(false);
  const [profileSettingsOpen, setProfileSettingsOpen] = useState(false);
  const confirmActionRef = useRef<null | (() => void | Promise<void>)>(null);
  const {
    apartmentsQuery,
    detailBundleQuery,
    adminUsersQuery,
    apartments: props,
    invalidateApartmentQueries,
    reload,
  } = useDashboardData({
    tok,
    sel,
    setSel,
    period: p,
    selectedApartmentId,
    setSelectedApartmentId,
    adminsModal,
    setErr,
    pushToast,
  });
  const { sortedRows, toggleSort, sortIcon, resetSortDefault } = useSortedRows(detail?.rows || []);
  const meters = detailBundleQuery.data?.meters || [];
  const automationsQuery = useQuery({
    queryKey: ["admin", "automations", tok],
    enabled: !!tok,
    queryFn: () => api<AutomationItem[]>("/admin/automations", tok),
  });
  const providersQuery = useQuery({
    queryKey: ["admin", "providers", tok],
    enabled: !!tok,
    queryFn: () => api<ProviderItem[]>("/admin/providers", tok),
  });
  const meterTypesQuery = useQuery({
    queryKey: ["admin", "meter-types", tok],
    enabled: !!tok,
    queryFn: () => api<MeterTypeItem[]>("/admin/meter-types", tok),
  });
  const serviceCatalogQuery = useQuery({
    queryKey: ["admin", "service-catalog", tok],
    enabled: !!tok,
    queryFn: () => api<ServiceCatalogItem[]>("/admin/service-catalog", tok),
  });
  const serviceConnectionsQuery = useQuery({
    queryKey: ["admin", "service-connections", tok, sel?.apartment_id],
    enabled: !!tok && !!sel?.apartment_id,
    queryFn: () =>
      api<ApartmentServiceConnectionItem[]>(`/admin/apartments/${sel?.apartment_id}/service-connections`, tok),
  });
  const automationTemplatesQuery = useQuery({
    queryKey: ["admin", "automation-templates", tok],
    enabled: !!tok,
    queryFn: () => api<AutomationTemplateItem[]>("/admin/automation-templates", tok),
  });
  const automationCycleRunsQuery = useQuery({
    queryKey: ["admin", "automation-cycle-runs", tok],
    enabled: !!tok,
    queryFn: () => api<AutomationCycleRunResult[]>("/admin/automations/cycle-runs?limit=20", tok),
  });
  const totals = useMemo(() => calculatePortfolioTotals(props), [props]);
  const accr = useMemo(() => calculateAccrualTotal(detail?.rows || []), [detail?.rows]);
  const maxPeriodInput = useMemo(() => {
    const now = new Date();
    const maxDate = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    return `${maxDate.getFullYear()}-${String(maxDate.getMonth() + 1).padStart(2, "0")}`;
  }, []);

  useEffect(() => {
    if (sessionError) setErr(sessionError);
  }, [sessionError]);
  useEffect(() => {
    const tenant = (detailBundleQuery.data as any)?.d?.tenant as any;
    setRentalTerms({
      rent_amount: tenant?.rent_amount ? String(tenant.rent_amount) : "",
      rent_currency: tenant?.rent_currency || "UAH",
    });
  }, [
    (detailBundleQuery.data as any)?.d?.tenant?.id,
    (detailBundleQuery.data as any)?.d?.tenant?.rent_amount,
    (detailBundleQuery.data as any)?.d?.tenant?.rent_currency,
  ]);
  useEffect(() => {
    setEditingMeterId(null);
    setMeterForm({
      meter_type_id: "",
      serial_number: "",
      installed_at: "",
    });
    setReplacingMeterId(null);
    setReplacementForm({
      serial_number: "",
      initial_reading: "",
      installed_at: "",
    });
    setEditingEquipmentId(null);
    setEquipmentForm({
      name: "",
      category: "other",
      model_name: "",
      serial_number: "",
      installed_at: "",
      manual_url: "",
      service_interval_days: "",
      last_service_at: "",
      next_service_at: "",
      note: "",
      is_active: true,
    });
  }, [sel?.apartment_id]);

  const confirmRun = (title: string, message: string, action: () => void | Promise<void>) => {
    confirmActionRef.current = action;
    setConfirm({ open: true, title, message });
  };
  const { login, out, changePassword, registerInitialAdmin } = useAuthActions({
    tok,
    cred,
    initialAdmin,
    pwd,
    setErr,
    setBoot,
    saveToken,
    clearToken,
    setSel,
    setSessionError,
    setPwdModal,
    setPwd,
    pushToast,
  });

  const { createAdminUserMutation, updateAdminUserMutation, changeAdminPasswordMutation } =
    useAdminUserActions({
      tok,
      queryClient,
      pushToast,
    });

  useDashboardStateSync({
    detailBundleData: detailBundleQuery.data,
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
    period: p,
    setNewTenant,
    setAssignExisting,
  });
  const { editSrv, setEditSrv, draft, setDraft, editRef, start, changed } = useRowEditing({
    asInt,
  });

  const { savePay, saveRow, recalcMonth, confirmMonth, reopenMonth } = useBillingActions({
    tok,
    apartmentId: sel?.apartment_id,
    period: p,
    pay,
    draft,
    setEditSrv,
    setDraft,
    setPayModal,
    pushToast,
    confirmRun,
    reload,
    invalidateApartmentQueries,
    calcLocked: detail?.calc_locked,
  });
  const {
    assignTenant,
    createTenantAndAssign,
    createTenantOnly,
    updateTenantById,
    saveTenant,
    saveRentalTerms,
    endTenancy,
    deleteTenantById,
  } =
    useTenantActions({
      tok,
      detail,
      sel,
      period: p,
      tenant,
      assignExisting,
      newTenant,
      setErr,
      setNewTenant,
      pushToast,
      reload,
    });
  const { createPayment, updatePayment, deletePayment } = usePaymentActions({
    tok,
    apartmentId: sel?.apartment_id,
    period: p,
    reload,
    pushToast,
  });
  const { addOwner, addMaint, saveOc, delOc, saveMr, delMr, openOc, openMr } = useOwnerActions({
    tok,
    apartmentId: sel?.apartment_id,
    period: p,
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
  });
  const { saveAp, createAp, delAp } = usePropertyActions({
    tok,
    sel,
    ap,
    setSel,
    setDrawer,
    setAddProp: () => {},
    apartmentsQuery,
    pushToast,
    confirmRun,
    queryClient,
    reload,
  });
  const {
    submitMeter,
    startEditMeter,
    askDeleteMeter,
    resetMeterForm,
    startReplaceMeter,
    submitReplacement,
    resetReplacementForm,
  } = useMeterActions({
    tok,
    apartmentId: sel?.apartment_id,
    meterForm,
    editingMeterId,
    replacingMeterId,
    replacementForm,
    setMeterForm,
    setEditingMeterId,
    setReplacingMeterId,
    setReplacementForm,
    pushToast,
    confirmRun,
    reload,
  });
  const batchReadingMeterOptions = useMemo(() => {
    const seen = new Map<number, string>();
    for (const row of sortedRows as Array<{ meter_id?: number | null; service_name?: string; meter_plan_mode?: string | null }>) {
      if (!row.meter_id || seen.has(row.meter_id)) continue;
      seen.set(
        row.meter_id,
        `${row.service_name || "Лічильник"}${row.meter_plan_mode ? ` • ${row.meter_plan_mode}` : ""}`,
      );
    }
    return [...seen.entries()].map(([meter_id, label]) => ({ meter_id, label }));
  }, [sortedRows]);
  const loadBatchReadingMetas = async () => {
    if (!sel?.apartment_id) return;
    const results = await Promise.all(
      batchReadingMeterOptions.map(async (item) => {
        const result = await api<MeterExpectedRegistersResult>(
          `/admin/apartments/${sel.apartment_id}/meters/${item.meter_id}/expected-registers?year=${p.year}&month=${p.month}`,
          tok,
        );
        return [String(item.meter_id), result] as const;
      }),
    );
    const nextMetas: Record<string, MeterExpectedRegistersResult> = {};
    const nextDraft: Record<string, Record<string, string>> = {};
    for (const [meterId, result] of results) {
      nextMetas[meterId] = result;
      nextDraft[meterId] = {};
      for (const register of result.registers || []) {
        nextDraft[meterId][register.register_name] = register.current_reading ? String(register.current_reading) : "";
      }
    }
    setBatchReadingMetas(nextMetas);
    setBatchReadingDraft(nextDraft);
  };
  const openBatchReadingModal = async () => {
    if (!batchReadingMeterOptions.length || !sel?.apartment_id) {
      pushToast("Немає лічильника для внесення показників у цьому періоді", "error");
      return;
    }
    await loadBatchReadingMetas();
    setBatchReadingModalOpen(true);
  };
  const saveBatchReadings = async () => {
    if (!sel?.apartment_id) return;
    setBatchReadingSaving(true);
    try {
      const pendingSubmits: Array<{ meter_id: number; register_name: string; template_name?: string | null }> = [];
      let savedCount = 0;
      for (const [meterId, meta] of Object.entries(batchReadingMetas)) {
        const meterDraft = batchReadingDraft[meterId] || {};
        for (const register of meta.registers) {
          const value = (meterDraft[register.register_name] || "").trim();
          if (!value) continue;
          const previousValue =
            register.previous_reading !== undefined && register.previous_reading !== null
              ? Number(register.previous_reading)
              : null;
          if (previousValue !== null && Number(value) < previousValue) {
            throw new Error(
              `${meta.meter_service_name}: поточний показник для "${register.label}" не може бути меншим за попередній (${register.previous_reading}).`,
            );
          }
          await api("/admin/readings", tok, {
            method: "POST",
            body: JSON.stringify({
              meter_id: meta.meter_id,
              register_name: register.register_name,
              year: p.year,
              month: p.month,
              value: Number(value),
            }),
          });
          savedCount += 1;
          const evalResult = await api<MeterSubmitEvaluateResult>(
            `/admin/automations/meter-submit/evaluate?apartment_id=${encodeURIComponent(
              String(sel.apartment_id),
            )}&meter_id=${encodeURIComponent(String(meta.meter_id))}&register_name=${encodeURIComponent(
              register.register_name,
            )}&year=${encodeURIComponent(String(p.year))}&month=${encodeURIComponent(String(p.month))}`,
            tok,
          );
          if (
            evalResult.can_submit &&
            !pendingSubmits.some((item) => item.meter_id === meta.meter_id && item.register_name === register.register_name)
          ) {
            pendingSubmits.push({
              meter_id: meta.meter_id,
              register_name: register.register_name,
              template_name: evalResult.template_name || null,
            });
          }
        }
      }
      if (savedCount === 0) {
        pushToast("Заповніть хоча б один показник для збереження", "error");
        return;
      }
      setBatchReadingModalOpen(false);
      pushToast(`Показники збережено: ${savedCount}`, "success");
      await reload();
      if (pendingSubmits.length > 0) {
        const templateName = pendingSubmits[0]?.template_name || "постачальника";
        const message =
          pendingSubmits.length === 1
            ? `Ви зберегли показник "${pendingSubmits[0].register_name}". Передати його через automation "${templateName}"?`
            : `Ви зберегли ${pendingSubmits.length} показники. Передати їх через automation "${templateName}"?`;
        confirmRun("Передати показник постачальнику", message, async () => {
          let dispatchedCount = 0;
          for (const item of pendingSubmits) {
            const dispatchResult = await api<MeterSubmitDispatchResult>("/admin/automations/meter-submit/dispatch", tok, {
              method: "POST",
              body: JSON.stringify({
                apartment_id: sel.apartment_id,
                meter_id: item.meter_id,
                register_name: item.register_name,
                year: p.year,
                month: p.month,
              }),
            });
            if (dispatchResult.dispatched) {
              dispatchedCount += 1;
            }
          }
          pushToast(
            dispatchedCount > 0
              ? `Показники передано постачальнику: ${dispatchedCount}`
              : "Показники збережено, але automation не виконала відправку",
            dispatchedCount > 0 ? "success" : "error",
          );
          await reload();
        });
      }
    } catch (error) {
      pushToast(error instanceof Error ? error.message : "Не вдалося зберегти показники", "error");
    } finally {
      setBatchReadingSaving(false);
    }
  };
  const prepareBillingStatement = async () => {
    if (!sel?.apartment_id) return;
    await api("/admin/billing/statements/prepare", tok, {
      method: "POST",
      body: {
        apartment_id: sel.apartment_id,
        year: p.year,
        month: p.month,
      },
    });
    pushToast("Рахунок підготовлено", "success");
    await reload();
  };
  const sendBillingStatement = async (statementId: number) => {
    await api(`/admin/billing/statements/${statementId}/send`, tok, {
      method: "POST",
      body: {
        sent_channel: "manual",
      },
    });
    pushToast("Рахунок позначено як відправлений", "success");
    await reload();
  };
  const saveAutomation = async (
    row: AutomationItem,
    draft: {
      provider_company: string;
      personal_account: string;
      cabinet_url: string;
      cabinet_login: string;
      auto_check_enabled: boolean;
      auto_check_time: string;
      auto_check_timezone: string;
      auto_check_window_day_from: string;
      auto_check_window_day_to: string;
      submit_enabled: boolean;
      submit_time: string;
      submit_window_day_from: string;
      submit_window_day_to: string;
      cabinet_password: string;
      },
  ) => {
    if (!row.template_id) {
      throw new Error("Для цього запису не знайдено шаблон автоматизації.");
    }
    await api(`/admin/apartments/${row.apartment_id}/automations`, tok, {
      method: "PUT",
      body: {
        apartment_id: row.apartment_id,
        template_id: row.template_id,
        provider_id: row.provider_id || null,
        personal_account: draft.personal_account.trim() || null,
        cabinet_url: draft.cabinet_url.trim() || null,
        cabinet_login: draft.cabinet_login.trim() || null,
        cabinet_password: draft.cabinet_password || null,
        is_enabled: !!draft.auto_check_enabled,
        accrual_enabled: !!draft.auto_check_enabled,
        accrual_time: draft.auto_check_time || "09:00",
        accrual_window_day_from: Number(draft.auto_check_window_day_from || 1),
        accrual_window_day_to: Number(draft.auto_check_window_day_to || 10),
        submit_enabled: !!draft.submit_enabled,
        submit_time: draft.submit_time || "09:00",
        submit_window_day_from: Number(draft.submit_window_day_from || 28),
        submit_window_day_to: Number(draft.submit_window_day_to || 3),
      },
    });
    await automationsQuery.refetch();
    await automationTemplatesQuery.refetch();
    await reload();
    pushToast("Налаштування автоматизації збережено", "success");
  };
  const runAutomation = async (row: AutomationItem, mode: "full" | "readings" | "tariffs" = "full") => {
    if (!row.automation_id) {
      throw new Error("Automation ще не підключена до цього об'єкта.");
    }
    const result = await api<AutomationItem>(
      `/admin/automations/run?automation_id=${encodeURIComponent(String(row.automation_id))}&mode=${encodeURIComponent(mode)}`,
      tok,
      { method: "POST" },
    );
    await automationsQuery.refetch();
    await reload();
    const status = result.auto_check_status || "unknown";
    const details = result.auto_check_message ? `: ${result.auto_check_message}` : "";
    const apartmentLabel = (row.apartment_address || "").trim() || row.apartment_code;
    if (status === "updated" || status === "no_change" || status === "waiting") {
      pushToast(`Ручний запуск [${status}] ${apartmentLabel} / ${row.service_name}${details}`, "success");
      return;
    }
    pushToast(`Ручний запуск [${status}] ${apartmentLabel} / ${row.service_name}${details}`, "error");
  };
  const createAutomationTemplate = async (payload: {
    code: string;
    name: string;
    provider_id: number | null;
    utility_type: UtilityType | null;
    cabinet_url: string | null;
    description: string | null;
    supports_accrual: boolean;
    supports_meter_submit: boolean;
    is_active: boolean;
  }) => {
    await api("/admin/automation-templates", tok, {
      method: "POST",
      body: payload,
    });
    await automationTemplatesQuery.refetch();
    pushToast("Шаблон автоматизації створено", "success");
  };
  const updateAutomationTemplate = async (
    templateId: number,
    payload: {
      code: string;
      name: string;
      provider_id: number | null;
      utility_type: UtilityType | null;
      cabinet_url: string | null;
      description: string | null;
      supports_accrual: boolean;
      supports_meter_submit: boolean;
      is_active: boolean;
    },
  ) => {
    await api(`/admin/automation-templates/${templateId}`, tok, {
      method: "PUT",
      body: payload,
    });
    await automationTemplatesQuery.refetch();
    pushToast("Шаблон автоматизації оновлено", "success");
  };
  const deleteAutomationTemplate = async (templateId: number) => {
    await api(`/admin/automation-templates/${templateId}`, tok, { method: "DELETE" });
    await automationTemplatesQuery.refetch();
    pushToast("Шаблон автоматизації видалено", "success");
  };
  const connectTemplateToApartment = async (
    templateId: number,
    apartmentId: number,
    payload: {
      personal_account: string;
      cabinet_url: string;
      cabinet_login: string;
      cabinet_password: string;
      accrual_enabled: boolean;
      accrual_time: string;
      accrual_window_day_from: string;
      accrual_window_day_to: string;
      submit_enabled: boolean;
      submit_time: string;
      submit_window_day_from: string;
      submit_window_day_to: string;
    },
  ) => {
    await api(`/admin/apartments/${apartmentId}/automations`, tok, {
      method: "PUT",
      body: {
        apartment_id: apartmentId,
        template_id: templateId,
        personal_account: payload.personal_account.trim() || null,
        cabinet_url: payload.cabinet_url.trim() || null,
        cabinet_login: payload.cabinet_login.trim() || null,
        cabinet_password: payload.cabinet_password || null,
        is_enabled: true,
        accrual_enabled: payload.accrual_enabled,
        accrual_time: payload.accrual_time || "09:00",
        accrual_window_day_from: Number(payload.accrual_window_day_from || 1),
        accrual_window_day_to: Number(payload.accrual_window_day_to || 10),
        submit_enabled: payload.submit_enabled,
        submit_time: payload.submit_time || "09:00",
        submit_window_day_from: Number(payload.submit_window_day_from || 28),
        submit_window_day_to: Number(payload.submit_window_day_to || 3),
      },
    });
    await automationsQuery.refetch();
    pushToast("Шаблон підключено до об'єкта", "success");
  };
  const disconnectTemplateFromApartment = async (row: AutomationItem) => {
    if (!row.template_id) return;
    await api(`/admin/apartments/${row.apartment_id}/automations/${row.template_id}`, tok, { method: "DELETE" });
    await automationsQuery.refetch();
    pushToast("Підключення автоматизації видалено", "success");
  };
  const fetchAutomationLogs = async (automationId: number) => {
    return api<AutomationRunLogItem[]>(`/admin/automations/${automationId}/logs?limit=5`, tok);
  };
  const runAutomationCycle = async () => {
    const result = await api<AutomationCycleRunResult>("/admin/automations/run-cycle", tok, { method: "POST" });
    await automationsQuery.refetch();
    await automationCycleRunsQuery.refetch();
    await reload();
    pushToast(result.message || "Плановий цикл виконано", "success");
  };
  const previewAutomationCycle = async () => {
    const result = await api<AutomationCyclePreviewResult>("/admin/automations/run-cycle-preview", tok);
    await automationCycleRunsQuery.refetch();
    return result;
  };
  const fetchAutomationCycleRunDetail = async (cycleRunId: number, apartmentId?: number | null) => {
    const suffix = apartmentId ? `?apartment_id=${encodeURIComponent(String(apartmentId))}` : "";
    return api<AutomationCycleRunDetailResult>(`/admin/automations/cycle-runs/${cycleRunId}${suffix}`, tok);
  };
  const createServiceCatalogItem = async (payload: {
    code: string;
    name: string;
    calculation_kind: ServiceCalculationKind;
    unit_name: string;
    requires_meter: boolean;
    allowed_meter_utility_type: UtilityType | null;
    default_provider_utility_type: UtilityType | null;
    derived_from_service_id: number | null;
    display_order: number;
    is_active: boolean;
  }) => {
    await api("/admin/service-catalog", tok, { method: "POST", body: payload });
    await serviceCatalogQuery.refetch();
    pushToast("Послугу довідника створено", "success");
  };
  const updateServiceCatalogItem = async (
    serviceCatalogId: number,
    payload: {
      code: string;
      name: string;
      calculation_kind: ServiceCalculationKind;
      unit_name: string;
      requires_meter: boolean;
      allowed_meter_utility_type: UtilityType | null;
      default_provider_utility_type: UtilityType | null;
      derived_from_service_id: number | null;
      display_order: number;
      is_active: boolean;
    },
  ) => {
    await api(`/admin/service-catalog/${serviceCatalogId}`, tok, { method: "PUT", body: payload });
    await serviceCatalogQuery.refetch();
    pushToast("Послугу довідника оновлено", "success");
  };
  const deleteServiceCatalogItem = async (serviceCatalogId: number) => {
    await api(`/admin/service-catalog/${serviceCatalogId}`, tok, { method: "DELETE" });
    await serviceCatalogQuery.refetch();
    pushToast("Послугу довідника видалено", "success");
  };
  const syncConnectionChargeLines = async (
    connectionId: number,
    existingLines: ApartmentServiceConnectionItem["charge_lines"],
    nextLines: Array<{
      id?: number;
      line_kind: ChargeLineKind;
      label: string;
      meter_id: number | null;
      meter_register: string;
      derived_from_line_id: number | null;
      initial_reading: string | null;
      unit_name: string;
      price_per_unit: string;
      quantity_source: QuantitySource;
      quantity_multiplier: string;
      effective_from: string;
      effective_to: string | null;
      is_active: boolean;
    }>,
  ) => {
    const staleLineIds = existingLines
      .filter((line) => !nextLines.some((item) => item.id === line.id))
      .map((line) => line.id);
    for (const lineId of staleLineIds) {
      await api(`/admin/charge-lines/${lineId}`, tok, { method: "DELETE" });
    }
    for (const line of nextLines) {
      const body = {
        line_kind: line.line_kind,
        label: line.label,
        meter_id: line.meter_id,
        meter_register: line.meter_register,
        derived_from_line_id: line.derived_from_line_id,
        initial_reading:
          line.line_kind === "meter_register" && line.initial_reading !== null && line.initial_reading !== undefined
            ? Number(line.initial_reading)
            : null,
        unit_name: line.unit_name,
        price_per_unit: Number(line.price_per_unit),
        quantity_source: line.quantity_source,
        quantity_multiplier: Number(line.quantity_multiplier || "1"),
        effective_from: line.effective_from,
        effective_to: line.effective_to,
        is_active: line.is_active,
      };
      if (line.id) {
        await api(`/admin/charge-lines/${line.id}`, tok, { method: "PUT", body });
      } else {
        await api(`/admin/service-connections/${connectionId}/charge-lines`, tok, { method: "POST", body });
      }
    }
  };
  const createServiceConnection = async (payload: {
    service_catalog_id: number;
    provider_id: number | null;
    personal_account: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    note: string | null;
    charge_lines: Array<{
      id?: number;
      line_kind: ChargeLineKind;
      label: string;
      meter_id: number | null;
      meter_register: string;
      derived_from_line_id: number | null;
      initial_reading: string | null;
      unit_name: string;
      price_per_unit: string;
      quantity_source: QuantitySource;
      quantity_multiplier: string;
      effective_from: string;
      effective_to: string | null;
      is_active: boolean;
    }>;
  }) => {
    const connection = await api<ApartmentServiceConnectionItem>("/admin/service-connections", tok, {
      method: "POST",
      body: {
        apartment_id: sel?.apartment_id,
        service_catalog_id: payload.service_catalog_id,
        provider_id: payload.provider_id,
        personal_account: payload.personal_account,
        started_at: payload.started_at,
        ended_at: payload.ended_at,
        status: payload.status,
        note: payload.note,
      },
    });
    await syncConnectionChargeLines(connection.id, [], payload.charge_lines);
    await serviceConnectionsQuery.refetch();
    await reload();
    pushToast("Послугу об'єкта підключено", "success");
  };
  const updateServiceConnection = async (
    connectionId: number,
    payload: {
      provider_id: number | null;
      personal_account: string | null;
      started_at: string;
      ended_at: string | null;
      status: string;
      note: string | null;
      charge_lines: Array<{
        id?: number;
        line_kind: ChargeLineKind;
        label: string;
        meter_id: number | null;
        meter_register: string;
        derived_from_line_id: number | null;
        initial_reading: string | null;
        unit_name: string;
        price_per_unit: string;
        quantity_source: QuantitySource;
        quantity_multiplier: string;
        effective_from: string;
        effective_to: string | null;
        is_active: boolean;
      }>;
    },
  ) => {
    const existingConnection = (serviceConnectionsQuery.data || []).find((item) => item.id === connectionId);
    await api(`/admin/service-connections/${connectionId}`, tok, {
      method: "PUT",
      body: {
        provider_id: payload.provider_id,
        personal_account: payload.personal_account,
        started_at: payload.started_at,
        ended_at: payload.ended_at,
        status: payload.status,
        note: payload.note,
      },
    });
    await syncConnectionChargeLines(connectionId, existingConnection?.charge_lines || [], payload.charge_lines);
    await serviceConnectionsQuery.refetch();
    await reload();
    pushToast("Послугу об'єкта оновлено", "success");
  };
  const deleteServiceConnection = async (connectionId: number) => {
    await api(`/admin/service-connections/${connectionId}`, tok, { method: "DELETE" });
    await serviceConnectionsQuery.refetch();
    await reload();
    pushToast("Послугу об'єкта видалено", "success");
  };
  const createProvider = async (payload: {
    name_full: string;
    utility_type: UtilityType;
    adapter_code: string;
    is_active: boolean;
    note: string;
  }) => {
    await api("/admin/providers", tok, {
      method: "POST",
      body: {
        name_full: payload.name_full.trim(),
        utility_type: payload.utility_type,
        adapter_code: payload.adapter_code.trim() || "manual_stub",
        is_active: !!payload.is_active,
        note: payload.note.trim() || null,
      },
    });
    await providersQuery.refetch();
    pushToast("Постачальника створено", "success");
  };
  const updateProvider = async (
    providerId: number,
    payload: {
      name_full: string;
      utility_type: UtilityType;
      adapter_code: string;
      is_active: boolean;
      note: string;
    },
  ) => {
    await api(`/admin/providers/${providerId}`, tok, {
      method: "PUT",
      body: {
        name_full: payload.name_full.trim(),
        utility_type: payload.utility_type,
        adapter_code: payload.adapter_code.trim() || "manual_stub",
        is_active: !!payload.is_active,
        note: payload.note.trim() || null,
      },
    });
    await providersQuery.refetch();
    pushToast("Постачальника оновлено", "success");
  };
  const deleteProvider = async (providerId: number) => {
    await api(`/admin/providers/${providerId}`, tok, { method: "DELETE" });
    await providersQuery.refetch();
    pushToast("Постачальника видалено", "success");
  };
  const createMeterType = async (payload: {
    name: string;
    utility_type: UtilityType;
    sort_order: number;
    is_active: boolean;
  }) => {
    await api("/admin/meter-types", tok, {
      method: "POST",
      body: {
        name: payload.name.trim(),
        utility_type: payload.utility_type,
        sort_order: payload.sort_order,
        is_active: !!payload.is_active,
      },
    });
    await meterTypesQuery.refetch();
    pushToast("Тип лічильника створено", "success");
  };
  const updateMeterType = async (
    meterTypeId: number,
    payload: {
      name: string;
      utility_type: UtilityType;
      sort_order: number;
      is_active: boolean;
    },
  ) => {
    await api(`/admin/meter-types/${meterTypeId}`, tok, {
      method: "PUT",
      body: {
        name: payload.name.trim(),
        utility_type: payload.utility_type,
        sort_order: payload.sort_order,
        is_active: !!payload.is_active,
      },
    });
    await meterTypesQuery.refetch();
    pushToast("Тип лічильника оновлено", "success");
  };
  const deleteMeterType = async (meterTypeId: number) => {
    await api(`/admin/meter-types/${meterTypeId}`, tok, { method: "DELETE" });
    await meterTypesQuery.refetch();
    pushToast("Тип лічильника видалено", "success");
  };
  const { submitEquipment, startEditEquipment, askDeleteEquipment, resetEquipmentForm } =
    useEquipmentActions({
      tok,
      apartmentId: sel?.apartment_id,
      equipmentForm,
      editingEquipmentId,
      setEquipmentForm,
      setEditingEquipmentId,
      pushToast,
      confirmRun,
      reload,
    });

  if (!tok) {
    return (
      <LoginScreen
        cred={cred}
        setCred={setCred}
        initialAdmin={initialAdmin}
        setInitialAdmin={setInitialAdmin}
        login={login}
        registerInitialAdmin={registerInitialAdmin}
        boot={boot}
        err={err}
      />
    );
  }

  return (
    <div className="app-shell">
      <AdminHeader
        boot={boot}
        onOpenDrawer={() => setDrawer(true)}
        onOpenAdmins={() => setAdminsModal(true)}
        onOpenSettings={() => setProfileSettingsOpen(true)}
        onLogout={out}
      />
      {profileSettingsOpen ? (
        <ProfileSettingsModal
          username={boot.username}
          themeMode={theme}
          onClose={() => setProfileSettingsOpen(false)}
          onCycleTheme={cycleTheme}
          onOpenPassword={() => {
            setProfileSettingsOpen(false);
            setPwdModal(true);
          }}
        />
      ) : null}
      <PropertyDrawer
        drawer={drawer}
        setDrawer={setDrawer}
        apartmentsQuery={apartmentsQuery}
        ap={ap}
        setAp={setAp}
        createAp={createAp}
        totals={totals}
        money={money}
        props={props}
        tenants={tenants}
        sel={sel}
        setSel={setSel}
        newTenant={newTenant}
        setNewTenant={setNewTenant}
        createTenantOnly={createTenantOnly}
        updateTenantById={updateTenantById}
        deleteTenantById={deleteTenantById}
      />
      <DashboardContent
        apartmentsQuery={apartmentsQuery}
        detailBundleQuery={detailBundleQuery}
        sel={sel}
        detail={detail}
        shiftPeriod={shiftPeriod}
        onPickPeriod={(year, month) => {
          if (isPeriodAfterMaxAllowed(year, month)) return;
          setPeriod({ year, month });
        }}
        maxPeriodInput={maxPeriodInput}
        periodLabel={periodLabel}
        p={p}
        money={money}
        tab={tab}
        setTab={setTab}
        pushToast={pushToast}
        dt={dt}
        payments={payments}
        prepareBillingStatement={prepareBillingStatement}
        sendBillingStatement={sendBillingStatement}
        toggleSort={toggleSort}
        sortIcon={sortIcon}
        sortedRows={sortedRows}
        editSrv={editSrv}
        editRef={editRef}
        asInt={asInt}
        start={start}
        setEditSrv={setEditSrv}
        setDraft={setDraft}
        draft={draft}
        changed={changed}
        saveRow={saveRow}
        recalcMonth={recalcMonth}
        confirmMonth={confirmMonth}
        reopenMonth={reopenMonth}
        resetSortDefault={resetSortDefault}
        accr={accr}
        history={history}
        openBatchReadingModal={openBatchReadingModal}
        batchReadingMeterOptions={batchReadingMeterOptions}
        batchReadingModalOpen={batchReadingModalOpen}
        closeBatchReadingModal={() => setBatchReadingModalOpen(false)}
        batchReadingMetas={batchReadingMetas}
        batchReadingDraft={batchReadingDraft}
        setBatchReadingDraft={setBatchReadingDraft}
        saveBatchReadings={saveBatchReadings}
        batchReadingSaving={batchReadingSaving}
        newTenant={newTenant}
        setNewTenant={setNewTenant}
        createTenantAndAssign={createTenantAndAssign}
        tenant={tenant}
        setTenant={setTenant}
        assignExisting={assignExisting}
        setAssignExisting={setAssignExisting}
        tenants={tenants}
        assignTenant={assignTenant}
        tenancies={tenancies}
        tenancyEndDate={tenancyEndDate}
        setTenancyEndDate={setTenancyEndDate}
        saveTenant={saveTenant}
        endTenancy={endTenancy}
        createPayment={createPayment}
        updatePayment={updatePayment}
        deletePayment={deletePayment}
        own={own}
        setOwn={setOwn}
        addOwner={addOwner}
        mnt={mnt}
        setMnt={setMnt}
        addMaint={addMaint}
        oc={oc}
        mr={mr}
        openOc={openOc}
        openMr={openMr}
        saveAp={saveAp}
        delAp={delAp}
        ap={ap}
        setAp={setAp}
        meters={meters}
        replacingMeterId={replacingMeterId}
        replacementForm={replacementForm}
        setReplacementForm={setReplacementForm}
        startReplaceMeter={startReplaceMeter}
        submitReplacement={submitReplacement}
        resetReplacementForm={resetReplacementForm}
        equipment={equipment}
        equipmentForm={equipmentForm}
        setEquipmentForm={setEquipmentForm}
        editingEquipmentId={editingEquipmentId}
        submitEquipment={submitEquipment}
        startEditEquipment={startEditEquipment}
        askDeleteEquipment={askDeleteEquipment}
        resetEquipmentForm={resetEquipmentForm}
        automations={automationsQuery.data || []}
        automationTemplates={automationTemplatesQuery.data || []}
        automationsLoading={automationsQuery.isLoading || automationsQuery.isFetching}
        saveAutomation={saveAutomation}
        runAutomation={runAutomation}
        createAutomationTemplate={createAutomationTemplate}
        updateAutomationTemplate={updateAutomationTemplate}
        deleteAutomationTemplate={deleteAutomationTemplate}
        connectTemplateToApartment={connectTemplateToApartment}
        disconnectTemplateFromApartment={disconnectTemplateFromApartment}
        fetchAutomationLogs={fetchAutomationLogs}
        runAutomationCycle={runAutomationCycle}
        previewAutomationCycle={previewAutomationCycle}
        automationCycleRuns={automationCycleRunsQuery.data || []}
        fetchAutomationCycleRunDetail={fetchAutomationCycleRunDetail}
        selectedApartmentId={sel?.apartment_id || null}
        providers={providersQuery.data || []}
        meterTypes={meterTypesQuery.data || []}
        serviceCatalog={serviceCatalogQuery.data || []}
        serviceConnections={serviceConnectionsQuery.data || []}
        serviceConnectionsLoading={serviceConnectionsQuery.isLoading || serviceConnectionsQuery.isFetching}
        createServiceConnection={createServiceConnection}
        updateServiceConnection={updateServiceConnection}
        deleteServiceConnection={deleteServiceConnection}
        createProvider={createProvider}
        updateProvider={updateProvider}
        deleteProvider={deleteProvider}
        createMeterType={createMeterType}
        updateMeterType={updateMeterType}
        deleteMeterType={deleteMeterType}
        createServiceCatalogItem={createServiceCatalogItem}
        updateServiceCatalogItem={updateServiceCatalogItem}
        deleteServiceCatalogItem={deleteServiceCatalogItem}
        meterForm={meterForm}
        setMeterForm={setMeterForm}
        editingMeterId={editingMeterId}
        submitMeter={submitMeter}
        startEditMeter={startEditMeter}
        askDeleteMeter={askDeleteMeter}
        resetMeterForm={resetMeterForm}
      />
      <AppModals
        payModal={payModal}
        setPayModal={setPayModal}
        pay={pay}
        savePay={savePay}
        pwdModal={pwdModal}
        setPwdModal={setPwdModal}
        pwd={pwd}
        changePassword={changePassword}
        adminsModal={adminsModal}
        setAdminsModal={setAdminsModal}
        adminUsersQuery={adminUsersQuery}
        createAdminUserMutation={createAdminUserMutation}
        updateAdminUserMutation={updateAdminUserMutation}
        changeAdminPasswordMutation={changeAdminPasswordMutation}
        ocModal={ocModal}
        ocForm={ocForm}
        setOcModal={setOcModal}
        setOcForm={setOcForm}
        saveOc={saveOc}
        delOc={delOc}
        mrModal={mrModal}
        mrForm={mrForm}
        setMrModal={setMrModal}
        setMrForm={setMrForm}
        saveMr={saveMr}
        delMr={delMr}
        confirm={confirm}
        setConfirm={setConfirm}
        confirmActionRef={confirmActionRef}
        toasts={toasts}
        setToasts={setToasts}
      />
    </div>
  );
}
