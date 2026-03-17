import { useMemo, useState } from "react";
import { Modal } from "@/shared/ui/modal";
import type {
  AutomationCyclePreviewItem,
  AutomationCycleRunDetailResult,
  AutomationCycleRunResult,
  AutomationItem,
  AutomationRunLogItem,
  AutomationTemplateItem,
} from "@/shared/api/types";
import { dt } from "@/shared/utils/format";

type Draft = {
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
};

type TemplateForm = {
  code: string;
  name: string;
  provider_id: string;
  utility_type: string;
  cabinet_url: string;
  description: string;
  supports_accrual: boolean;
  supports_meter_submit: boolean;
  is_active: boolean;
};

type ConnectionForm = {
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
};

type StatusTone = "ok" | "draft" | "error";

const slugifyTemplatePart = (value: string) =>
  String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_");

const buildTemplateCode = (name: string, providerName?: string | null) => {
  const provider = slugifyTemplatePart(providerName || "provider");
  const label = slugifyTemplatePart(name || "template");
  return `${provider}_${label}`;
};

const rowKey = (row: AutomationItem) => `${row.automation_id || `${row.apartment_id}:${row.service_name}`}`;

const statusView = (status?: string | null): { label: string; tone: StatusTone } => {
  if (status === "updated") return { label: "Оновлено", tone: "ok" };
  if (status === "no_change") return { label: "Без змін", tone: "ok" };
  if (status === "waiting") return { label: "Очікування", tone: "draft" };
  if (status === "error") return { label: "Помилка", tone: "error" };
  return { label: "Невідомо", tone: "draft" };
};

const shortDate = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${day}.${month}`;
};

const currentKyivDate = () => {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Kyiv",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(new Date());
  const year = Number(parts.find((part) => part.type === "year")?.value || "0");
  const month = Number(parts.find((part) => part.type === "month")?.value || "0");
  const day = Number(parts.find((part) => part.type === "day")?.value || "0");
  return { year, month, day };
};

const isDayInWindow = (day: number, dayFrom: number, dayTo: number) => {
  if (dayFrom <= dayTo) return day >= dayFrom && day <= dayTo;
  return day >= dayFrom || day <= dayTo;
};

const submitPeriodLabel = (row: AutomationItem) => {
  if (!row.submit_target_year || !row.submit_target_month) return "—";
  return `${String(row.submit_target_month).padStart(2, "0")}.${row.submit_target_year}`;
};

const logTargetPeriodLabel = (log: AutomationRunLogItem) => {
  if (!log.target_year || !log.target_month) return "—";
  return `${String(log.target_month).padStart(2, "0")}.${log.target_year}`;
};

const cycleModeLabel = (mode?: string | null) => {
  if (mode === "manual") return "Ручний";
  if (mode === "dry-run") return "Dry-run";
  return "Плановий";
};

const cyclePhaseLabel = (phase?: string | null) => {
  if (phase === "accrual") return "Нарахування";
  if (phase === "submit") return "Подача";
  if (phase === "legacy") return "Legacy вимкнено";
  return phase || "—";
};

const previewReasonCodeLabel = (code?: string | null) => {
  switch (code) {
    case "accrual_ready":
      return "Accrual готовий";
    case "accrual_completed":
      return "Accrual завершено";
    case "submit_ready":
      return "Submit готовий";
    case "submit_disabled":
      return "Submit вимкнено";
    case "submit_missing_credentials":
      return "Немає credentials";
    case "submit_outside_window":
      return "Поза вікном";
    case "submit_missing_reading":
      return "Немає показника";
    case "submit_completed":
      return "Вже подано";
    default:
      return code || "—";
  }
};

const durationLabel = (durationMs?: number | null) => {
  if (!durationMs && durationMs !== 0) return "—";
  if (durationMs < 1000) return `${durationMs} мс`;
  return `${(durationMs / 1000).toFixed(1)} с`;
};

const submitState = (row: AutomationItem): { label: string; tone: StatusTone } => {
  if (!row.submit_enabled) return { label: "Submit вимкнено", tone: "draft" };
  const { day } = currentKyivDate();
  const inWindow = isDayInWindow(day, row.submit_window_day_from || 28, row.submit_window_day_to || 3);
  if (row.submit_completed_for_period) return { label: "Вже подано", tone: "ok" };
  if (inWindow) return { label: "Вікно відкрите", tone: "ok" };
  return { label: "Поза вікном", tone: "draft" };
};

const submitStateTone = (row: AutomationItem): StatusTone => {
  if (row.submit_completed_for_period) return "ok";
  const reason = (row.submit_state_reason || "").toLowerCase();
  if (reason.includes("бракує") || reason.includes("вимкн")) return "error";
  if (reason.includes("готово") || reason.includes("подано")) return "ok";
  return "draft";
};

const maskLogin = (value?: string | null) => {
  const raw = (value || "").trim();
  if (!raw) return "—";
  if (raw.length <= 4) return `${raw[0] || "*"}***`;
  return `${raw.slice(0, 3)}...${raw.slice(-2)}`;
};

const apartmentLabel = (row: Pick<AutomationItem, "apartment_address" | "apartment_code">) =>
  (row.apartment_address || "").trim() || (row.apartment_code || "").trim() || "—";

const lastResultText = (row: AutomationItem) => {
  const status = statusView(row.auto_check_status);
  const marker = status.tone === "error" ? "⚠" : "✅";
  return `${marker} ${status.label} ${shortDate(row.auto_check_last_checked_at || row.auto_check_last_updated_at)}`;
};

const missingDataMessage = (row: AutomationItem) => {
  const missingPassword = !(row.cabinet_password || "").trim();
  if (missingPassword) return "Автоматизація неможлива: бракує пароля у кабінеті.";
  const missingCore = !(row.cabinet_url || "").trim() || !(row.cabinet_login || "").trim();
  if (missingCore) return "Автоматизація обмежена: перевірте URL або логін.";
  return null;
};

export function AutomationsTab({
  automations,
  templates,
  loading,
  saveAutomation,
  runAutomation,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  connectTemplateToApartment,
  disconnectTemplateFromApartment,
  fetchAutomationLogs,
  runAutomationCycle,
  previewAutomationCycle,
  automationCycleRuns,
  fetchAutomationCycleRunDetail,
  selectedApartmentId,
  providers,
  onOpenTariffs,
}: {
  automations: AutomationItem[];
  templates: AutomationTemplateItem[];
  loading?: boolean;
  saveAutomation: (row: AutomationItem, draft: Draft) => Promise<void>;
  runAutomation: (row: AutomationItem, mode: "full" | "readings" | "tariffs") => Promise<void>;
  createTemplate: (payload: {
    code: string;
    name: string;
    provider_id: number | null;
    utility_type: "electricity" | "water" | "gas" | "heating" | "sewage" | "internet" | "other" | null;
    cabinet_url: string | null;
    description: string | null;
    supports_accrual: boolean;
    supports_meter_submit: boolean;
    is_active: boolean;
  }) => Promise<void>;
  updateTemplate: (
    templateId: number,
    payload: {
      code: string;
      name: string;
      provider_id: number | null;
      utility_type: "electricity" | "water" | "gas" | "heating" | "sewage" | "internet" | "other" | null;
      cabinet_url: string | null;
      description: string | null;
      supports_accrual: boolean;
      supports_meter_submit: boolean;
      is_active: boolean;
    },
  ) => Promise<void>;
  deleteTemplate: (templateId: number) => Promise<void>;
  connectTemplateToApartment: (
    templateId: number,
    apartmentId: number,
    payload: ConnectionForm,
  ) => Promise<void>;
  disconnectTemplateFromApartment: (row: AutomationItem) => Promise<void>;
  fetchAutomationLogs: (automationId: number) => Promise<AutomationRunLogItem[]>;
  runAutomationCycle: () => Promise<void>;
  previewAutomationCycle: () => Promise<{ items: AutomationCyclePreviewItem[]; message: string }>;
  automationCycleRuns: AutomationCycleRunResult[];
  fetchAutomationCycleRunDetail: (cycleRunId: number, apartmentId?: number | null) => Promise<AutomationCycleRunDetailResult>;
  selectedApartmentId?: number | null;
  providers: Array<{ id: number; name_full: string }>;
  onOpenTariffs?: () => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [expandedStatus, setExpandedStatus] = useState<Record<string, boolean>>({});
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [groupBusy, setGroupBusy] = useState<Record<string, boolean>>({});
  const [tab, setTab] = useState<"connections" | "cycles" | "templates">("connections");
  const [showConnectionFilters, setShowConnectionFilters] = useState(false);
  const [logsLoading, setLogsLoading] = useState<Record<string, boolean>>({});
  const [logsByKey, setLogsByKey] = useState<Record<string, AutomationRunLogItem[]>>({});
  const [templateSaving, setTemplateSaving] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [connectTemplate, setConnectTemplate] = useState<AutomationTemplateItem | null>(null);
  const [connectionSaving, setConnectionSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [logQueryByKey, setLogQueryByKey] = useState<Record<string, string>>({});
  const [logRegisterFilterByKey, setLogRegisterFilterByKey] = useState<Record<string, string>>({});
  const [cycleRunning, setCycleRunning] = useState(false);
  const [cyclePreviewLoading, setCyclePreviewLoading] = useState(false);
  const [cyclePreview, setCyclePreview] = useState<AutomationCyclePreviewItem[]>([]);
  const [showCyclePreview, setShowCyclePreview] = useState(false);
  const [selectedCycleRunDetail, setSelectedCycleRunDetail] = useState<AutomationCycleRunDetailResult | null>(null);
  const [cycleDetailLoading, setCycleDetailLoading] = useState(false);
  const [cycleDetailApartmentFilter, setCycleDetailApartmentFilter] = useState<string>(selectedApartmentId ? String(selectedApartmentId) : "");
  const [cycleModeFilter, setCycleModeFilter] = useState("all");
  const [cycleQuery, setCycleQuery] = useState("");
  const [previewActionFilter, setPreviewActionFilter] = useState("all");
  const [filterQuery, setFilterQuery] = useState("");
  const [filterErrorsOnly, setFilterErrorsOnly] = useState(false);
  const [filterSubmitWindowOnly, setFilterSubmitWindowOnly] = useState(false);
  const [filterAwaitingReadingOnly, setFilterAwaitingReadingOnly] = useState(false);
  const [templateForm, setTemplateForm] = useState<TemplateForm>({
    code: "",
    name: "",
    provider_id: "",
    utility_type: "",
    cabinet_url: "",
    description: "",
    supports_accrual: true,
    supports_meter_submit: false,
    is_active: true,
  });
  const [connectionForm, setConnectionForm] = useState<ConnectionForm>({
    personal_account: "",
    cabinet_url: "",
    cabinet_login: "",
    cabinet_password: "",
    accrual_enabled: true,
    accrual_time: "09:00",
    accrual_window_day_from: "1",
    accrual_window_day_to: "10",
    submit_enabled: false,
    submit_time: "09:00",
    submit_window_day_from: "28",
    submit_window_day_to: "3",
  });

  const ensureDraft = (row: AutomationItem): Draft =>
    drafts[rowKey(row)] || {
      provider_company: row.provider_company || "",
      personal_account: row.personal_account || "",
      cabinet_url: row.cabinet_url || "",
      cabinet_login: row.cabinet_login || "",
      auto_check_enabled: !!row.auto_check_enabled,
      auto_check_time: row.auto_check_time || "09:00",
      auto_check_timezone: row.auto_check_timezone || "Europe/Kyiv",
      auto_check_window_day_from: String(row.auto_check_window_day_from || 1),
      auto_check_window_day_to: String(row.auto_check_window_day_to || 10),
      submit_enabled: !!row.submit_enabled,
      submit_time: row.submit_time || "09:00",
      submit_window_day_from: String(row.submit_window_day_from || 28),
      submit_window_day_to: String(row.submit_window_day_to || 3),
      cabinet_password: row.cabinet_password || "",
    };

  const sorted = useMemo(
    () =>
      [...automations].sort((a, b) =>
        `${apartmentLabel(a)}:${a.service_name}`.localeCompare(`${apartmentLabel(b)}:${b.service_name}`, "uk"),
      ),
    [automations],
  );

  const filteredAutomationItems = useMemo(() => {
    const query = filterQuery.trim().toLowerCase();
    return sorted.filter((item) => {
      if (selectedApartmentId && selectedApartmentId > 0 && item.apartment_id !== selectedApartmentId) return false;
      if (query) {
        const haystack = [
          item.service_name,
          item.provider_name || "",
          item.provider_company || "",
          item.apartment_address || "",
          item.submit_state_reason || "",
          item.auto_check_message || "",
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      if (filterErrorsOnly && item.auto_check_status !== "error") return false;
      if (filterSubmitWindowOnly && submitState(item).label !== "Вікно відкрите") return false;
      if (
        filterAwaitingReadingOnly &&
        !(item.submit_enabled && (item.submit_state_reason || "").toLowerCase().includes("немає показника"))
      ) {
        return false;
      }
      return true;
    });
  }, [sorted, selectedApartmentId, filterQuery, filterErrorsOnly, filterSubmitWindowOnly, filterAwaitingReadingOnly]);

  const grouped = useMemo(() => {
    const map = new Map<number, { apartment_id: number; apartment_address: string; items: AutomationItem[] }>();
    for (const item of filteredAutomationItems) {
      if (!map.has(item.apartment_id)) {
        map.set(item.apartment_id, {
          apartment_id: item.apartment_id,
          apartment_address: item.apartment_address,
          items: [],
        });
      }
      map.get(item.apartment_id)?.items.push(item);
    }
    return [...map.values()].sort((a, b) =>
      apartmentLabel({ apartment_address: a.apartment_address, apartment_code: "" }).localeCompare(
        apartmentLabel({ apartment_address: b.apartment_address, apartment_code: "" }),
        "uk",
      ),
    );
  }, [filteredAutomationItems]);

  const groupedCyclePreview = useMemo(() => {
    const previewMap = new Map<
      string,
      { apartment_id: number; apartment_address: string; phases: Map<string, AutomationCyclePreviewItem[]> }
    >();
    for (const item of cyclePreview) {
      const apartmentKey = `${item.apartment_id}:${item.apartment_address}`;
      if (!previewMap.has(apartmentKey)) {
        previewMap.set(apartmentKey, {
          apartment_id: item.apartment_id,
          apartment_address: item.apartment_address,
          phases: new Map(),
        });
      }
      const apartmentGroup = previewMap.get(apartmentKey)!;
      if (!apartmentGroup.phases.has(item.phase)) apartmentGroup.phases.set(item.phase, []);
      apartmentGroup.phases.get(item.phase)!.push(item);
    }
    return [...previewMap.values()].sort((a, b) => a.apartment_address.localeCompare(b.apartment_address, "uk"));
  }, [cyclePreview]);

  const cycleReasonSummary = useMemo(() => {
    const map = new Map<string, { phase: string; action: string; reason_code: string; reason: string; count: number }>();
    for (const item of cyclePreview) {
      if (previewActionFilter !== "all" && item.action !== previewActionFilter) continue;
      const key = `${item.phase}|${item.action}|${item.reason_code}`;
      const current = map.get(key);
      if (current) {
        current.count += 1;
        continue;
      }
      map.set(key, {
        phase: item.phase,
        action: item.action,
        reason_code: item.reason_code,
        reason: item.reason,
        count: 1,
      });
    }
    return [...map.values()].sort((a, b) => b.count - a.count || a.phase.localeCompare(b.phase, "uk"));
  }, [cyclePreview, previewActionFilter]);

  const filteredGroupedCyclePreview = useMemo(() => {
    return groupedCyclePreview
      .map((group) => ({
        ...group,
        phases: new Map<string, AutomationCyclePreviewItem[]>(
          [...group.phases.entries()]
            .map(
              ([phase, items]): [string, AutomationCyclePreviewItem[]] => [
                phase,
                items.filter((item) => previewActionFilter === "all" || item.action === previewActionFilter),
              ],
            )
            .filter((entry): entry is [string, AutomationCyclePreviewItem[]] => entry[1].length > 0),
        ),
      }))
      .filter((group) => group.phases.size > 0);
  }, [groupedCyclePreview, previewActionFilter]);

  const filteredCycleRuns = useMemo(() => {
    const query = cycleQuery.trim().toLowerCase();
    return automationCycleRuns.filter((row) => {
      if (cycleModeFilter !== "all" && (row.trigger_mode || "scheduled") !== cycleModeFilter) return false;
      if (!query) return true;
      const haystack = [
        row.message || "",
        row.trigger_mode || "",
        dt(row.started_at || null),
        dt(row.finished_at || null),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [automationCycleRuns, cycleModeFilter, cycleQuery]);

  const cycleApartmentOptions = useMemo(() => {
    const map = new Map<number, string>();
    for (const item of automations) {
      if (!map.has(item.apartment_id)) map.set(item.apartment_id, apartmentLabel(item));
    }
    return [...map.entries()]
      .map(([apartment_id, label]) => ({ apartment_id, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "uk"));
  }, [automations]);

  const openCycleRunDetail = async (cycleRunId: number) => {
    setCycleDetailLoading(true);
    try {
      const apartmentId = cycleDetailApartmentFilter ? Number(cycleDetailApartmentFilter) : null;
      const detail = await fetchAutomationCycleRunDetail(cycleRunId, apartmentId);
      setSelectedCycleRunDetail(detail);
    } finally {
      setCycleDetailLoading(false);
    }
  };

  const editingRow = useMemo(() => sorted.find((item) => rowKey(item) === editingKey) || null, [editingKey, sorted]);

  const updateDraft = (row: AutomationItem, patch: Partial<Draft>) => {
    const key = rowKey(row);
    const current = ensureDraft(row);
    setDrafts((state) => ({ ...state, [key]: { ...current, ...patch } }));
  };

  const saveRow = async (row: AutomationItem) => {
    const key = rowKey(row);
    const current = ensureDraft(row);
    setSaving((state) => ({ ...state, [key]: true }));
    try {
      await saveAutomation(row, current);
    } finally {
      setSaving((state) => ({ ...state, [key]: false }));
    }
  };

  const runRow = async (row: AutomationItem) => {
    const key = rowKey(row);
    setRunning((state) => ({ ...state, [key]: true }));
    try {
      await runAutomation(row, "full");
    } finally {
      setRunning((state) => ({ ...state, [key]: false }));
    }
  };

  const toggleExpanded = async (row: AutomationItem) => {
    const key = rowKey(row);
    const isExpanded = !!expandedStatus[key];
    setExpandedStatus((s) => ({ ...s, [key]: !isExpanded }));
    if (!isExpanded && row.automation_id) {
      setLogsLoading((s) => ({ ...s, [key]: true }));
      try {
        const rows = await fetchAutomationLogs(row.automation_id);
        setLogsByKey((s) => ({ ...s, [key]: rows }));
      } finally {
        setLogsLoading((s) => ({ ...s, [key]: false }));
      }
    }
  };

  const pauseAllForApartment = async (group: { apartment_id: number; apartment_address: string; items: AutomationItem[] }) => {
    const busyKey = `pause-${group.apartment_id}`;
    setGroupBusy((state) => ({ ...state, [busyKey]: true }));
    try {
      for (const row of group.items) {
        updateDraft(row, { auto_check_enabled: false });
        const base = ensureDraft(row);
        await saveAutomation(row, { ...base, auto_check_enabled: false });
      }
    } finally {
      setGroupBusy((state) => ({ ...state, [busyKey]: false }));
    }
  };

  const runAllForApartment = async (group: { apartment_id: number; apartment_address: string; items: AutomationItem[] }) => {
    const busyKey = `run-${group.apartment_id}`;
    setGroupBusy((state) => ({ ...state, [busyKey]: true }));
    try {
      for (const row of group.items) {
        if (missingDataMessage(row)) continue;
        await runRow(row);
      }
    } finally {
      setGroupBusy((state) => ({ ...state, [busyKey]: false }));
    }
  };

  const resetTemplateForm = () => {
    setEditingTemplateId(null);
    setTemplateForm({
      code: "",
      name: "",
      provider_id: "",
      utility_type: "",
      cabinet_url: "",
      description: "",
      supports_accrual: true,
      supports_meter_submit: false,
      is_active: true,
    });
  };

  const editTemplate = (tpl: AutomationTemplateItem) => {
    setEditingTemplateId(tpl.id);
    setTemplateForm({
      code: tpl.code || "",
      name: tpl.name || "",
      provider_id: tpl.provider_id ? String(tpl.provider_id) : "",
      utility_type: tpl.utility_type || "",
      cabinet_url: tpl.cabinet_url || "",
      description: tpl.description || "",
      supports_accrual: !!tpl.supports_accrual,
      supports_meter_submit: !!tpl.supports_meter_submit,
      is_active: !!tpl.is_active,
    });
  };

  const openConnectModal = (tpl: AutomationTemplateItem) => {
    setConnectTemplate(tpl);
    setShowPassword(false);
    setConnectionForm({
      personal_account: "",
      cabinet_url: tpl.cabinet_url || "",
      cabinet_login: "",
      cabinet_password: "",
      accrual_enabled: !!tpl.supports_accrual,
      accrual_time: "09:00",
      accrual_window_day_from: "1",
      accrual_window_day_to: "10",
      submit_enabled: !!tpl.supports_meter_submit,
      submit_time: "09:00",
      submit_window_day_from: "28",
      submit_window_day_to: "3",
    });
  };

  const submitTemplate = async () => {
    if (!templateForm.name.trim()) return;
    setTemplateSaving(true);
    const generatedCode =
      templateForm.code.trim() ||
      buildTemplateCode(
        templateForm.name.trim(),
        providers.find((provider) => String(provider.id) === templateForm.provider_id)?.name_full,
      );
    const payload = {
      code: generatedCode,
      name: templateForm.name.trim(),
      provider_id: templateForm.provider_id ? Number(templateForm.provider_id) : null,
      utility_type: (templateForm.utility_type || null) as
        | "electricity"
        | "water"
        | "gas"
        | "heating"
        | "sewage"
        | "internet"
        | "other"
        | null,
      cabinet_url: templateForm.cabinet_url.trim() || null,
      description: templateForm.description.trim() || null,
      supports_accrual: !!templateForm.supports_accrual,
      supports_meter_submit: !!templateForm.supports_meter_submit,
      is_active: !!templateForm.is_active,
    };
    try {
      if (editingTemplateId) await updateTemplate(editingTemplateId, payload);
      else await createTemplate(payload);
      resetTemplateForm();
    } finally {
      setTemplateSaving(false);
    }
  };

  const filteredLogs = (key: string) => {
    const query = (logQueryByKey[key] || "").trim().toLowerCase();
    const registerFilter = (logRegisterFilterByKey[key] || "").trim().toLowerCase();
    const rows = logsByKey[key] || [];
    return rows.filter((log) => {
      if (registerFilter && (log.register_name || "").toLowerCase() !== registerFilter) return false;
      if (!query) return true;
      return [log.status, log.mode, log.message || "", dt(log.started_at), log.register_name || "", logTargetPeriodLabel(log)]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  };

  const exportLogs = (row: AutomationItem) => {
    const key = rowKey(row);
    const rows = filteredLogs(key);
    if (!rows.length) return;
    const csv = [
      ["started_at", "finished_at", "target_period", "mode", "status", "register_name", "message"].join(","),
      ...rows.map((log) =>
        [
          log.started_at || "",
          log.finished_at || "",
          logTargetPeriodLabel(log),
          log.mode || "",
          log.status || "",
          log.register_name || "",
          `"${String(log.message || "").replace(/"/g, '""')}"`,
        ].join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `automation-logs-${row.apartment_id}-${row.service_name}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const logsByMode = (key: string, mode: "readings" | "full" | "tariffs") =>
    filteredLogs(key).filter((log) => {
      if (mode === "readings") return log.mode === "readings";
      return log.mode === mode || (mode === "tariffs" && log.mode === "full");
    });

  return (
    <div className="subcard">
      <h4>Автоматизації</h4>
      <p className="helper">Розділили керування на окремі зони: підключення, планові цикли та шаблони постачальників.</p>
        {loading ? (
          <div className="skeleton-block" aria-hidden="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}

      <div className="tabs top-gap">
        <button className={`tab ${tab === "connections" ? "active" : ""}`} onClick={() => setTab("connections")}>
          Підключення до об'єктів
        </button>
        <button className={`tab ${tab === "cycles" ? "active" : ""}`} onClick={() => setTab("cycles")}>
          Планові цикли
        </button>
        <button className={`tab ${tab === "templates" ? "active" : ""}`} onClick={() => setTab("templates")}>
          Шаблони автоматизацій
        </button>
      </div>

      {tab === "connections" && (
        <div className="automation-board">
          <div className="automation-summary-grid">
            <div className="metric">
              <div className="label">Усього підключень</div>
              <div className="value">{filteredAutomationItems.length}</div>
            </div>
            <div className="metric">
              <div className="label">Активні</div>
              <div className="value">{filteredAutomationItems.filter((item) => item.auto_check_enabled).length}</div>
            </div>
            <div className="metric">
              <div className="label">Потребують уваги</div>
              <div className="value">{filteredAutomationItems.filter((item) => item.auto_check_status === "error" || missingDataMessage(item)).length}</div>
            </div>
          </div>
          <div className="row-actions">
            <button type="button" className="secondary" onClick={() => setShowConnectionFilters((value) => !value)}>
              {showConnectionFilters ? "Сховати фільтри" : "Показати фільтри"}
            </button>
          </div>
          {showConnectionFilters ? (
            <div className="automation-filter-panel">
              <input
                placeholder="Пошук за послугою, постачальником або текстом помилки"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
              />
              <label className="check">
                <input type="checkbox" checked={filterErrorsOnly} onChange={(e) => setFilterErrorsOnly(e.target.checked)} />
                Лише з помилками
              </label>
              <label className="check">
                <input type="checkbox" checked={filterSubmitWindowOnly} onChange={(e) => setFilterSubmitWindowOnly(e.target.checked)} />
                Відкрите submit-вікно
              </label>
              <label className="check">
                <input type="checkbox" checked={filterAwaitingReadingOnly} onChange={(e) => setFilterAwaitingReadingOnly(e.target.checked)} />
                Чекають показник
              </label>
            </div>
          ) : null}
          {grouped.map((group) => {
            const isRunBusy = !!groupBusy[`run-${group.apartment_id}`];
            const isPauseBusy = !!groupBusy[`pause-${group.apartment_id}`];
            return (
              <section className="automation-group" key={group.apartment_id}>
                <div className="automation-group-header">
                  <strong>{apartmentLabel({ apartment_address: group.apartment_address, apartment_code: "" })}</strong>
                  <div className="automation-group-actions">
                    <button onClick={() => runAllForApartment(group)} disabled={isRunBusy || isPauseBusy || !group.items.some((x) => !missingDataMessage(x))}>
                      {isRunBusy ? "Запуск..." : "Запустити всі"}
                    </button>
                    <button className="secondary" onClick={() => pauseAllForApartment(group)} disabled={isRunBusy || isPauseBusy}>
                      {isPauseBusy ? "Зупинка..." : "Зупинити всі"}
                    </button>
                  </div>
                </div>
                <div className="automation-grid">
                  {group.items.map((row) => {
                    const key = rowKey(row);
                    const status = statusView(row.auto_check_status);
                    const submit = submitState(row);
                    const submitTone = submitStateTone(row);
                    const blockedText = missingDataMessage(row);
                    const isRunning = !!running[key];
                    const isSaving = !!saving[key];
                    const isExpanded = !!expandedStatus[key];
                    return (
                      <article className={`automation-card ${blockedText ? "blocked" : ""}`} key={key}>
                        <div className="automation-card-top">
                          <div>
                            <div className="automation-service">{row.service_name}</div>
                            <div className="automation-provider">{row.provider_name || row.provider_company || "Постачальник не вказаний"}</div>
                          </div>
                          <span className={`status-pill ${row.auto_check_enabled ? "ok" : "draft"}`}>
                            {row.auto_check_enabled ? "Active" : "Paused"}
                          </span>
                        </div>

                        <div className="automation-meta-row">
                          <div><span className="field-label">Останній check</span><strong>{dt(row.auto_check_last_checked_at || null)}</strong></div>
                          <div><span className="field-label">Останнє оновлення</span><strong>{dt(row.auto_check_last_updated_at || null)}</strong></div>
                          <div><span className="field-label">Наступний запуск</span><strong>{dt(row.auto_check_next_at || null)}</strong></div>
                          <div className="automation-meta-details"><span className="field-label">Деталі</span><strong>{row.auto_check_message || "—"}</strong></div>
                        </div>

                        <div className="automation-meta-row">
                          <div>
                            <span className="field-label">Подача показників</span>
                            <strong>{submit.label}</strong>
                          </div>
                          <div>
                            <span className="field-label">Вікно подачі</span>
                            <strong>
                              {row.submit_enabled
                                ? `${String(row.submit_window_day_from || 28).padStart(2, "0")} - ${String(row.submit_window_day_to || 3).padStart(2, "0")}`
                                : "—"}
                            </strong>
                          </div>
                          <div>
                            <span className="field-label">Цільовий період</span>
                            <strong>{submitPeriodLabel(row)}</strong>
                          </div>
                          <div>
                            <span className="field-label">Наступний submit</span>
                            <strong>{dt(row.submit_next_at || null)}</strong>
                          </div>
                          <div className="automation-meta-details">
                            <span className="field-label">Стан submit</span>
                            <span className={`status-pill ${submitTone}`}>{submit.label}</span>
                          </div>
                        </div>

                        <div className="automation-warning">{row.submit_state_reason || "—"}</div>

                        <button className="automation-status-btn" onClick={() => toggleExpanded(row)}>{lastResultText(row)}</button>

                        {isExpanded && (
                          <div className="automation-status-panel">
                            <div><strong>Статус:</strong> {status.label}</div>
                            <div><strong>Останній check:</strong> {dt(row.auto_check_last_checked_at || null)}</div>
                            <div><strong>Останнє оновлення:</strong> {dt(row.auto_check_last_updated_at || null)}</div>
                            <div><strong>Наступний запуск:</strong> {dt(row.auto_check_next_at || null)}</div>
                            {row.auto_check_message ? <div><strong>Деталі:</strong> {row.auto_check_message}</div> : null}
                            <div className="top-gap"><strong>Останні 5 спроб:</strong></div>
                            <div className="automation-card-actions top-gap">
                              <input
                                placeholder="Пошук по логу"
                                value={logQueryByKey[key] || ""}
                                onChange={(e) => setLogQueryByKey((s) => ({ ...s, [key]: e.target.value }))}
                              />
                              <select
                                value={logRegisterFilterByKey[key] || ""}
                                onChange={(e) => setLogRegisterFilterByKey((s) => ({ ...s, [key]: e.target.value }))}
                              >
                                <option value="">Усі реєстри</option>
                                {Array.from(
                                  new Set((logsByKey[key] || []).map((log) => (log.register_name || "").trim()).filter(Boolean)),
                                )
                                  .sort((a, b) => a.localeCompare(b, "uk"))
                                  .map((register) => (
                                    <option key={register} value={register}>
                                      {register}
                                    </option>
                                  ))}
                              </select>
                              <button
                                className="secondary"
                                onClick={() => exportLogs(row)}
                                disabled={filteredLogs(key).length === 0}
                              >
                                Експорт CSV
                              </button>
                            </div>
                            {logsLoading[key] ? <div className="helper">Завантаження...</div> : (
                              <>
                                <div className="top-gap"><strong>Нарахування:</strong></div>
                                <ul>
                                  {logsByMode(key, "tariffs").slice(0, 5).map((log) => (
                                    <li key={log.id}>{dt(log.started_at)} [{log.mode}] {log.status}{log.target_month && log.target_year ? ` • ${logTargetPeriodLabel(log)}` : ""}{log.register_name ? ` • ${log.register_name}` : ""}{log.message ? `: ${log.message}` : ""}</li>
                                  ))}
                                  {logsByMode(key, "tariffs").length === 0 ? <li className="helper">Логів нарахувань немає</li> : null}
                                </ul>
                                <div className="top-gap"><strong>Подача показників:</strong></div>
                                <ul>
                                  {logsByMode(key, "readings").slice(0, 5).map((log) => (
                                    <li key={log.id}>{dt(log.started_at)} [{log.mode}] {log.status}{log.target_month && log.target_year ? ` • ${logTargetPeriodLabel(log)}` : ""}{log.register_name ? ` • ${log.register_name}` : ""}{log.message ? `: ${log.message}` : ""}</li>
                                  ))}
                                  {logsByMode(key, "readings").length === 0 ? <li className="helper">Логів подачі показників немає</li> : null}
                                </ul>
                              </>
                            )}
                          </div>
                        )}

                        {blockedText ? <div className="automation-warning">{blockedText}</div> : null}

                        <div className="automation-card-actions">
                          <button className="secondary" onClick={() => setEditingKey(key)}>Налаштувати</button>
                          <button onClick={() => runRow(row)} disabled={!!blockedText || isRunning}>{isRunning ? "Запуск..." : "Запустити"}</button>
                          <button onClick={() => saveRow(row)} disabled={isSaving}>{isSaving ? "Збереження..." : "Зберегти"}</button>
                          {row.automation_id ? <button className="danger" onClick={() => disconnectTemplateFromApartment(row)}>Відключити</button> : null}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {tab === "cycles" && (
        <div className="top-gap">
          <div className="row-actions">
            <button
              onClick={async () => {
                setCycleRunning(true);
                try {
                  await runAutomationCycle();
                } finally {
                  setCycleRunning(false);
                }
              }}
              disabled={cycleRunning}
            >
              {cycleRunning ? "Виконання..." : "Запустити плановий цикл"}
            </button>
            <button
              className="secondary"
              onClick={async () => {
                setCyclePreviewLoading(true);
                try {
                  const result = await previewAutomationCycle();
                  setCyclePreview(result.items || []);
                  setShowCyclePreview(true);
                } finally {
                  setCyclePreviewLoading(false);
                }
              }}
              disabled={cyclePreviewLoading}
            >
              {cyclePreviewLoading ? "Підготовка..." : "Dry-run циклу"}
            </button>
          </div>
          <div className="automation-filter-panel top-gap">
            <select value={cycleModeFilter} onChange={(e) => setCycleModeFilter(e.target.value)}>
              <option value="all">Усі цикли</option>
              <option value="scheduled">Планові</option>
              <option value="manual">Ручні</option>
              <option value="dry-run">Dry-run</option>
            </select>
            <input placeholder="Пошук по журналу циклів" value={cycleQuery} onChange={(e) => setCycleQuery(e.target.value)} />
          </div>
          <div className="table-wrap top-gap">
            <table>
              <thead>
                <tr>
                  <th>Останні цикли</th>
                  <th>Режим</th>
                  <th>Старт</th>
                  <th>Фініш</th>
                  <th>Фази</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredCycleRuns.map((row) => (
                  <tr key={`${row.id || row.started_at || "cycle"}-${row.trigger_mode || "scheduled"}`}>
                    <td>{row.message || "Плановий цикл виконано"}</td>
                    <td>{cycleModeLabel(row.trigger_mode)}</td>
                    <td>{dt(row.started_at || null)}</td>
                    <td>{dt(row.finished_at || null)}</td>
                    <td>
                      {(row.phases || []).length ? (
                        <div className="stack">
                          {(row.phases || []).map((phase) => (
                            <div key={`${row.id || "cycle"}-${phase.id || phase.phase}`} className="helper">
                              {cyclePhaseLabel(phase.phase)}: run={phase.processed_count}, skip={phase.skipped_count}
                              {phase.submitted_readings ? `, sent=${phase.submitted_readings}` : ""}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <>accrual={row.processed_accrual_automations}, submit={row.processed_submit_automations}, sent={row.submitted_readings}</>
                      )}
                    </td>
                    <td>{typeof row.id === "number" ? <button className="secondary" onClick={() => void openCycleRunDetail(row.id!)}>Деталі</button> : null}</td>
                  </tr>
                ))}
                {filteredCycleRuns.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <span className="helper">Журнал циклів не містить записів за поточним фільтром.</span>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "templates" && (
        <div className="top-gap">
          <div className="forms-grid compact-grid">
            <input placeholder="Назва шаблону" value={templateForm.name} onChange={(e) => setTemplateForm((s) => ({ ...s, name: e.target.value }))} />
            <select value={templateForm.provider_id} onChange={(e) => setTemplateForm((s) => ({ ...s, provider_id: e.target.value }))}>
              <option value="">Постачальник (опційно)</option>
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name_full}
                </option>
              ))}
            </select>
            <select value={templateForm.utility_type} onChange={(e) => setTemplateForm((s) => ({ ...s, utility_type: e.target.value }))}>
              <option value="">Тип послуги (опційно)</option>
              <option value="electricity">Електроенергія</option><option value="water">Вода</option><option value="gas">Газ</option><option value="heating">Опалення</option><option value="sewage">Водовідведення</option><option value="internet">Інтернет</option><option value="other">Інше</option>
            </select>
            <input placeholder="URL кабінету" value={templateForm.cabinet_url} onChange={(e) => setTemplateForm((s) => ({ ...s, cabinet_url: e.target.value }))} />
            <input placeholder="Опис" value={templateForm.description} onChange={(e) => setTemplateForm((s) => ({ ...s, description: e.target.value }))} />
            <label className="check"><input type="checkbox" checked={templateForm.supports_accrual} onChange={(e) => setTemplateForm((s) => ({ ...s, supports_accrual: e.target.checked }))} />Підтримує нарахування</label>
            <label className="check"><input type="checkbox" checked={templateForm.supports_meter_submit} onChange={(e) => setTemplateForm((s) => ({ ...s, supports_meter_submit: e.target.checked }))} />Підтримує подачу показників</label>
            <label className="check"><input type="checkbox" checked={templateForm.is_active} onChange={(e) => setTemplateForm((s) => ({ ...s, is_active: e.target.checked }))} />Активний шаблон</label>
          </div>
          <div className="automation-window-preview top-gap">
            <strong>Примітка:</strong> технічний код шаблону генерується автоматично і в інтерфейсі не показується.
          </div>
          <div className="row-actions top-gap">
            <button onClick={submitTemplate} disabled={templateSaving || !templateForm.name.trim()}>{templateSaving ? "Збереження..." : editingTemplateId ? "Оновити шаблон" : "Створити шаблон"}</button>
            {editingTemplateId ? <button className="secondary" onClick={resetTemplateForm}>Скасувати редагування</button> : null}
          </div>

          <div className="table-wrap top-gap">
            <table>
              <thead><tr><th>Назва</th><th>Постачальник</th><th>Що робить</th><th>Активний</th><th></th></tr></thead>
              <tbody>
                {templates.map((tpl) => (
                  <tr key={tpl.id}>
                    <td>{tpl.name}</td><td>{tpl.provider_name || "—"}</td><td>{tpl.description || "—"}</td><td>{tpl.is_active ? "Так" : "Ні"}</td>
                    <td>
                      <button className="secondary" onClick={() => editTemplate(tpl)}>Редагувати</button>{" "}
                      {selectedApartmentId ? <button onClick={() => openConnectModal(tpl)}>Підключити</button> : null}{" "}
                      <button className="danger" onClick={() => deleteTemplate(tpl.id)}>Видалити</button>
                    </td>
                  </tr>
                ))}
                {templates.length === 0 && <tr><td colSpan={5}><span className="helper">Шаблони автоматизацій ще не створені.</span></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {grouped.length === 0 && tab === "connections" && <span className="helper">Налаштування автоматизацій ще не створені.</span>}

      {editingRow && (
        <Modal title={`Автоматизація: ${editingRow.service_name}`} onClose={() => setEditingKey(null)}>
          <div className="automation-modal-grid">
            <label className="check"><input type="checkbox" checked={ensureDraft(editingRow).auto_check_enabled} onChange={(e) => updateDraft(editingRow, { auto_check_enabled: e.target.checked })} />Увімкнути автоперевірку</label>

            <div className="automation-schedule-grid">
              <div className="field"><label className="field-label">Час автоперевірки</label><input type="time" value={ensureDraft(editingRow).auto_check_time} onChange={(e) => updateDraft(editingRow, { auto_check_time: e.target.value })} /></div>
              <div className="field"><label className="field-label">Вікно перевірки: день від</label><input type="number" min="1" max="31" value={ensureDraft(editingRow).auto_check_window_day_from} onChange={(e) => updateDraft(editingRow, { auto_check_window_day_from: e.target.value })} /></div>
              <div className="field"><label className="field-label">Вікно перевірки: день до</label><input type="number" min="1" max="31" value={ensureDraft(editingRow).auto_check_window_day_to} onChange={(e) => updateDraft(editingRow, { auto_check_window_day_to: e.target.value })} /></div>
            </div>

            <div className="automation-schedule-grid">
              <label className="check"><input type="checkbox" checked={ensureDraft(editingRow).submit_enabled} onChange={(e) => updateDraft(editingRow, { submit_enabled: e.target.checked })} />Увімкнути подачу показників</label>
              <div className="field"><label className="field-label">Час подачі</label><input type="time" value={ensureDraft(editingRow).submit_time} onChange={(e) => updateDraft(editingRow, { submit_time: e.target.value })} /></div>
              <div className="field"><label className="field-label">Вікно подачі: день від</label><input type="number" min="1" max="31" value={ensureDraft(editingRow).submit_window_day_from} onChange={(e) => updateDraft(editingRow, { submit_window_day_from: e.target.value })} /></div>
              <div className="field"><label className="field-label">Вікно подачі: день до</label><input type="number" min="1" max="31" value={ensureDraft(editingRow).submit_window_day_to} onChange={(e) => updateDraft(editingRow, { submit_window_day_to: e.target.value })} /></div>
            </div>

            <div className="automation-source-box">
              <div className="field-label">Джерело даних</div>
              <div>Логін: <strong>{maskLogin(editingRow.cabinet_login)}</strong></div>
              <div>URL: <strong>{editingRow.cabinet_url || "—"}</strong></div>
              <div>Особовий рахунок: <strong>{editingRow.personal_account || "—"}</strong></div>
              <div className="helper">Параметри послуги та її нарахувань редагуються у вкладці Послуги об'єкта.</div>
              <button className="secondary" onClick={() => { setEditingKey(null); onOpenTariffs?.(); }}>Відкрити послуги об'єкта</button>
            </div>

            <div className="row-actions">
              <button onClick={async () => { await saveRow(editingRow); setEditingKey(null); }}>Зберегти</button>
              <button onClick={async () => { await runRow(editingRow); }} disabled={!!missingDataMessage(editingRow) || !!running[rowKey(editingRow)]}>{running[rowKey(editingRow)] ? "Запуск..." : "Запустити зараз"}</button>
            </div>
          </div>
        </Modal>
      )}

      {connectTemplate && selectedApartmentId ? (
        <Modal title={`Підключити шаблон: ${connectTemplate.name}`} onClose={() => setConnectTemplate(null)}>
          <div className="automation-modal-grid">
            <div className="field">
              <label className="field-label">Особовий рахунок</label>
              <div className="helper">Номер рахунку або особового запису в кабінеті постачальника.</div>
              <input
                value={connectionForm.personal_account}
                onChange={(e) => setConnectionForm((s) => ({ ...s, personal_account: e.target.value }))}
              />
            </div>
            <div className="field">
              <label className="field-label">URL кабінету</label>
              <div className="helper">Повна адреса сторінки входу або особистого кабінету постачальника.</div>
              <input
                value={connectionForm.cabinet_url}
                onChange={(e) => setConnectionForm((s) => ({ ...s, cabinet_url: e.target.value }))}
              />
            </div>
            <div className="field">
              <label className="field-label">Логін</label>
              <div className="helper">Email, номер договору або інший логін для входу у кабінет.</div>
              <input
                value={connectionForm.cabinet_login}
                onChange={(e) => setConnectionForm((s) => ({ ...s, cabinet_login: e.target.value }))}
              />
            </div>
            <div className="field">
              <label className="field-label">Пароль</label>
              <div className="helper">Пароль зберігається для автоматичного входу в кабінет постачальника.</div>
              <div className="row-actions">
                <input
                  type={showPassword ? "text" : "password"}
                  value={connectionForm.cabinet_password}
                  onChange={(e) => setConnectionForm((s) => ({ ...s, cabinet_password: e.target.value }))}
                />
                <button type="button" className="secondary" onClick={() => setShowPassword((v) => !v)}>
                  {showPassword ? "Сховати" : "Показати"}
                </button>
              </div>
            </div>
            <div className="automation-schedule-grid">
              <label className="check">
                <input
                  type="checkbox"
                  checked={connectionForm.accrual_enabled}
                  onChange={(e) => setConnectionForm((s) => ({ ...s, accrual_enabled: e.target.checked }))}
                />
                Увімкнути нарахування
              </label>
              <div className="helper">Система перевірятиме кабінет і підтягуватиме нарахування лише у вказане вікно днів.</div>
              <input
                type="time"
                value={connectionForm.accrual_time}
                onChange={(e) => setConnectionForm((s) => ({ ...s, accrual_time: e.target.value }))}
              />
              <input
                type="number"
                min="1"
                max="31"
                value={connectionForm.accrual_window_day_from}
                onChange={(e) => setConnectionForm((s) => ({ ...s, accrual_window_day_from: e.target.value }))}
              />
              <input
                type="number"
                min="1"
                max="31"
                value={connectionForm.accrual_window_day_to}
                onChange={(e) => setConnectionForm((s) => ({ ...s, accrual_window_day_to: e.target.value }))}
              />
            </div>
            <div className="automation-schedule-grid">
              <label className="check">
                <input
                  type="checkbox"
                  checked={connectionForm.submit_enabled}
                  onChange={(e) => setConnectionForm((s) => ({ ...s, submit_enabled: e.target.checked }))}
                />
                Увімкнути подачу показників
              </label>
              <div className="helper">Показники відправлятимуться у вказане вікно днів, якщо для місяця вже є збережене значення.</div>
              <input
                type="time"
                value={connectionForm.submit_time}
                onChange={(e) => setConnectionForm((s) => ({ ...s, submit_time: e.target.value }))}
              />
              <input
                type="number"
                min="1"
                max="31"
                value={connectionForm.submit_window_day_from}
                onChange={(e) => setConnectionForm((s) => ({ ...s, submit_window_day_from: e.target.value }))}
              />
              <input
                type="number"
                min="1"
                max="31"
                value={connectionForm.submit_window_day_to}
                onChange={(e) => setConnectionForm((s) => ({ ...s, submit_window_day_to: e.target.value }))}
              />
            </div>
            <div className="row-actions">
              <button
                disabled={
                  connectionSaving ||
                  !connectionForm.cabinet_url.trim() ||
                  !connectionForm.cabinet_login.trim() ||
                  !connectionForm.cabinet_password.trim()
                }
                onClick={async () => {
                  setConnectionSaving(true);
                  try {
                    await connectTemplateToApartment(connectTemplate.id, selectedApartmentId, connectionForm);
                    setConnectTemplate(null);
                  } finally {
                    setConnectionSaving(false);
                  }
                }}
              >
                {connectionSaving ? "Підключення..." : "Підключити"}
              </button>
              <button className="secondary" onClick={() => setConnectTemplate(null)}>
                Скасувати
              </button>
            </div>
          </div>
        </Modal>
      ) : null}

      {showCyclePreview ? (
        <Modal title="Dry-run планового циклу" onClose={() => setShowCyclePreview(false)}>
          <div className="stack gap-md">
            <div className="row-actions">
              <select value={previewActionFilter} onChange={(e) => setPreviewActionFilter(e.target.value)}>
                <option value="all">Усі дії</option>
                <option value="run">Лише run</option>
                <option value="skip">Лише skip</option>
              </select>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Фаза</th>
                    <th>Дія</th>
                    <th>Код</th>
                    <th>Причина</th>
                    <th>К-сть</th>
                  </tr>
                </thead>
                <tbody>
                  {cycleReasonSummary.map((row, index) => (
                    <tr key={`${row.phase}-${row.action}-${index}`}>
                      <td>{row.phase}</td>
                      <td>{row.action}</td>
                      <td>{previewReasonCodeLabel(row.reason_code)}</td>
                      <td>{row.reason}</td>
                      <td>{row.count}</td>
                    </tr>
                  ))}
                  {cycleReasonSummary.length === 0 ? (
                    <tr>
                      <td colSpan={5}>
                        <span className="helper">Немає причин для показу за поточним фільтром.</span>
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {filteredGroupedCyclePreview.map((apartmentGroup) => (
              <section key={`${apartmentGroup.apartment_id}:${apartmentGroup.apartment_address}`} className="card-section">
                <div className="section-head">
                  <div>
                    <strong>{apartmentGroup.apartment_address}</strong>
                  </div>
                  <span className="helper">Фаз: {apartmentGroup.phases.size}</span>
                </div>
                {[...apartmentGroup.phases.entries()].map(([phase, items]) => (
                  <div key={phase} className="top-gap">
                    <div className="helper">{phase}</div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Послуга</th>
                            <th>Дія</th>
                            <th>Код</th>
                            <th>Причина</th>
                          </tr>
                        </thead>
                        <tbody>
                          {items.map((item, index) => (
                            <tr key={`${item.automation_id || "legacy"}-${phase}-${index}`}>
                              <td>{item.service_name}</td>
                              <td>{item.action}</td>
                              <td>{previewReasonCodeLabel(item.reason_code)}</td>
                              <td>{item.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </section>
            ))}
            {filteredGroupedCyclePreview.length === 0 ? <span className="helper">Немає даних для preview.</span> : null}
          </div>
        </Modal>
      ) : null}

      {selectedCycleRunDetail ? (
        <Modal title={`Цикл #${selectedCycleRunDetail.id} • ${cycleModeLabel(selectedCycleRunDetail.trigger_mode)}`} onClose={() => setSelectedCycleRunDetail(null)}>
          <div className="row-actions">
            <select
              value={cycleDetailApartmentFilter}
              onChange={async (e) => {
                const nextValue = e.target.value;
                setCycleDetailApartmentFilter(nextValue);
                setCycleDetailLoading(true);
                try {
                  const detail = await fetchAutomationCycleRunDetail(selectedCycleRunDetail.id, nextValue ? Number(nextValue) : null);
                  setSelectedCycleRunDetail(detail);
                } finally {
                  setCycleDetailLoading(false);
                }
              }}
            >
              <option value="">Усі об'єкти</option>
              {cycleApartmentOptions.map((item) => (
                <option key={item.apartment_id} value={item.apartment_id}>
                  {item.label}
                </option>
              ))}
            </select>
            {cycleDetailLoading ? <span className="helper">Завантаження...</span> : null}
          </div>
          <div className="table-wrap top-gap">
            <table>
              <thead>
                <tr>
                  <th>Фаза</th>
                  <th>Статус</th>
                  <th>Run</th>
                  <th>Skip</th>
                  <th>Sent</th>
                  <th>Тривалість</th>
                  <th>Деталі</th>
                </tr>
              </thead>
              <tbody>
                {selectedCycleRunDetail.phases.map((phase) => (
                  <tr key={`${selectedCycleRunDetail.id}-${phase.id || phase.phase}`}>
                    <td>{cyclePhaseLabel(phase.phase)}</td>
                    <td>{phase.status}</td>
                    <td>{phase.processed_count}</td>
                    <td>{phase.skipped_count}</td>
                    <td>{phase.submitted_readings}</td>
                    <td>{durationLabel(phase.duration_ms)}</td>
                    <td>{phase.message || "—"}</td>
                  </tr>
                ))}
                {selectedCycleRunDetail.phases.length === 0 ? (
                  <tr>
                    <td colSpan={7}>
                      <span className="helper">Phase-log відсутній.</span>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="table-wrap top-gap">
            <table>
              <thead>
                <tr>
                  <th>Коли</th>
                  <th>Об'єкт</th>
                  <th>Фаза</th>
                  <th>Послуга</th>
                  <th>Статус</th>
                  <th>Період</th>
                  <th>Реєстр</th>
                  <th>Деталі</th>
                </tr>
              </thead>
              <tbody>
                {selectedCycleRunDetail.logs.map((log) => (
                  <tr key={log.id}>
                    <td>{dt(log.started_at)}</td>
                    <td>{log.apartment_address}</td>
                    <td>{cyclePhaseLabel(log.phase)}</td>
                    <td>{log.service_name}</td>
                    <td>{log.status}</td>
                    <td>{log.target_month && log.target_year ? `${String(log.target_month).padStart(2, "0")}.${log.target_year}` : "—"}</td>
                    <td>{log.register_name || "—"}</td>
                    <td>{log.message || "—"}</td>
                  </tr>
                ))}
                {selectedCycleRunDetail.logs.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <span className="helper">Для цього циклу немає automation-log за поточним фільтром об'єкта.</span>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
