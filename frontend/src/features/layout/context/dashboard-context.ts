import { createContext, useContext } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import type {
  ApartmentEquipmentForm,
  ApartmentEquipmentItem,
  ApartmentProfileForm,
  MeterExpectedRegistersResult,
  MeterItem,
  MeterTypeItem,
  MeterUpsertForm,
  UtilityPaymentItem,
  AutomationCyclePreviewResult,
  AutomationCycleRunDetailResult,
  AutomationCycleRunResult,
  AutomationItem,
  AutomationRunLogItem,
  AutomationTemplateItem,
  ApartmentServiceConnectionItem,
  ProviderItem,
  ServiceCatalogItem,
  UtilityType,
} from "@/shared/api/types";
import type { ElectricityPlanForm } from "@/features/tariffs/hooks/use-electricity-plan-actions";

export type TabKey = "calc" | "payments" | "tenant" | "tariffs" | "automations" | "owner" | "report" | "property";

export type DashboardContextValue = {
  apartmentsQuery: { isLoading?: boolean };
  detailBundleQuery: { isFetching?: boolean };
  sel: any;
  detail: any;
  shiftPeriod: (delta: number) => void;
  onPickPeriod: (year: number, month: number) => void;
  maxPeriodInput: string;
  periodLabel: (year: number, month: number) => string;
  p: { year: number; month: number };
  money: (v: unknown) => string;
  tab: TabKey;
  setTab: (tab: TabKey) => void;
  dt: (x: string | Date | null | undefined) => string;
  payments: UtilityPaymentItem[];
  prepareBillingStatement: () => Promise<void>;
  sendBillingStatement: (statementId: number) => Promise<void>;
  toggleSort: any;
  sortIcon: any;
  sortedRows: any[];
  editSrv: string | null;
  editRef: RefObject<HTMLTableRowElement | null>;
  asInt: (v: unknown) => string;
  start: (row: any) => void;
  setEditSrv: (v: string | null) => void;
  setDraft: (v: any) => void;
  draft: any;
  changed: (row: any) => boolean;
  saveRow: (row: any) => Promise<void>;
  recalcMonth: () => Promise<void>;
  confirmMonth: () => Promise<void>;
  reopenMonth: (reason: string) => Promise<void>;
  resetSortDefault: () => void;
  accr: number;
  history: any[];
  openBatchReadingModal: () => Promise<void>;
  batchReadingMeterOptions: Array<{ meter_id: number; label: string }>;
  batchReadingModalOpen: boolean;
  closeBatchReadingModal: () => void;
  batchReadingMetas: Record<string, MeterExpectedRegistersResult>;
  batchReadingDraft: Record<string, Record<string, string>>;
  setBatchReadingDraft: Dispatch<SetStateAction<Record<string, Record<string, string>>>>;
  saveBatchReadings: () => Promise<void>;
  batchReadingSaving?: boolean;
  newTenant: any;
  setNewTenant: (v: any) => void;
  createTenantAndAssign: () => Promise<void>;
  tenant: any;
  setTenant: (v: any) => void;
  assignExisting: any;
  setAssignExisting: (v: any) => void;
  tenants: any[];
  assignTenant: () => Promise<void>;
  tenancies: any[];
  tenancyEndDate: string;
  setTenancyEndDate: Dispatch<SetStateAction<string>>;
  saveTenant: () => Promise<void>;
  endTenancy: (tenancyId: number, endDate: string) => Promise<void>;
  createPayment: (payload: {
    amount: number;
    paid_at: string;
    note: string | null;
    payer_type: "tenant" | "owner";
    tenant_id: number | null;
  }) => Promise<void>;
  updatePayment: (
    paymentId: number,
    payload: {
      amount: number;
      paid_at: string;
      note: string | null;
      payer_type: "tenant" | "owner";
      tenant_id: number | null;
    },
  ) => Promise<void>;
  deletePayment: (paymentId: number) => Promise<void>;
  meters: MeterItem[];
  equipment: ApartmentEquipmentItem[];
  equipmentForm: ApartmentEquipmentForm;
  setEquipmentForm: Dispatch<SetStateAction<ApartmentEquipmentForm>>;
  editingEquipmentId: number | null;
  submitEquipment: () => Promise<void>;
  startEditEquipment: (item: ApartmentEquipmentItem) => void;
  askDeleteEquipment: (item: ApartmentEquipmentItem) => void;
  resetEquipmentForm: () => void;
  automations: AutomationItem[];
  automationTemplates: AutomationTemplateItem[];
  automationsLoading?: boolean;
  saveAutomation: (
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
  ) => Promise<void>;
  runAutomation: (row: AutomationItem, mode: "full" | "readings" | "tariffs") => Promise<void>;
  createAutomationTemplate: (payload: {
    code: string;
    name: string;
    provider_id: number | null;
    utility_type: UtilityType | null;
    cabinet_url: string | null;
    description: string | null;
    supports_accrual: boolean;
    supports_meter_submit: boolean;
    is_active: boolean;
  }) => Promise<void>;
  updateAutomationTemplate: (
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
  ) => Promise<void>;
  deleteAutomationTemplate: (templateId: number) => Promise<void>;
  connectTemplateToApartment: (
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
  ) => Promise<void>;
  disconnectTemplateFromApartment: (row: AutomationItem) => Promise<void>;
  fetchAutomationLogs: (automationId: number) => Promise<AutomationRunLogItem[]>;
  runAutomationCycle: () => Promise<void>;
  previewAutomationCycle: () => Promise<AutomationCyclePreviewResult>;
  automationCycleRuns: AutomationCycleRunResult[];
  fetchAutomationCycleRunDetail: (cycleRunId: number, apartmentId?: number | null) => Promise<AutomationCycleRunDetailResult>;
  selectedApartmentId?: number | null;
  providers: ProviderItem[];
  meterTypes: MeterTypeItem[];
  serviceCatalog: ServiceCatalogItem[];
  serviceConnections: ApartmentServiceConnectionItem[];
  serviceConnectionsLoading?: boolean;
  createServiceConnection: (payload: {
    service_catalog_id: number;
    provider_id: number | null;
    personal_account: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    note: string | null;
    charge_lines: Array<{
      id?: number;
      line_kind: "fixed" | "meter_register" | "derived";
      label: string;
      meter_id: number | null;
      meter_register: string;
      derived_from_line_id: number | null;
      initial_reading: string | null;
      unit_name: string;
      price_per_unit: string;
      quantity_source: "fixed_1" | "registered_residents" | "area_m2" | "derived_consumption";
      quantity_multiplier: string;
      effective_from: string;
      effective_to: string | null;
      is_active: boolean;
    }>;
  }) => Promise<void>;
  updateServiceConnection: (
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
        line_kind: "fixed" | "meter_register" | "derived";
        label: string;
        meter_id: number | null;
        meter_register: string;
        derived_from_line_id: number | null;
        initial_reading: string | null;
        unit_name: string;
        price_per_unit: string;
        quantity_source: "fixed_1" | "registered_residents" | "area_m2" | "derived_consumption";
        quantity_multiplier: string;
        effective_from: string;
        effective_to: string | null;
        is_active: boolean;
      }>;
    },
  ) => Promise<void>;
  deleteServiceConnection: (connectionId: number) => Promise<void>;
  electricityPlanForm: ElectricityPlanForm;
  setElectricityPlanForm: Dispatch<SetStateAction<ElectricityPlanForm>>;
  electricityMeters: MeterItem[];
  saveElectricityPlan: () => Promise<void>;
  own: any;
  setOwn: (v: any) => void;
  addOwner: () => Promise<void>;
  mnt: any;
  setMnt: (v: any) => void;
  addMaint: () => Promise<void>;
  oc: any[];
  mr: any[];
  openOc: (item: any) => void;
  openMr: (item: any) => void;
  saveAp: () => Promise<void>;
  delAp: () => Promise<void>;
  ap: ApartmentProfileForm;
  setAp: Dispatch<SetStateAction<ApartmentProfileForm>>;
  meterForm: MeterUpsertForm;
  setMeterForm: Dispatch<SetStateAction<MeterUpsertForm>>;
  editingMeterId: number | null;
  submitMeter: () => Promise<boolean>;
  startEditMeter: (meter: MeterItem) => void;
  askDeleteMeter: (meter: MeterItem) => void;
  resetMeterForm: () => void;
  replacingMeterId: number | null;
  replacementForm: { serial_number: string; initial_reading: string; installed_at: string };
  setReplacementForm: Dispatch<
    SetStateAction<{ serial_number: string; initial_reading: string; installed_at: string }>
  >;
  startReplaceMeter: (meter: MeterItem) => void;
  submitReplacement: () => Promise<void>;
  resetReplacementForm: () => void;
};

export const DashboardContext = createContext<DashboardContextValue | null>(null);

export function useDashboardContext(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) {
    throw new Error("useDashboardContext must be used within DashboardContext.Provider");
  }
  return ctx;
}
