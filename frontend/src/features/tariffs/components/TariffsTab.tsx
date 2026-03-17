import { useMemo, useState } from "react";
import { In, Se } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import { TariffRow, submitBadge } from "@/features/tariffs/components/TariffRow";
import type {
  AutomationItem,
  ElectricityPlanHistoryItem,
  ProviderItem,
} from "@/shared/api/types";
import type { Dispatch, SetStateAction } from "react";

type NewTariffForm = {
  service_name: string;
  charge_mode: "fixed" | "metered";
  price_per_unit: string;
  unit_name: "kWh" | "m3" | "month";
  effective_from: string;
  initial_meter_reading: string;
  meter_serial_number: string;
  service_status: "active" | "inactive";
  disable_from_month: string;
  provider_id: string;
  provider_company: string;
  personal_account: string;
  meter_id: string;
  meter_register: string;
  source_service_name: string;
  fixed_quantity_source: "auto" | "unit" | "apartment_registered_residents" | "apartment_area_m2";
  fixed_quantity_multiplier: string;
};

type DualPlanDraft = {
  meter_id: string;
  effective_from: string;
  day_service_name: string;
  night_service_name: string;
  day_price_per_unit: string;
  night_price_per_unit: string;
  day_initial_reading: string;
  night_initial_reading: string;
};

type TriPlanDraft = {
  meter_id: string;
  effective_from: string;
  peak_service_name: string;
  semi_peak_service_name: string;
  off_peak_service_name: string;
  peak_price_per_unit: string;
  semi_peak_price_per_unit: string;
  off_peak_price_per_unit: string;
  peak_initial_reading: string;
  semi_peak_initial_reading: string;
  off_peak_initial_reading: string;
};

const DEFAULT_DUAL_PLAN: DualPlanDraft = {
  meter_id: "",
  effective_from: "",
  day_service_name: "Електроенергія денний тариф",
  night_service_name: "Електроенергія нічний тариф",
  day_price_per_unit: "",
  night_price_per_unit: "",
  day_initial_reading: "",
  night_initial_reading: "",
};

const DEFAULT_TRI_PLAN: TriPlanDraft = {
  meter_id: "",
  effective_from: "",
  peak_service_name: "Електроенергія піковий тариф",
  semi_peak_service_name: "Електроенергія напівпіковий тариф",
  off_peak_service_name: "Електроенергія нічний тариф",
  peak_price_per_unit: "",
  semi_peak_price_per_unit: "",
  off_peak_price_per_unit: "",
  peak_initial_reading: "",
  semi_peak_initial_reading: "",
  off_peak_initial_reading: "",
};

type TariffScenario = "fixed_amount" | "per_parameter" | "metered";
type ParameterBase =
  | "apartment_registered_residents"
  | "apartment_area_m2"
  | "linked_service";

const TARIFF_SCENARIOS: Array<{
  id: TariffScenario;
  title: string;
  description: string;
}> = [
  {
    id: "fixed_amount",
    title: "Фіксована сума",
    description: "Для інтернету, абонплати, оренди або інших сум, які не залежать від площі чи людей.",
  },
  {
    id: "per_parameter",
    title: "За одиницю / параметр",
    description: "Для сміття, квартплати, водовідведення або послуг, що рахуються від площі, прописаних чи іншої послуги.",
  },
  {
    id: "metered",
    title: "За лічильником",
    description: "Для газу, води й електроенергії з однотарифним, день/ніч або тризонним режимом.",
  },
];

const SERVICE_PRESETS = [
  "Інтернет",
  "Оренда",
  "Комуналка",
  "Вивіз сміття",
  "Водопостачання",
  "Водовідведення",
  "Газопостачання",
  "За розподіл (доставку) газу",
  "Електроенергія",
  "Абонентська плата (водоканал)",
] as const;

function isAutomatedProvider(provider: ProviderItem | undefined) {
  return !!provider && provider.adapter_code !== "manual_stub";
}

function providerDisplayName(provider: ProviderItem | undefined) {
  if (!provider) return "";
  return `${isAutomatedProvider(provider) ? "A - " : ""}${provider.name_full}`;
}

export function TariffsTab({
  tar,
  loading,
  openT,
  newTar,
  setNewTar,
  createTariff,
  meters,
  fixedServiceNames,
  selectedLedgerService,
  setSelectedLedgerService,
  ledgerForm,
  setLedgerForm,
  saveServiceLedgerMonth,
  ledgerHistory,
  ledgerHistoryLoading,
  electricityPlanForm,
  setElectricityPlanForm,
  electricityMeters,
  electricityPlans,
  saveElectricityPlan,
  deleteElectricityPlan,
  apartmentId,
  automations,
  providers,
  registeredResidents,
  areaM2,
  money,
  pushToast,
}: {
  tar: any[];
  loading?: boolean;
  openT: (row: any) => void;
  newTar: NewTariffForm;
  setNewTar: Dispatch<SetStateAction<NewTariffForm>>;
  createTariff: () => Promise<void>;
  meters: Array<{ id: number; service_name: string; meter_type_name?: string | null; display_name?: string | null; serial_number?: string | null; utility_type: string }>;
  fixedServiceNames: string[];
  selectedLedgerService: string;
  setSelectedLedgerService: Dispatch<SetStateAction<string>>;
  ledgerForm: {
    year: number;
    month: number;
    accrued: string;
    paid: string;
    adjustment: string;
    benefit: string;
    subsidy: string;
  };
  setLedgerForm: Dispatch<
    SetStateAction<{
      year: number;
      month: number;
      accrued: string;
      paid: string;
      adjustment: string;
      benefit: string;
      subsidy: string;
    }>
  >;
  saveServiceLedgerMonth: () => Promise<void>;
  ledgerHistory: Array<{
    year: number;
    month: number;
    accrued: string;
    paid: string;
    closing_balance: string;
  }>;
  ledgerHistoryLoading: boolean;
  electricityPlanForm: {
    plan_mode: "single" | "day_night" | "tri_zone";
    meter_id: string;
    effective_from: string;
    single_service_name: string;
    day_service_name: string;
    night_service_name: string;
    peak_service_name: string;
    semi_peak_service_name: string;
    off_peak_service_name: string;
    single_price_per_unit: string;
    day_price_per_unit: string;
    night_price_per_unit: string;
    peak_price_per_unit: string;
    semi_peak_price_per_unit: string;
    off_peak_price_per_unit: string;
    single_initial_reading: string;
    day_initial_reading: string;
    night_initial_reading: string;
    peak_initial_reading: string;
    semi_peak_initial_reading: string;
    off_peak_initial_reading: string;
  };
  setElectricityPlanForm: Dispatch<
    SetStateAction<{
      plan_mode: "single" | "day_night" | "tri_zone";
      meter_id: string;
      effective_from: string;
      single_service_name: string;
      day_service_name: string;
      night_service_name: string;
      peak_service_name: string;
      semi_peak_service_name: string;
      off_peak_service_name: string;
      single_price_per_unit: string;
      day_price_per_unit: string;
      night_price_per_unit: string;
      peak_price_per_unit: string;
      semi_peak_price_per_unit: string;
      off_peak_price_per_unit: string;
      single_initial_reading: string;
      day_initial_reading: string;
      night_initial_reading: string;
      peak_initial_reading: string;
      semi_peak_initial_reading: string;
      off_peak_initial_reading: string;
    }>
  >;
  electricityMeters: Array<{ id: number; service_name: string; meter_type_name?: string | null; display_name?: string | null; serial_number?: string | null; initial_reading?: string | number }>;
  electricityPlans: ElectricityPlanHistoryItem[];
  saveElectricityPlan: () => Promise<void>;
  deleteElectricityPlan: (planId: number) => Promise<void>;
  apartmentId?: number | null;
  automations: AutomationItem[];
  providers: ProviderItem[];
  registeredResidents?: string | number;
  areaM2?: string | number;
  money: (v: unknown) => string;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
}) {
  const [addTariffOpen, setAddTariffOpen] = useState(false);
  const [chargeScenario, setChargeScenario] = useState<TariffScenario>("fixed_amount");
  const [parameterBase, setParameterBase] = useState<ParameterBase>("apartment_registered_residents");
  const [meteredPlanMode, setMeteredPlanMode] = useState<"single" | "day_night" | "tri_zone">("single");
  const [dualPlan, setDualPlan] = useState<DualPlanDraft>(DEFAULT_DUAL_PLAN);
  const [triPlan, setTriPlan] = useState<TriPlanDraft>(DEFAULT_TRI_PLAN);
  const [editingElectricityPlanId, setEditingElectricityPlanId] = useState<number | null>(null);

  const sourceOptions = tar
    .map((x) => x.service_name)
    .filter((name, idx, arr) => !!name && arr.indexOf(name) === idx && name !== newTar.service_name);
  const serviceOptions = useMemo(
    () =>
      Array.from(
        new Set([
          ...SERVICE_PRESETS,
          ...fixedServiceNames,
          ...meters.map((meter) => meter.display_name || meter.meter_type_name || meter.service_name),
          ...sourceOptions,
          ...tar.map((row) => row.service_name).filter(Boolean),
        ]),
      ).sort((a, b) => a.localeCompare(b, "uk")),
    [fixedServiceNames, meters, sourceOptions, tar],
  );
  const isMetered = newTar.charge_mode === "metered";
  const isDualPlan = isMetered && meteredPlanMode === "day_night";
  const isTriZonePlan = isMetered && meteredPlanMode === "tri_zone";
  const selectedProvider = providers.find((provider) => String(provider.id) === newTar.provider_id);
  const matchingAutomations = automations
    .filter((item) => item.apartment_id === apartmentId)
    .filter((item) => String(item.provider_id || "") === newTar.provider_id);
  const matchingAutomation = matchingAutomations[0] || null;
  const selectedTariffMeter = meters.find((meter) => String(meter.id) === newTar.meter_id) || null;
  const selectedDualPlanMeter = electricityMeters.find((meter) => String(meter.id) === dualPlan.meter_id) || null;
  const selectedTriPlanMeter = electricityMeters.find((meter) => String(meter.id) === triPlan.meter_id) || null;
  const selectedElectricityPlanMeter =
    electricityMeters.find((meter) => String(meter.id) === electricityPlanForm.meter_id) || null;
  const isElectricityService = (newTar.service_name || "").toLowerCase().includes("електро");
  const selectedServiceFromCatalog = serviceOptions.includes(newTar.service_name);
  const residentsCount = Number(registeredResidents || 0);
  const areaValue = Number(areaM2 || 0);

  const applyScenario = (scenario: TariffScenario) => {
    setChargeScenario(scenario);
    if (scenario === "fixed_amount") {
      setMeteredPlanMode("single");
      setNewTar((s) => ({
        ...s,
        charge_mode: "fixed",
        unit_name: "month",
        fixed_quantity_source: "unit",
        fixed_quantity_multiplier: "1",
        meter_id: "",
        meter_register: "total",
        source_service_name: "",
      }));
      return;
    }
    if (scenario === "per_parameter") {
      setMeteredPlanMode("single");
      setParameterBase((current) => current || "apartment_registered_residents");
      setNewTar((s) => ({
        ...s,
        charge_mode: "fixed",
        unit_name: "month",
        fixed_quantity_source:
          s.source_service_name && s.source_service_name !== ""
            ? "unit"
            : s.fixed_quantity_source === "apartment_area_m2" || s.fixed_quantity_source === "apartment_registered_residents"
              ? s.fixed_quantity_source
              : "apartment_registered_residents",
        fixed_quantity_multiplier: s.fixed_quantity_multiplier || "1",
        meter_id: "",
        meter_register: "total",
      }));
      return;
    }
    setNewTar((s) => ({
      ...s,
      charge_mode: "metered",
      unit_name: s.service_name.toLowerCase().includes("газ") || s.service_name.toLowerCase().includes("вод")
        ? "m3"
        : "kWh",
      fixed_quantity_source: "auto",
      fixed_quantity_multiplier: "1",
    }));
  };

  const applyServicePreset = (serviceName: string) => {
    setNewTar((s) => ({ ...s, service_name: serviceName }));
    const normalized = serviceName.trim().toLowerCase();
    if (!normalized) return;
    if (normalized.includes("інтернет") || normalized.includes("оренд")) {
      applyScenario("fixed_amount");
      return;
    }
    if (normalized.includes("сміт")) {
      setParameterBase("apartment_registered_residents");
      applyScenario("per_parameter");
      setNewTar((s) => ({
        ...s,
        service_name: serviceName,
        fixed_quantity_source: "apartment_registered_residents",
      }));
      return;
    }
    if (normalized.includes("комунал")) {
      setParameterBase("apartment_area_m2");
      applyScenario("per_parameter");
      setNewTar((s) => ({
        ...s,
        service_name: serviceName,
        fixed_quantity_source: "apartment_area_m2",
      }));
      return;
    }
    if (normalized.includes("водовідвед")) {
      setParameterBase("linked_service");
      applyScenario("per_parameter");
      setNewTar((s) => ({
        ...s,
        service_name: serviceName,
        charge_mode: "metered",
        unit_name: "m3",
        source_service_name: "Водопостачання",
        meter_id: "",
        meter_register: "total",
      }));
      return;
    }
    if (normalized.includes("електро")) {
      applyScenario("metered");
      setNewTar((s) => ({ ...s, service_name: serviceName, unit_name: "kWh" }));
      return;
    }
    if (normalized.includes("газ") || normalized.includes("вод")) {
      applyScenario("metered");
      setNewTar((s) => ({ ...s, service_name: serviceName, unit_name: "m3" }));
      return;
    }
    applyScenario("fixed_amount");
  };

  const openAddTariffModal = () => {
    setAddTariffOpen(true);
    setChargeScenario("fixed_amount");
    setParameterBase("apartment_registered_residents");
    setMeteredPlanMode("single");
    setNewTar((s) => ({
      ...s,
      service_name: "",
      charge_mode: "fixed",
      price_per_unit: "",
      unit_name: "month",
      effective_from: new Date().toISOString().slice(0, 10),
      initial_meter_reading: "",
      meter_serial_number: "",
      service_status: "active",
      disable_from_month: "",
      provider_id: "",
      provider_company: "",
      personal_account: "",
      meter_id: "",
      meter_register: "total",
      source_service_name: "",
      fixed_quantity_source: "unit",
      fixed_quantity_multiplier: "1",
    }));
    setDualPlan({
      meter_id: electricityPlanForm.meter_id || "",
      effective_from: electricityPlanForm.effective_from || newTar.effective_from || "",
      day_service_name: electricityPlanForm.day_service_name || DEFAULT_DUAL_PLAN.day_service_name,
      night_service_name:
        electricityPlanForm.night_service_name || DEFAULT_DUAL_PLAN.night_service_name,
      day_price_per_unit: electricityPlanForm.day_price_per_unit || "",
      night_price_per_unit: electricityPlanForm.night_price_per_unit || "",
      day_initial_reading: electricityPlanForm.day_initial_reading || "",
      night_initial_reading: electricityPlanForm.night_initial_reading || "",
    });
    setTriPlan({
      meter_id: electricityPlanForm.meter_id || "",
      effective_from: electricityPlanForm.effective_from || newTar.effective_from || "",
      peak_service_name: electricityPlanForm.peak_service_name || DEFAULT_TRI_PLAN.peak_service_name,
      semi_peak_service_name:
        electricityPlanForm.semi_peak_service_name || DEFAULT_TRI_PLAN.semi_peak_service_name,
      off_peak_service_name: electricityPlanForm.off_peak_service_name || DEFAULT_TRI_PLAN.off_peak_service_name,
      peak_price_per_unit: electricityPlanForm.peak_price_per_unit || "",
      semi_peak_price_per_unit: electricityPlanForm.semi_peak_price_per_unit || "",
      off_peak_price_per_unit: electricityPlanForm.off_peak_price_per_unit || "",
      peak_initial_reading: electricityPlanForm.peak_initial_reading || "",
      semi_peak_initial_reading: electricityPlanForm.semi_peak_initial_reading || "",
      off_peak_initial_reading: electricityPlanForm.off_peak_initial_reading || "",
    });
  };

  const closeAddTariffModal = () => {
    setAddTariffOpen(false);
  };
  const loadElectricityPlanForEdit = (plan: ElectricityPlanHistoryItem) => {
    setEditingElectricityPlanId(plan.id);
    setElectricityPlanForm((s) => ({
      ...s,
      plan_mode: (plan.plan_mode as "single" | "day_night" | "tri_zone") || "single",
      meter_id: String(plan.meter_id),
      effective_from: plan.effective_from,
      single_service_name: plan.single_service_name || "Електроенергія",
      day_service_name: plan.day_service_name || "Електроенергія денний тариф",
      night_service_name: plan.night_service_name || "Електроенергія нічний тариф",
      peak_service_name: plan.peak_service_name || "Електроенергія піковий тариф",
      semi_peak_service_name: plan.semi_peak_service_name || "Електроенергія напівпіковий тариф",
      off_peak_service_name: plan.off_peak_service_name || "Електроенергія нічний тариф",
      single_price_per_unit: plan.single_price_per_unit || "",
      day_price_per_unit: plan.day_price_per_unit || "",
      night_price_per_unit: plan.night_price_per_unit || "",
      peak_price_per_unit: plan.peak_price_per_unit || "",
      semi_peak_price_per_unit: plan.semi_peak_price_per_unit || "",
      off_peak_price_per_unit: plan.off_peak_price_per_unit || "",
      single_initial_reading: plan.single_initial_reading || "",
      day_initial_reading: plan.day_initial_reading || "",
      night_initial_reading: plan.night_initial_reading || "",
      peak_initial_reading: plan.peak_initial_reading || "",
      semi_peak_initial_reading: plan.semi_peak_initial_reading || "",
      off_peak_initial_reading: plan.off_peak_initial_reading || "",
    }));
  };

  const fixedFormulaPreview = (() => {
    if (chargeScenario === "per_parameter" && parameterBase === "linked_service") {
      return `Сума = тариф × обсяг послуги «${newTar.source_service_name || "донор"}»`;
    }
    if (newTar.charge_mode !== "fixed") return "";
    const multiplier = newTar.fixed_quantity_multiplier || "1";
    if (newTar.fixed_quantity_source === "apartment_registered_residents") {
      return `Сума = тариф × ${registeredResidents || 1} (прописані) × ${multiplier}`;
    }
    if (newTar.fixed_quantity_source === "apartment_area_m2") {
      return `Сума = тариф × ${areaM2 || 0} (м²) × ${multiplier}`;
    }
    if (newTar.fixed_quantity_source === "unit") {
      return `Сума = тариф × ${multiplier}`;
    }
    return `Сума = тариф × ${multiplier}`;
  })();

  const electricityPlanModeLabel = (mode: string) => {
    if (mode === "single") return "Однотарифний";
    if (mode === "day_night") return "День/Ніч";
    if (mode === "tri_zone") return "Тризонний";
    return mode;
  };
  const electricityModeHint =
    electricityPlanForm.plan_mode === "single"
      ? "Для однотарифного режиму залишаємо лише найнеобхідніші поля: один тариф і один стартовий показник."
      : electricityPlanForm.plan_mode === "day_night"
        ? "Денний і нічний тарифи згруповані по окремих картках. У кожній картці одразу видно ціну та стартовий показник."
        : "Для тризонного режиму кожна зона має власну картку з автоматичною назвою, тарифом і стартовим показником.";

  const submitAddTariff = async () => {
    if (isDualPlan) {
      if (!dualPlan.meter_id) {
        pushToast("Оберіть електролічильник для режиму День/Ніч", "error");
        return;
      }
      if (!dualPlan.effective_from) {
        pushToast("Вкажіть дату дії тарифу", "error");
        return;
      }
      if (!dualPlan.day_service_name.trim() || !dualPlan.night_service_name.trim()) {
        pushToast("Вкажіть назви денного і нічного тарифів", "error");
        return;
      }
      if (!dualPlan.day_price_per_unit.trim() || !dualPlan.night_price_per_unit.trim()) {
        pushToast("Вкажіть ціни для денного і нічного тарифів", "error");
        return;
      }
      if (!dualPlan.day_initial_reading.trim() || !dualPlan.night_initial_reading.trim()) {
        pushToast("Вкажіть стартові показники day і night після перепрограмування", "error");
        return;
      }
      setElectricityPlanForm((s) => ({
        ...s,
        plan_mode: "day_night",
        single_initial_reading: "",
        meter_id: dualPlan.meter_id,
        effective_from: dualPlan.effective_from,
        day_service_name: dualPlan.day_service_name.trim(),
        night_service_name: dualPlan.night_service_name.trim(),
        day_price_per_unit: dualPlan.day_price_per_unit.trim(),
        night_price_per_unit: dualPlan.night_price_per_unit.trim(),
        day_initial_reading: dualPlan.day_initial_reading.trim(),
        night_initial_reading: dualPlan.night_initial_reading.trim(),
      }));
      await saveElectricityPlan();
      closeAddTariffModal();
      return;
    }
    if (isTriZonePlan) {
      if (!triPlan.meter_id || !triPlan.effective_from) {
        pushToast("Оберіть лічильник і дату дії тризонного режиму", "error");
        return;
      }
      if (
        !triPlan.peak_price_per_unit.trim() ||
        !triPlan.semi_peak_price_per_unit.trim() ||
        !triPlan.off_peak_price_per_unit.trim()
      ) {
        pushToast("Вкажіть тарифи peak / semi_peak / off_peak", "error");
        return;
      }
      if (
        !triPlan.peak_initial_reading.trim() ||
        !triPlan.semi_peak_initial_reading.trim() ||
        !triPlan.off_peak_initial_reading.trim()
      ) {
        pushToast("Вкажіть стартові показники peak / semi_peak / off_peak", "error");
        return;
      }
      setElectricityPlanForm((s) => ({
        ...s,
        plan_mode: "tri_zone",
        meter_id: triPlan.meter_id,
        effective_from: triPlan.effective_from,
        peak_service_name: triPlan.peak_service_name.trim(),
        semi_peak_service_name: triPlan.semi_peak_service_name.trim(),
        off_peak_service_name: triPlan.off_peak_service_name.trim(),
        peak_price_per_unit: triPlan.peak_price_per_unit.trim(),
        semi_peak_price_per_unit: triPlan.semi_peak_price_per_unit.trim(),
        off_peak_price_per_unit: triPlan.off_peak_price_per_unit.trim(),
        peak_initial_reading: triPlan.peak_initial_reading.trim(),
        semi_peak_initial_reading: triPlan.semi_peak_initial_reading.trim(),
        off_peak_initial_reading: triPlan.off_peak_initial_reading.trim(),
      }));
      await saveElectricityPlan();
      closeAddTariffModal();
      return;
    }

    const selectedElectricityMeter = electricityMeters.find((meter) => String(meter.id) === newTar.meter_id);
    if (isMetered && meteredPlanMode === "single" && selectedElectricityMeter) {
      if (!newTar.effective_from) {
        pushToast("Вкажіть дату дії тарифу", "error");
        return;
      }
      if (!newTar.price_per_unit.trim()) {
        pushToast("Вкажіть тариф для електроенергії", "error");
        return;
      }
      setElectricityPlanForm((s) => ({
        ...s,
        plan_mode: "single",
        meter_id: newTar.meter_id,
        effective_from: newTar.effective_from,
        single_service_name: newTar.service_name.trim() || "Електроенергія",
        single_price_per_unit: newTar.price_per_unit.trim(),
        single_initial_reading:
          newTar.initial_meter_reading.trim() ||
          String(selectedElectricityMeter.initial_reading ?? ""),
      }));
      await saveElectricityPlan();
      closeAddTariffModal();
      return;
    }

    if (isMetered && newTar.unit_name === "month") {
      setNewTar((s) => ({ ...s, unit_name: "kWh" }));
    }
    await createTariff();
    closeAddTariffModal();
  };

  return (
    <>
      <div className="subcard">
        <div className="title-row">
          <h4>Тарифи</h4>
          <button onClick={openAddTariffModal}>Додати тариф</button>
        </div>
        {loading ? (
          <div className="skeleton-block" aria-hidden="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}
        <div className="table-wrap mobile-hide-table">
          <table>
            <thead>
              <tr>
                <th>Послуга</th>
                <th>Тариф</th>
                <th>Одиниця</th>
                <th>Особовий рахунок</th>
                <th>Постачальник</th>
                <th>Статус</th>
                <th>Автоперевірка</th>
                <th>Остання звірка</th>
                <th></th>
              </tr>
            </thead>
            <tbody>{tar.map((r) => <TariffRow key={r.service_name} row={r} open={openT} />)}</tbody>
          </table>
        </div>
        <div className="mobile-cards">
          {tar.map((r) => (
            <article className="mobile-card" key={`tariff-mobile-${r.service_name}`}>
              <div className="mobile-card-title">
                <strong>{r.service_name}</strong>
                <span>{money(r.price_per_unit)}</span>
              </div>
              <div className="mobile-card-meta">Одиниця: {r.unit_name}</div>
              {r.charge_mode === "fixed" && (
                <div className="mobile-card-meta">
                  Формула:{" "}
                  {r.fixed_quantity_source === "apartment_registered_residents"
                    ? `тариф × прописані × ${r.fixed_quantity_multiplier || 1}`
                    : r.fixed_quantity_source === "apartment_area_m2"
                      ? `тариф × м² × ${r.fixed_quantity_multiplier || 1}`
                    : r.fixed_quantity_source === "unit"
                      ? `тариф × ${r.fixed_quantity_multiplier || 1}`
                      : `авто × ${r.fixed_quantity_multiplier || 1}`}
                </div>
              )}
              <div className="mobile-card-meta">Особовий: {r.personal_account || "—"}</div>
              <div className="mobile-card-meta">Статус: {r.is_active_for_period ? "Активна" : "Неактивна"}</div>
              {submitBadge(r) ? <div className="mobile-card-meta">Automation: {submitBadge(r)}</div> : null}
              <div className="row-actions top-gap">
                <button className="secondary" onClick={() => openT(r)}>
                  Налаштувати
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>

      {addTariffOpen && (
        <Modal title="Додати тариф" onClose={closeAddTariffModal}>
          <div className="subcard">
            <h4>Крок 1. Тип нарахування</h4>
            <div className="tariff-scenario-grid">
              {TARIFF_SCENARIOS.map((scenario) => (
                <button
                  key={scenario.id}
                  type="button"
                  className={`tariff-scenario-card ${chargeScenario === scenario.id ? "active" : ""}`}
                  onClick={() => applyScenario(scenario.id)}
                >
                  <strong>{scenario.title}</strong>
                  <span>{scenario.description}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="forms-grid compact-grid">
            <div className="full-row">
              <h4>Крок 2. Послуга та розрахунок</h4>
            </div>
            <Se
              tip="Послуга"
              help="Оберіть послугу зі списку. Якщо потрібної немає, виберіть свою назву нижче."
              value={serviceOptions.includes(newTar.service_name) ? newTar.service_name : ""}
              onChange={(e) => applyServicePreset(e.target.value)}
            >
              <option value="">Оберіть зі списку</option>
              {serviceOptions.map((serviceName) => (
                <option key={serviceName} value={serviceName}>
                  {serviceName}
                </option>
              ))}
            </Se>
            {!selectedServiceFromCatalog ? (
              <In
                tip="Своя назва послуги"
                help="Заповнюйте лише якщо потрібної послуги немає у списку."
                placeholder="Наприклад: Охорона ЖК"
                value={newTar.service_name}
                onChange={(e) => setNewTar((s) => ({ ...s, service_name: e.target.value }))}
              />
            ) : (
              <In
                tip="Обрана послуга"
                help="Назва вже визначена вибором зі списку вище."
                value={newTar.service_name}
                readOnly
              />
            )}
            <In
              tip="Ціна"
              help={
                chargeScenario === "fixed_amount"
                  ? "Фіксована сума за повний місяць."
                  : chargeScenario === "per_parameter"
                    ? "Тариф за одну одиницю вибраної бази розрахунку."
                    : "Тариф за одну одиницю показника лічильника."
              }
              placeholder="0.00"
              value={newTar.price_per_unit}
              onChange={(e) => setNewTar((s) => ({ ...s, price_per_unit: e.target.value }))}
            />

            {chargeScenario === "fixed_amount" && (
              <>
                <In tip="Одиниця виміру" value="місяць" readOnly help="Для фіксованої суми множник завжди дорівнює 1." />
                <div className="full-row automation-window-preview">
                  <strong>Логіка розрахунку:</strong> Сума = тариф за місяць.
                </div>
              </>
            )}

            {chargeScenario === "per_parameter" && (
              <>
                <Se
                  tip="База розрахунку"
                  help="Оберіть, від чого саме буде рахуватися послуга."
                  value={parameterBase}
                  onChange={(e) => {
                    const nextBase = e.target.value as ParameterBase;
                    setParameterBase(nextBase);
                    if (nextBase === "linked_service") {
                      setNewTar((s) => ({
                        ...s,
                        charge_mode: "metered",
                        unit_name: "m3",
                        source_service_name: s.source_service_name || "Водопостачання",
                        meter_id: "",
                        meter_register: "total",
                      }));
                      return;
                    }
                    setNewTar((s) => ({
                      ...s,
                      charge_mode: "fixed",
                      unit_name: "month",
                      source_service_name: "",
                      meter_id: "",
                      fixed_quantity_source: nextBase,
                    }));
                  }}
                >
                  <option value="apartment_registered_residents">К-сть прописаних</option>
                  <option value="apartment_area_m2">Площа, м²</option>
                  <option value="linked_service">Рахувати від іншої послуги</option>
                </Se>
                {parameterBase === "linked_service" ? (
                  <>
                    <Se
                      tip="Послуга-донор"
                      help="Система візьме обсяг з цієї послуги і помножить на ваш тариф."
                      value={newTar.source_service_name}
                      onChange={(e) =>
                        setNewTar((s) => ({
                          ...s,
                          charge_mode: "metered",
                          unit_name: "m3",
                          source_service_name: e.target.value,
                          meter_id: "",
                          meter_register: "total",
                        }))
                      }
                    >
                      <option value="">Оберіть послугу-донор</option>
                      {sourceOptions.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </Se>
                    <In
                      tip="Одиниця виміру"
                      value="обсяг донорської послуги"
                      readOnly
                      help="Наприклад, для водовідведення це буде обсяг водопостачання."
                    />
                  </>
                ) : (
                  <>
                    <In
                      tip="Множник"
                      type="number"
                      min="0.001"
                      step="0.001"
                      help="Коефіцієнт для базового параметра."
                      value={newTar.fixed_quantity_multiplier}
                      onChange={(e) =>
                        setNewTar((s) => ({ ...s, fixed_quantity_multiplier: e.target.value }))
                      }
                    />
                    {parameterBase === "apartment_registered_residents" ? (
                      <div className="full-row tariff-context-box">
                        <strong>Поточна база:</strong>{" "}
                        {residentsCount > 0
                          ? `${residentsCount} прописаних в об'єкті.`
                          : "У картці об'єкта ще не заповнено кількість прописаних."}
                      </div>
                    ) : (
                      <div className="full-row tariff-context-box">
                        <strong>Поточна база:</strong>{" "}
                        {areaValue > 0
                          ? `${areaValue} м² загальної площі.`
                          : "У картці об'єкта ще не заповнено загальну площу."}
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {chargeScenario === "metered" && (
              <>
                <div className="full-row">
                  <h4>Крок 3. Логіка по лічильнику</h4>
                </div>
                <Se
                  tip="Режим лічильника"
                  help="Для електроенергії можна обрати багатозонний режим, для інших послуг використовується однотарифний."
                  value={meteredPlanMode}
                  onChange={(e) => setMeteredPlanMode(e.target.value as "single" | "day_night" | "tri_zone")}
                >
                  <option value="single">Однотарифний</option>
                  {isElectricityService ? <option value="day_night">День/Ніч</option> : null}
                  {isElectricityService ? <option value="tri_zone">Тризонний</option> : null}
                </Se>
              </>
            )}

            {!isDualPlan && !isTriZonePlan && chargeScenario === "metered" && (
              <Se
                tip="Одиниця тарифу"
                help="Для електроенергії використовується кВт·год, для газу та води м3."
                value={newTar.unit_name}
                onChange={(e) =>
                  setNewTar((s) => ({
                    ...s,
                    unit_name: e.target.value as "kWh" | "m3" | "month",
                  }))
                }
              >
                <option value="kWh">1 кВт·год</option>
                <option value="m3">1 м3</option>
              </Se>
            )}
            <In
              tip="Дата початку дії тарифу"
              help="З цієї дати тариф почне брати участь у розрахунках."
              type="date"
              value={newTar.effective_from}
              onChange={(e) => setNewTar((s) => ({ ...s, effective_from: e.target.value }))}
            />
            <In
              tip="Особовий рахунок"
              help="Номер особового рахунку в кабінеті або у виписках постачальника."
              placeholder="Особовий рахунок"
              value={newTar.personal_account}
              onChange={(e) => setNewTar((s) => ({ ...s, personal_account: e.target.value }))}
            />
            <Se
              tip="Постачальник (довідник)"
              help="Для автоматизованих постачальників можна використати вже підключений кабінет."
              value={newTar.provider_id}
              onChange={(e) =>
                setNewTar((s) => ({
                  ...s,
                  provider_id: e.target.value,
                  provider_company: e.target.value ? "" : s.provider_company,
                }))
              }
            >
              <option value="">Без довідника / вручну</option>
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {providerDisplayName(provider)}
                </option>
              ))}
            </Se>
            <In
              tip="Назва постачальника вручну"
              help="Потрібно лише якщо компанії немає в довіднику."
              placeholder="Назва компанії"
              value={newTar.provider_company}
              onChange={(e) => setNewTar((s) => ({ ...s, provider_company: e.target.value }))}
              readOnly={!!selectedProvider}
            />
            <Se
              tip="Статус послуги"
              help="Неактивну послугу система перестане враховувати з вказаного місяця."
              value={newTar.service_status}
              onChange={(e) =>
                setNewTar((s) => ({
                  ...s,
                  service_status: e.target.value as "active" | "inactive",
                }))
              }
            >
              <option value="active">Активна</option>
              <option value="inactive">Неактивна</option>
            </Se>
            {selectedProvider ? (
              <div className="full-row tariff-context-box">
                <strong>Постачальник:</strong> {providerDisplayName(selectedProvider)}
                {isAutomatedProvider(selectedProvider) ? " підтримує automation." : " працює як ручний довідник."}
              </div>
            ) : null}
            {matchingAutomation ? (
              <div className="full-row automation-window-preview">
                <strong>Знайдено підключену автоматизацію.</strong> Для цього тарифу буде використано вже налаштований кабінет
                {matchingAutomation.template_name ? ` «${matchingAutomation.template_name}»` : ""}.
                {matchingAutomation.personal_account ? ` Особовий рахунок: ${matchingAutomation.personal_account}.` : ""}
              </div>
            ) : selectedProvider && isAutomatedProvider(selectedProvider) ? (
              <div className="full-row tariff-context-box">
                Для цього постачальника ще немає automation саме для цього об&apos;єкта. Після збереження тариф можна одразу
                підключити у вкладці «Автоматизації».
              </div>
            ) : null}
            {newTar.service_status === "inactive" && (
              <In
                tip="Місяць, з якого послуга вимикається"
                type="month"
                value={newTar.disable_from_month}
                onChange={(e) => setNewTar((s) => ({ ...s, disable_from_month: e.target.value }))}
              />
            )}

            {isMetered && !isDualPlan && !(chargeScenario === "per_parameter" && parameterBase === "linked_service") && (
              <>
                <Se
                  tip="Лічильник для послуги"
                  help="Оберіть уже створений лічильник у системі. Для електролічильника стартові показники по зонах задаються в блоці режимів електролічильника."
                  value={newTar.meter_id}
                  onChange={(e) =>
                    setNewTar((s) => ({
                      ...s,
                      meter_id: e.target.value,
                      source_service_name: e.target.value ? "" : s.source_service_name,
                    }))
                  }
                >
                  <option value="">Оберіть лічильник</option>
                  {meters.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name || m.meter_type_name || m.service_name || "Лічильник"}
                      {m.serial_number ? ` (${m.serial_number})` : ""}
                    </option>
                  ))}
                </Se>
                {selectedTariffMeter && selectedTariffMeter.utility_type === "electricity" ? (
                  <div className="full-row tariff-context-box">
                    Для лічильника <strong>{selectedTariffMeter.display_name || selectedTariffMeter.meter_type_name || selectedTariffMeter.service_name || "Лічильник"}</strong>
                    {selectedTariffMeter.serial_number ? ` (${selectedTariffMeter.serial_number})` : ""} стартові показники
                    зон задаються в блоці <strong>«Режими електролічильника»</strong> нижче. У формі створення лічильника вони
                    більше не вводяться.
                  </div>
                ) : null}
                <In
                  tip="Реєстр показника"
                  help="Для більшості лічильників достатньо total."
                  placeholder="total / day / night"
                  value={newTar.meter_register}
                  onChange={(e) => setNewTar((s) => ({ ...s, meter_register: e.target.value }))}
                />
                <Se
                  tip="Рахувати від іншої послуги"
                  help="Необов'язково. Якщо обрати послугу-донор, власний лічильник не використовується."
                  value={newTar.source_service_name}
                  onChange={(e) =>
                    setNewTar((s) => ({
                      ...s,
                      source_service_name: e.target.value,
                      meter_id: e.target.value ? "" : s.meter_id,
                    }))
                  }
                >
                  <option value="">Власний лічильник</option>
                  {sourceOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </Se>
                {!newTar.source_service_name && !newTar.meter_id && (
                  <>
                    <In
                      tip="Стартовий показник"
                      help="Потрібно лише якщо лічильник створюється разом з тарифом."
                      placeholder="Початковий показник"
                      value={newTar.initial_meter_reading}
                      onChange={(e) =>
                        setNewTar((s) => ({ ...s, initial_meter_reading: e.target.value }))
                      }
                    />
                    <In
                      tip="Серійний номер"
                      help="Необов'язково."
                      placeholder="Серійний номер"
                      value={newTar.meter_serial_number}
                      onChange={(e) =>
                        setNewTar((s) => ({ ...s, meter_serial_number: e.target.value }))
                      }
                    />
                  </>
                )}
              </>
            )}

            {isDualPlan && (
              <>
                <div className="full-row">
                  <h4>Крок 4. Налаштування День/Ніч</h4>
                </div>
                <Se
                  tip="Електролічильник"
                  value={dualPlan.meter_id}
                  onChange={(e) => setDualPlan((s) => ({ ...s, meter_id: e.target.value }))}
                >
                  <option value="">Оберіть лічильник</option>
                  {electricityMeters.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name || m.meter_type_name || m.service_name || "Лічильник"}
                      {m.serial_number ? ` (${m.serial_number})` : ""}
                    </option>
                  ))}
                </Se>
                {selectedDualPlanMeter ? (
                  <div className="full-row tariff-context-box">
                    Для вибраного лічильника <strong>{selectedDualPlanMeter.display_name || selectedDualPlanMeter.meter_type_name || selectedDualPlanMeter.service_name || "Лічильник"}</strong>
                    {selectedDualPlanMeter.serial_number ? ` (${selectedDualPlanMeter.serial_number})` : ""} стартові
                    показники зон <strong>День</strong> і <strong>Ніч</strong> задаються саме в цій формі.
                  </div>
                ) : null}
                <In
                  tip="Дата дії плану"
                  type="date"
                  value={dualPlan.effective_from}
                  onChange={(e) => setDualPlan((s) => ({ ...s, effective_from: e.target.value }))}
                />
                <In
                  tip="Назва денного тарифу"
                  value={dualPlan.day_service_name}
                  readOnly
                />
                <In
                  tip="Назва нічного тарифу"
                  value={dualPlan.night_service_name}
                  readOnly
                />
                <In
                  tip="Тариф day (грн/кВт·год)"
                  type="number"
                  min="0"
                  step="0.0001"
                  value={dualPlan.day_price_per_unit}
                  onChange={(e) =>
                    setDualPlan((s) => ({ ...s, day_price_per_unit: e.target.value }))
                  }
                />
                <In
                  tip="Тариф night (грн/кВт·год)"
                  type="number"
                  min="0"
                  step="0.0001"
                  value={dualPlan.night_price_per_unit}
                  onChange={(e) =>
                    setDualPlan((s) => ({ ...s, night_price_per_unit: e.target.value }))
                  }
                />
                <In
                  tip="Стартовий показник day"
                  type="number"
                  min="0"
                  step="0.001"
                  value={dualPlan.day_initial_reading}
                  onChange={(e) =>
                    setDualPlan((s) => ({ ...s, day_initial_reading: e.target.value }))
                  }
                />
                <In
                  tip="Стартовий показник night"
                  type="number"
                  min="0"
                  step="0.001"
                  value={dualPlan.night_initial_reading}
                  onChange={(e) =>
                    setDualPlan((s) => ({ ...s, night_initial_reading: e.target.value }))
                  }
                />
                <div className="full-row helper">
                  Для режиму День/Ніч ціна і стартовий показник згруповані поруч, щоб денну і нічну зони було видно одразу.
                </div>
              </>
            )}
            {isTriZonePlan && (
              <>
                <div className="full-row">
                  <h4>Крок 4. Налаштування тризонного режиму</h4>
                </div>
                <Se tip="Електролічильник" value={triPlan.meter_id} onChange={(e) => setTriPlan((s) => ({ ...s, meter_id: e.target.value }))}>
                  <option value="">Оберіть лічильник</option>
                  {electricityMeters.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name || m.meter_type_name || m.service_name || "Лічильник"}
                      {m.serial_number ? ` (${m.serial_number})` : ""}
                    </option>
                  ))}
                </Se>
                {selectedTriPlanMeter ? (
                  <div className="full-row tariff-context-box">
                    Для вибраного лічильника <strong>{selectedTriPlanMeter.display_name || selectedTriPlanMeter.meter_type_name || selectedTriPlanMeter.service_name || "Лічильник"}</strong>
                    {selectedTriPlanMeter.serial_number ? ` (${selectedTriPlanMeter.serial_number})` : ""} стартові
                    показники зон <strong>Пік</strong>, <strong>Напівпік</strong> і <strong>Ніч</strong> задаються саме в
                    цій формі.
                  </div>
                ) : null}
                <In tip="Дата дії плану" type="date" value={triPlan.effective_from} onChange={(e) => setTriPlan((s) => ({ ...s, effective_from: e.target.value }))} />
                <In tip="Назва пікового тарифу" value={triPlan.peak_service_name} readOnly />
                <In tip="Назва напівпікового тарифу" value={triPlan.semi_peak_service_name} readOnly />
                <In tip="Назва нічного тарифу" value={triPlan.off_peak_service_name} readOnly />
                <In tip="Тариф peak" type="number" min="0" step="0.0001" value={triPlan.peak_price_per_unit} onChange={(e) => setTriPlan((s) => ({ ...s, peak_price_per_unit: e.target.value }))} />
                <In tip="Тариф semi_peak" type="number" min="0" step="0.0001" value={triPlan.semi_peak_price_per_unit} onChange={(e) => setTriPlan((s) => ({ ...s, semi_peak_price_per_unit: e.target.value }))} />
                <In tip="Тариф off_peak" type="number" min="0" step="0.0001" value={triPlan.off_peak_price_per_unit} onChange={(e) => setTriPlan((s) => ({ ...s, off_peak_price_per_unit: e.target.value }))} />
                <In tip="Стартовий peak" type="number" min="0" step="0.001" value={triPlan.peak_initial_reading} onChange={(e) => setTriPlan((s) => ({ ...s, peak_initial_reading: e.target.value }))} />
                <In tip="Стартовий semi_peak" type="number" min="0" step="0.001" value={triPlan.semi_peak_initial_reading} onChange={(e) => setTriPlan((s) => ({ ...s, semi_peak_initial_reading: e.target.value }))} />
                <In tip="Стартовий off_peak" type="number" min="0" step="0.001" value={triPlan.off_peak_initial_reading} onChange={(e) => setTriPlan((s) => ({ ...s, off_peak_initial_reading: e.target.value }))} />
                <div className="full-row helper">
                  Для тризонного лічильника кожна зона має окрему картку з ціною та стартовим показником.
                </div>
              </>
            )}
          </div>
          {fixedFormulaPreview ? (
            <div className="automation-window-preview top-gap">
              <strong>Прев&apos;ю формули:</strong> {fixedFormulaPreview}
            </div>
          ) : null}
          <div className="row-actions top-gap">
            <button onClick={submitAddTariff}>
              {isTriZonePlan ? "Застосувати тризонний план" : isDualPlan ? "Застосувати план День/Ніч" : "Додати тариф"}
            </button>
            <button className="secondary" onClick={closeAddTariffModal}>
              Скасувати
            </button>
          </div>
        </Modal>
      )}

      <div className="subcard top-gap">
        <h4>Історія режимів електролічильника</h4>
        {!electricityMeters.length ? (
          <p className="helper">Активних електролічильників не знайдено.</p>
        ) : (
          <>
            <div className="title-row">
              <h4>{editingElectricityPlanId ? "Редагування режиму електролічильника" : "Новий режим електролічильника"}</h4>
              {editingElectricityPlanId ? (
                <button
                  className="secondary"
                  onClick={() => {
                    setEditingElectricityPlanId(null);
                    setElectricityPlanForm((s) => ({
                      ...s,
                      plan_mode: "single",
                    }));
                  }}
                >
                  Скасувати редагування
                </button>
              ) : null}
            </div>
            <div className="electricity-mode-shell">
              <div className="electricity-mode-toolbar">
              <Se
                tip="Режим"
                value={electricityPlanForm.plan_mode}
                help="Оберіть тип лічильника. Склад форми нижче зміниться автоматично."
                onChange={(e) =>
                  setElectricityPlanForm((s) => ({
                    ...s,
                    plan_mode: e.target.value as "single" | "day_night" | "tri_zone",
                  }))
                }
              >
                <option value="single">Однотарифний</option>
                <option value="day_night">День/Ніч</option>
                <option value="tri_zone">Тризонний</option>
              </Se>
              <Se
                tip="Електролічильник"
                value={electricityPlanForm.meter_id}
                help="Оберіть лічильник, для якого діятиме цей режим. Саме нижче задаються стартові показники по зонах."
                onChange={(e) =>
                  setElectricityPlanForm((s) => ({ ...s, meter_id: e.target.value }))
                }
              >
                <option value="">Оберіть лічильник</option>
                {electricityMeters.map((meter) => (
                  <option key={meter.id} value={meter.id}>
                    {meter.display_name || meter.meter_type_name || meter.service_name || "Лічильник"}
                    {meter.serial_number ? ` (${meter.serial_number})` : ""}
                  </option>
                ))}
              </Se>
              <In
                tip="Діє з"
                type="date"
                help="Дата запуску цього режиму після перепрограмування або заміни налаштувань."
                value={electricityPlanForm.effective_from}
                onChange={(e) =>
                  setElectricityPlanForm((s) => ({ ...s, effective_from: e.target.value }))
                }
              />
              </div>
              {selectedElectricityPlanMeter ? (
                <div className="automation-window-preview">
                  <strong>Важливо:</strong> для лічильника {selectedElectricityPlanMeter.display_name || selectedElectricityPlanMeter.meter_type_name || selectedElectricityPlanMeter.service_name || "Лічильник"}
                  {selectedElectricityPlanMeter.serial_number ? ` (${selectedElectricityPlanMeter.serial_number})` : ""} стартові
                  показники активних зон задаються саме в картках нижче. У формі створення лічильника вони не вводяться.
                </div>
              ) : null}
              <div className="automation-window-preview">
                <strong>Підказка:</strong> {electricityModeHint}
              </div>
              {electricityPlanForm.plan_mode === "single" ? (
                <div className="electricity-single-card">
                  <In
                    tip="Назва послуги"
                    help="Назва заповнюється автоматично і не потребує ручного редагування."
                    value={electricityPlanForm.single_service_name}
                    readOnly
                  />
                  <In
                    tip="Тариф, грн/кВт·год"
                    type="number"
                    min="0"
                    step="0.0001"
                    help="Ціна 1 кВт·год для всього лічильника."
                    value={electricityPlanForm.single_price_per_unit}
                    onChange={(e) =>
                      setElectricityPlanForm((s) => ({ ...s, single_price_per_unit: e.target.value }))
                    }
                  />
                  <In
                    tip="Стартовий показник total"
                    type="number"
                    min="0"
                    step="0.001"
                    help="Початковий total-показник після налаштування режиму."
                    value={electricityPlanForm.single_initial_reading}
                    onChange={(e) =>
                      setElectricityPlanForm((s) => ({ ...s, single_initial_reading: e.target.value }))
                    }
                  />
                </div>
              ) : electricityPlanForm.plan_mode === "day_night" ? (
                <div className="electricity-zone-grid">
                  <div className="electricity-zone-card day">
                    <div className="electricity-zone-head">
                      <strong>☀ День</strong>
                      <span className="helper">Основний денний тариф</span>
                    </div>
                    <In tip="Назва тарифу" value={electricityPlanForm.day_service_name} readOnly help="Заповнюється автоматично." />
                    <In
                      tip="Тариф, грн/кВт·год"
                      type="number"
                      min="0"
                      step="0.0001"
                      help="Вартість денного реєстру."
                      value={electricityPlanForm.day_price_per_unit}
                      onChange={(e) =>
                        setElectricityPlanForm((s) => ({ ...s, day_price_per_unit: e.target.value }))
                      }
                    />
                    <In
                      tip="Стартовий показник"
                      type="number"
                      min="0"
                      step="0.001"
                      help="Початковий показник денного реєстру."
                      value={electricityPlanForm.day_initial_reading}
                      onChange={(e) =>
                        setElectricityPlanForm((s) => ({ ...s, day_initial_reading: e.target.value }))
                      }
                    />
                  </div>
                  <div className="electricity-zone-card night">
                    <div className="electricity-zone-head">
                      <strong>☾ Ніч</strong>
                      <span className="helper">Пільговий нічний тариф</span>
                    </div>
                    <In tip="Назва тарифу" value={electricityPlanForm.night_service_name} readOnly help="Заповнюється автоматично." />
                    <In
                      tip="Тариф, грн/кВт·год"
                      type="number"
                      min="0"
                      step="0.0001"
                      help="Вартість нічного реєстру."
                      value={electricityPlanForm.night_price_per_unit}
                      onChange={(e) =>
                        setElectricityPlanForm((s) => ({ ...s, night_price_per_unit: e.target.value }))
                      }
                    />
                    <In
                      tip="Стартовий показник"
                      type="number"
                      min="0"
                      step="0.001"
                      help="Початковий показник нічного реєстру."
                      value={electricityPlanForm.night_initial_reading}
                      onChange={(e) =>
                        setElectricityPlanForm((s) => ({ ...s, night_initial_reading: e.target.value }))
                      }
                    />
                  </div>
                </div>
              ) : (
                <div className="electricity-zone-grid tri-zone">
                  <div className="electricity-zone-card peak">
                    <div className="electricity-zone-head">
                      <strong>⛰ Пік</strong>
                      <span className="helper">Найвищий тариф</span>
                    </div>
                    <In tip="Назва тарифу" value={electricityPlanForm.peak_service_name} readOnly help="Заповнюється автоматично." />
                    <In tip="Тариф, грн/кВт·год" type="number" min="0" step="0.0001" help="Вартість пікової зони." value={electricityPlanForm.peak_price_per_unit} onChange={(e) => setElectricityPlanForm((s) => ({ ...s, peak_price_per_unit: e.target.value }))} />
                    <In tip="Стартовий показник" type="number" min="0" step="0.001" help="Початковий показник пікового реєстру." value={electricityPlanForm.peak_initial_reading} onChange={(e) => setElectricityPlanForm((s) => ({ ...s, peak_initial_reading: e.target.value }))} />
                  </div>
                  <div className="electricity-zone-card semi">
                    <div className="electricity-zone-head">
                      <strong>☀ Напівпік</strong>
                      <span className="helper">Проміжна тарифна зона</span>
                    </div>
                    <In tip="Назва тарифу" value={electricityPlanForm.semi_peak_service_name} readOnly help="Заповнюється автоматично." />
                    <In tip="Тариф, грн/кВт·год" type="number" min="0" step="0.0001" help="Вартість напівпікової зони." value={electricityPlanForm.semi_peak_price_per_unit} onChange={(e) => setElectricityPlanForm((s) => ({ ...s, semi_peak_price_per_unit: e.target.value }))} />
                    <In tip="Стартовий показник" type="number" min="0" step="0.001" help="Початковий показник напівпікового реєстру." value={electricityPlanForm.semi_peak_initial_reading} onChange={(e) => setElectricityPlanForm((s) => ({ ...s, semi_peak_initial_reading: e.target.value }))} />
                  </div>
                  <div className="electricity-zone-card night">
                    <div className="electricity-zone-head">
                      <strong>☾ Ніч</strong>
                      <span className="helper">Найнижчий тариф</span>
                    </div>
                    <In tip="Назва тарифу" value={electricityPlanForm.off_peak_service_name} readOnly help="Заповнюється автоматично." />
                    <In tip="Тариф, грн/кВт·год" type="number" min="0" step="0.0001" help="Вартість нічної зони." value={electricityPlanForm.off_peak_price_per_unit} onChange={(e) => setElectricityPlanForm((s) => ({ ...s, off_peak_price_per_unit: e.target.value }))} />
                    <In tip="Стартовий показник" type="number" min="0" step="0.001" help="Початковий показник нічного реєстру." value={electricityPlanForm.off_peak_initial_reading} onChange={(e) => setElectricityPlanForm((s) => ({ ...s, off_peak_initial_reading: e.target.value }))} />
                  </div>
                </div>
              )}
            </div>
            <div className="automation-window-preview top-gap">
              <strong>Примітка:</strong> при зміні режиму формуйте окремі стартові показники для реєстрів після перепрограмування лічильника.
            </div>
            <div className="row-actions top-gap">
              <button
                onClick={async () => {
                  await saveElectricityPlan();
                  setEditingElectricityPlanId(null);
                }}
              >
                {editingElectricityPlanId ? "Оновити режим електрики" : "Зберегти режим електрики"}
              </button>
            </div>
          </>
        )}
        <div className="table-wrap top-gap">
          <table>
            <thead>
              <tr>
                <th>Діє з</th>
                <th>Лічильник</th>
                <th>Режим</th>
                <th>Тарифи</th>
                <th>Стартові показники</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {electricityPlans.length ? (
                electricityPlans.map((plan) => (
                  <tr key={plan.id}>
                    <td>{plan.effective_from}</td>
                    <td>
                      {plan.meter_service_name}
                      {plan.meter_serial_number ? <div className="helper">{plan.meter_serial_number}</div> : null}
                    </td>
                    <td>{electricityPlanModeLabel(plan.plan_mode)}</td>
                    <td>
                      {plan.plan_mode === "single" ? (
                        <>
                          {plan.single_service_name || "Електроенергія"}: {money(plan.single_price_per_unit || 0)}
                        </>
                      ) : plan.plan_mode === "day_night" ? (
                        <>
                          <div>{plan.day_service_name || "Day"}: {money(plan.day_price_per_unit || 0)}</div>
                          <div>{plan.night_service_name || "Night"}: {money(plan.night_price_per_unit || 0)}</div>
                        </>
                      ) : (
                        <>
                          <div>{plan.peak_service_name || "Peak"}: {money(plan.peak_price_per_unit || 0)}</div>
                          <div>{plan.semi_peak_service_name || "Semi-peak"}: {money(plan.semi_peak_price_per_unit || 0)}</div>
                          <div>{plan.off_peak_service_name || "Off-peak"}: {money(plan.off_peak_price_per_unit || 0)}</div>
                        </>
                      )}
                    </td>
                    <td>
                      {plan.plan_mode === "single" ? (
                        <>total: {plan.single_initial_reading || "—"}</>
                      ) : plan.plan_mode === "day_night" ? (
                        <>
                          <div>day: {plan.day_initial_reading || "—"}</div>
                          <div>night: {plan.night_initial_reading || "—"}</div>
                        </>
                      ) : (
                        <>
                          <div>peak: {plan.peak_initial_reading || "—"}</div>
                          <div>semi_peak: {plan.semi_peak_initial_reading || "—"}</div>
                          <div>off_peak: {plan.off_peak_initial_reading || "—"}</div>
                        </>
                      )}
                    </td>
                    <td>
                      <button className="secondary" onClick={() => loadElectricityPlanForEdit(plan)}>
                        Редагувати
                      </button>
                      <button
                        className="danger"
                        disabled={!plan.can_delete}
                        title={plan.can_delete ? "Видалити режим" : plan.delete_block_reason || "Видалення недоступне"}
                        onClick={async () => {
                          if (!plan.can_delete) {
                            pushToast(plan.delete_block_reason || "Видалення недоступне", "info");
                            return;
                          }
                          if (!window.confirm(`Видалити режим електрики з ${plan.effective_from}?`)) return;
                          await deleteElectricityPlan(plan.id);
                          if (editingElectricityPlanId === plan.id) setEditingElectricityPlanId(null);
                        }}
                      >
                        Видалити
                      </button>
                      {!plan.can_delete && plan.delete_block_reason ? (
                        <div className="helper">{plan.delete_block_reason}</div>
                      ) : null}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="helper">
                    Історія режимів поки порожня.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="subcard top-gap">
        <h4>Спрощений помісячний облік послуги</h4>
        {!fixedServiceNames.length ? (
          <p className="helper">Немає fixed-послуг для ведення помісячного обліку.</p>
        ) : (
          <>
            <div className="forms-grid">
              <Se
                tip="Послуга"
                value={selectedLedgerService}
                onChange={(e) => setSelectedLedgerService(e.target.value)}
              >
                {fixedServiceNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </Se>
              <In
                tip="Рік"
                type="number"
                min="2000"
                max="2100"
                value={ledgerForm.year}
                onChange={(e) => setLedgerForm((s) => ({ ...s, year: Number(e.target.value || s.year) }))}
              />
              <In
                tip="Місяць"
                type="number"
                min="1"
                max="12"
                value={ledgerForm.month}
                onChange={(e) => setLedgerForm((s) => ({ ...s, month: Number(e.target.value || s.month) }))}
              />
              <In
                tip="Нараховано"
                type="number"
                step="0.01"
                value={ledgerForm.accrued}
                onChange={(e) => setLedgerForm((s) => ({ ...s, accrued: e.target.value }))}
              />
              <In
                tip="Оплачено"
                type="number"
                step="0.01"
                value={ledgerForm.paid}
                onChange={(e) => setLedgerForm((s) => ({ ...s, paid: e.target.value }))}
              />
              <In
                tip="Перерахунок (+/-)"
                type="number"
                step="0.01"
                value={ledgerForm.adjustment}
                onChange={(e) => setLedgerForm((s) => ({ ...s, adjustment: e.target.value }))}
              />
              <In
                tip="Пільга"
                type="number"
                step="0.01"
                value={ledgerForm.benefit}
                onChange={(e) => setLedgerForm((s) => ({ ...s, benefit: e.target.value }))}
              />
              <In
                tip="Субсидія"
                type="number"
                step="0.01"
                value={ledgerForm.subsidy}
                onChange={(e) => setLedgerForm((s) => ({ ...s, subsidy: e.target.value }))}
              />
            </div>
            <button className="top-gap" onClick={saveServiceLedgerMonth}>
              Зберегти місячні дані
            </button>
            <div className="table-wrap top-gap">
              <table>
                <thead>
                  <tr>
                    <th>Період</th>
                    <th>Нараховано</th>
                    <th>Оплачено</th>
                    <th>Баланс на кінець</th>
                  </tr>
                </thead>
                <tbody>
                  {ledgerHistoryLoading && (
                    <tr>
                      <td colSpan={4}>
                        <span className="helper">Завантаження історії...</span>
                      </td>
                    </tr>
                  )}
                  {!ledgerHistoryLoading && ledgerHistory.length === 0 && (
                    <tr>
                      <td colSpan={4}>
                        <span className="helper">Поки що немає записів.</span>
                      </td>
                    </tr>
                  )}
                  {!ledgerHistoryLoading &&
                    ledgerHistory.map((row) => (
                      <tr key={`${row.year}-${row.month}`}>
                        <td>
                          {String(row.month).padStart(2, "0")}.{row.year}
                        </td>
                        <td>{money(row.accrued)}</td>
                        <td>{money(row.paid)}</td>
                        <td>{money(row.closing_balance)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
