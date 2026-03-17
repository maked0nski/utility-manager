import { useEffect, useMemo, useState } from "react";
import { In, Se, Ta } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import type {
  ApartmentServiceConnectionItem,
  ChargeLineKind,
  ConnectionChargeLineItem,
  MeterItem,
  ProviderItem,
  QuantitySource,
  ServiceCatalogItem,
  UtilityType,
} from "@/shared/api/types";

type EditableChargeLine = {
  id?: number;
  line_kind: ChargeLineKind;
  label: string;
  meter_id: string;
  meter_register: string;
  derived_from_line_id: string;
  initial_reading: string;
  unit_name: string;
  price_per_unit: string;
  quantity_source: QuantitySource;
  quantity_multiplier: string;
  effective_from: string;
  effective_to: string;
  is_active: boolean;
};

type ConnectionEditorForm = {
  service_catalog_id: string;
  provider_id: string;
  personal_account: string;
  started_at: string;
  ended_at: string;
  status: "active" | "inactive";
  note: string;
  meter_mode: "single" | "day_night" | "tri_zone";
  charge_lines: EditableChargeLine[];
};

type ChargeLinePayload = {
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
};

const UTILITY_TYPE_LABELS: Record<UtilityType, string> = {
  electricity: "Електроенергія",
  water: "Вода",
  gas: "Газ",
  heating: "Опалення",
  sewage: "Водовідведення",
  internet: "Інтернет",
  other: "Інше",
};

const CALCULATION_KIND_LABELS = {
  fixed: "Фіксована сума",
  metered: "За лічильником",
  derived: "Похідна від іншої послуги",
} as const;

const QUANTITY_SOURCE_LABELS: Record<QuantitySource, string> = {
  fixed_1: "Фіксована кількість",
  registered_residents: "К-сть прописаних",
  area_m2: "Площа, м²",
  derived_consumption: "Обсяг з іншої послуги",
};

const CALCULATION_KIND_DESCRIPTIONS = {
  fixed: "Щомісячна або розрахункова фіксована послуга без показників лічильника.",
  metered: "Послуга рахується за показниками лічильника і стартовим значенням для кожного рядка.",
  derived: "Сума рахується від обсягу іншої послуги, наприклад водовідведення від водопостачання.",
} as const;

const METER_REGISTER_LABELS: Record<string, string> = {
  total: "Загальний реєстр",
  day: "Денний реєстр",
  night: "Нічний реєстр",
  peak: "Піковий реєстр",
  semi_peak: "Напівпіковий реєстр",
  off_peak: "Нічний реєстр",
};

function lineKindLabel(lineKind: ChargeLineKind) {
  if (lineKind === "meter_register") return "Лічильник";
  if (lineKind === "derived") return "Похідна";
  return "Фіксована";
}

function lineToneClass(line: Pick<EditableChargeLine | ConnectionChargeLineItem, "line_kind" | "meter_register">) {
  if (line.line_kind !== "meter_register") return line.line_kind === "derived" ? "tone-derived" : "tone-fixed";
  if (line.meter_register === "day") return "day";
  if (line.meter_register === "night" || line.meter_register === "off_peak") return "night";
  if (line.meter_register === "peak") return "peak";
  if (line.meter_register === "semi_peak") return "semi";
  return "tone-meter";
}

function makeLine(overrides: Partial<EditableChargeLine> = {}): EditableChargeLine {
  return {
    line_kind: "fixed",
    label: "Основний тариф",
    meter_id: "",
    meter_register: "total",
    derived_from_line_id: "",
    initial_reading: "",
    unit_name: "month",
    price_per_unit: "",
    quantity_source: "fixed_1",
    quantity_multiplier: "1",
    effective_from: new Date().toISOString().slice(0, 10),
    effective_to: "",
    is_active: true,
    ...overrides,
  };
}

function buildDefaultForm(): ConnectionEditorForm {
  return {
    service_catalog_id: "",
    provider_id: "",
    personal_account: "",
    started_at: new Date().toISOString().slice(0, 10),
    ended_at: "",
    status: "active",
    note: "",
    meter_mode: "single",
    charge_lines: [makeLine()],
  };
}

function inferMeterMode(lines: ConnectionChargeLineItem[]) {
  if (lines.some((line) => line.meter_register === "peak" || line.meter_register === "semi_peak")) return "tri_zone";
  if (lines.some((line) => line.meter_register === "day" || line.meter_register === "night")) return "day_night";
  return "single";
}

function connectionStatusLabel(status: string) {
  return status === "active" ? "Активна" : "Неактивна";
}

function expectedElectricRegisters(mode: ConnectionEditorForm["meter_mode"]): string[] {
  if (mode === "day_night") return ["day", "night"];
  if (mode === "tri_zone") return ["peak", "semi_peak", "off_peak"];
  return ["total"];
}

function normalizeLineByService(
  line: EditableChargeLine,
  service: ServiceCatalogItem | null,
  mode: ConnectionEditorForm["meter_mode"],
): EditableChargeLine {
  if (!service) return line;
  if (service.calculation_kind === "derived") {
    return {
      ...line,
      line_kind: "derived",
      meter_id: "",
      meter_register: "total",
      quantity_source: "derived_consumption",
      quantity_multiplier: line.quantity_multiplier || "1",
      initial_reading: "",
    };
  }
  if (service.calculation_kind === "metered") {
    const expected = expectedElectricRegisters(mode);
    return {
      ...line,
      line_kind: "meter_register",
      meter_register: expected.includes(line.meter_register) ? line.meter_register : expected[0],
      derived_from_line_id: "",
      quantity_source: "fixed_1",
      quantity_multiplier: "1",
    };
  }
  return {
      ...line,
      line_kind: "fixed",
      meter_id: "",
      meter_register: "total",
      derived_from_line_id: "",
      initial_reading: "",
      quantity_source:
        line.quantity_source === "registered_residents" || line.quantity_source === "area_m2"
          ? line.quantity_source
        : "fixed_1",
  };
}

export function ObjectServicesTab({
  services,
  connections,
  providers,
  meters,
  loading,
  onCreateConnection,
  onUpdateConnection,
  onDeleteConnection,
}: {
  services: ServiceCatalogItem[];
  connections: ApartmentServiceConnectionItem[];
  providers: ProviderItem[];
  meters: MeterItem[];
  loading?: boolean;
  onCreateConnection: (payload: {
    service_catalog_id: number;
    provider_id: number | null;
    personal_account: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    note: string | null;
    charge_lines: ChargeLinePayload[];
  }) => Promise<void>;
  onUpdateConnection: (
    connectionId: number,
    payload: {
      provider_id: number | null;
      personal_account: string | null;
      started_at: string;
      ended_at: string | null;
      status: string;
      note: string | null;
      charge_lines: ChargeLinePayload[];
    },
  ) => Promise<void>;
  onDeleteConnection: (connectionId: number) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [editingConnectionId, setEditingConnectionId] = useState<number | null>(null);
  const [expandedConnectionId, setExpandedConnectionId] = useState<number | null>(null);
  const [form, setForm] = useState<ConnectionEditorForm>(buildDefaultForm());

  const serviceMap = useMemo(() => new Map(services.map((item) => [item.id, item])), [services]);
  const providerMap = useMemo(() => new Map(providers.map((item) => [item.id, item])), [providers]);
  const meterMap = useMemo(() => new Map(meters.map((item) => [item.id, item])), [meters]);

  const selectedService = services.find((item) => String(item.id) === form.service_catalog_id) || null;
  const requiredDerivedService = selectedService?.derived_from_service_id
    ? serviceMap.get(selectedService.derived_from_service_id) || null
    : null;
  const derivedSourceOptions = useMemo(() => {
    return connections.flatMap((connection) => {
      if (editingConnectionId && connection.id === editingConnectionId) return [];
      if (
        selectedService?.derived_from_service_id &&
        connection.service_catalog_id !== selectedService.derived_from_service_id
      ) {
        return [];
      }
      return connection.charge_lines
        .filter((line) => line.line_kind === "meter_register")
        .map((line) => ({
          id: line.id,
          label: `${serviceMap.get(connection.service_catalog_id)?.name || "Послуга"} -> ${line.label}`,
        }));
    });
  }, [connections, editingConnectionId, selectedService, serviceMap]);
  const selectedProvider = providers.find((item) => String(item.id) === form.provider_id) || null;
  const recommendedProviders = useMemo(() => {
    if (!selectedService?.default_provider_utility_type) return providers;
    const matched = providers.filter((item) => item.utility_type === selectedService.default_provider_utility_type);
    const fallback = providers.filter((item) => item.utility_type !== selectedService.default_provider_utility_type);
    return [...matched, ...fallback];
  }, [providers, selectedService]);
  const activeConnections = connections.filter((item) => item.status === "active");

  useEffect(() => {
    if (expandedConnectionId && !connections.some((item) => item.id === expandedConnectionId)) {
      setExpandedConnectionId(null);
    }
  }, [connections, expandedConnectionId]);

  const compatibleMeters = useMemo(() => {
    if (!selectedService?.requires_meter || !selectedService.allowed_meter_utility_type) return [];
    return meters.filter((meter) => meter.utility_type === selectedService.allowed_meter_utility_type && meter.is_active !== false);
  }, [meters, selectedService]);

  useEffect(() => {
    if (!selectedService || selectedService.calculation_kind !== "derived") return;
    setForm((current) => {
      let changed = false;
      const nextLines = current.charge_lines.map((line) => {
        if (line.line_kind !== "derived") return line;
        if (line.derived_from_line_id) return line;
        const firstSourceId = derivedSourceOptions[0]?.id ? String(derivedSourceOptions[0].id) : "";
        if (!firstSourceId) return line;
        changed = true;
        return { ...line, derived_from_line_id: firstSourceId };
      });
      if (!changed) return current;
      return { ...current, charge_lines: nextLines };
    });
  }, [derivedSourceOptions, selectedService]);

  const applyServiceTemplate = (service: ServiceCatalogItem | null, startedAt: string, mode: ConnectionEditorForm["meter_mode"]) => {
    if (!service) return setForm((current) => ({ ...current, charge_lines: [makeLine({ effective_from: startedAt })] }));
    if (service.calculation_kind === "fixed") {
      return setForm((current) => ({ ...current, charge_lines: [makeLine({ line_kind: "fixed", label: "Основний тариф", unit_name: service.unit_name, effective_from: startedAt })] }));
    }
    if (service.calculation_kind === "derived") {
      return setForm((current) => ({ ...current, charge_lines: [makeLine({ line_kind: "derived", label: "Розрахунок від іншої послуги", unit_name: service.unit_name, effective_from: startedAt, quantity_source: "derived_consumption" })] }));
    }
    if (service.allowed_meter_utility_type === "electricity" && mode !== "single") {
      const zoneLines =
        mode === "day_night"
          ? [
              makeLine({ line_kind: "meter_register", label: "Денний тариф", meter_register: "day", unit_name: service.unit_name, effective_from: startedAt }),
              makeLine({ line_kind: "meter_register", label: "Нічний тариф", meter_register: "night", unit_name: service.unit_name, effective_from: startedAt }),
            ]
          : [
              makeLine({ line_kind: "meter_register", label: "Піковий тариф", meter_register: "peak", unit_name: service.unit_name, effective_from: startedAt }),
              makeLine({ line_kind: "meter_register", label: "Напівпіковий тариф", meter_register: "semi_peak", unit_name: service.unit_name, effective_from: startedAt }),
              makeLine({ line_kind: "meter_register", label: "Нічний тариф", meter_register: "off_peak", unit_name: service.unit_name, effective_from: startedAt }),
            ];
      return setForm((current) => ({ ...current, charge_lines: zoneLines }));
    }
    return setForm((current) => ({ ...current, charge_lines: [makeLine({ line_kind: "meter_register", label: "Основний тариф", meter_register: "total", unit_name: service.unit_name, effective_from: startedAt })] }));
  };

  const closeModal = () => {
    setOpen(false);
    setEditingConnectionId(null);
    setForm(buildDefaultForm());
  };

  const openCreate = () => {
    setEditingConnectionId(null);
    setForm(buildDefaultForm());
    setOpen(true);
  };

  const openEdit = (connection: ApartmentServiceConnectionItem) => {
    setEditingConnectionId(connection.id);
    setForm({
      service_catalog_id: String(connection.service_catalog_id),
      provider_id: connection.provider_id ? String(connection.provider_id) : "",
      personal_account: connection.personal_account || "",
      started_at: connection.started_at,
      ended_at: connection.ended_at || "",
      status: connection.status === "inactive" ? "inactive" : "active",
      note: connection.note || "",
      meter_mode: inferMeterMode(connection.charge_lines),
      charge_lines: connection.charge_lines.length
        ? connection.charge_lines.map((line) => ({
            id: line.id,
            line_kind: line.line_kind,
            label: line.label,
            meter_id: line.meter_id ? String(line.meter_id) : "",
            meter_register: line.meter_register,
            derived_from_line_id: line.derived_from_line_id ? String(line.derived_from_line_id) : "",
            initial_reading:
              line.initial_reading !== null && line.initial_reading !== undefined ? String(line.initial_reading) : "",
            unit_name: line.unit_name,
            price_per_unit: String(line.price_per_unit ?? ""),
            quantity_source: line.quantity_source,
            quantity_multiplier: String(line.quantity_multiplier ?? "1"),
            effective_from: line.effective_from,
            effective_to: line.effective_to || "",
            is_active: line.is_active,
          }))
        : [makeLine({ effective_from: connection.started_at })],
    });
    setOpen(true);
  };

  const updateLine = (index: number, patch: Partial<EditableChargeLine>) => {
    setForm((current) => ({
      ...current,
      charge_lines: current.charge_lines.map((line, lineIndex) => (lineIndex === index ? { ...line, ...patch } : line)),
    }));
  };

  const canEditLineLabels =
    !!selectedService && !(selectedService.calculation_kind === "metered" && selectedService.allowed_meter_utility_type === "electricity");

  const validationMessage = (() => {
    if (!services.length) return "Спочатку створіть хоча б одну послугу в Налаштуваннях.";
    if (!form.service_catalog_id) return "Оберіть послугу.";
    if (form.charge_lines.some((line) => !line.price_per_unit.trim())) return "Заповніть ціну для кожного рядка.";
    if (
      selectedService?.requires_meter &&
      form.charge_lines.some((line) => line.line_kind === "meter_register" && !line.meter_id)
    ) {
      return "Для рядків за лічильником потрібно обрати лічильник.";
    }
    if (
      selectedService?.calculation_kind === "metered" &&
      form.charge_lines.some((line) => line.line_kind === "meter_register" && !line.initial_reading.trim())
    ) {
      return "Для рядків за лічильником потрібно вказати початковий показник.";
    }
    if (selectedService?.calculation_kind === "derived") {
      if (!derivedSourceOptions.length) {
        if (requiredDerivedService) {
          return `Немає доступного джерела обсягу. Спочатку підключіть послугу "${requiredDerivedService.name}" для цього об'єкта.`;
        }
        return "Немає доступного джерела обсягу. Спочатку додайте послугу-донор з лічильником.";
      }
      if (form.charge_lines.some((line) => !line.derived_from_line_id)) {
        return "Для похідної послуги потрібно вибрати джерело обсягу.";
      }
    }
    if (selectedService?.calculation_kind === "metered" && selectedService.allowed_meter_utility_type === "electricity") {
      const expected = expectedElectricRegisters(form.meter_mode);
      const actual = form.charge_lines.map((line) => line.meter_register);
      if (expected.length !== actual.length || expected.some((registerName, index) => actual[index] !== registerName)) {
        return "Для обраного режиму електролічильника структура рядків буде створена автоматично.";
      }
    }
    return "";
  })();

  const save = async () => {
    if (!form.service_catalog_id || form.charge_lines.some((line) => !line.price_per_unit.trim())) return;
    const chargeLines = form.charge_lines.map((rawLine) => {
      const line = normalizeLineByService(rawLine, selectedService, form.meter_mode);
      return {
      id: line.id,
      line_kind: line.line_kind,
      label: line.label.trim(),
      meter_id: line.meter_id ? Number(line.meter_id) : null,
      meter_register: line.meter_register,
      derived_from_line_id: line.derived_from_line_id ? Number(line.derived_from_line_id) : null,
      initial_reading: line.line_kind === "meter_register" && line.initial_reading.trim() ? line.initial_reading.trim() : null,
      unit_name: line.unit_name,
      price_per_unit: line.price_per_unit,
      quantity_source: line.quantity_source,
      quantity_multiplier: line.quantity_multiplier || "1",
      effective_from: line.effective_from,
      effective_to: line.effective_to || null,
      is_active: line.is_active,
      };
    });
    if (editingConnectionId) {
      await onUpdateConnection(editingConnectionId, {
        provider_id: form.provider_id ? Number(form.provider_id) : null,
        personal_account: form.personal_account.trim() || null,
        started_at: form.started_at,
        ended_at: form.ended_at || null,
        status: form.status,
        note: form.note.trim() || null,
        charge_lines: chargeLines,
      });
    } else {
      await onCreateConnection({
        service_catalog_id: Number(form.service_catalog_id),
        provider_id: form.provider_id ? Number(form.provider_id) : null,
        personal_account: form.personal_account.trim() || null,
        started_at: form.started_at,
        ended_at: form.ended_at || null,
        status: form.status,
        note: form.note.trim() || null,
        charge_lines: chargeLines,
      });
    }
    closeModal();
  };

  return (
    <div className="property-sections">
      <div className="subcard">
        <div className="header-tools">
          <div>
            <h4>Послуги об&apos;єкта</h4>
            <p className="helper">Нова модель: одна послуга об&apos;єкта + один або кілька рядків розрахунку всередині.</p>
          </div>
          <div className="row-actions">
            <button onClick={openCreate} disabled={!services.length}>Підключити послугу</button>
          </div>
        </div>
        <div className="summary-grid dashboard-kpi-strip">
          <div className="metric">
            <div className="label">Усього послуг у довіднику</div>
            <div className="value">{services.length}</div>
          </div>
          <div className="metric">
            <div className="label">Підключено до об&apos;єкта</div>
            <div className="value">{connections.length}</div>
          </div>
          <div className="metric">
            <div className="label">Активні зараз</div>
            <div className="value">{activeConnections.length}</div>
          </div>
        </div>
        <div className="property-steps">
          <div><span className="helper">Крок 1</span><strong>Оберіть послугу</strong><span className="helper">Форма сама підлаштується під тип розрахунку.</span></div>
          <div><span className="helper">Крок 2</span><strong>Прив&apos;яжіть постачальника</strong><span className="helper">Особовий рахунок і провайдер зберігаються на рівні підключення.</span></div>
          <div><span className="helper">Крок 3</span><strong>Налаштуйте рядки</strong><span className="helper">Окремі лінії для дня/ночі, похідних або фіксованих послуг.</span></div>
        </div>
      </div>

      <div className="subcard">
        <h4>Активні підключення</h4>
        {loading ? <p className="helper">Завантаження послуг...</p> : null}
        {!loading && connections.length === 0 ? <p className="helper">Поки що немає підключених послуг.</p> : null}
        <div className="service-connection-list">
          {connections.map((connection) => {
            const service = serviceMap.get(connection.service_catalog_id);
            const provider = connection.provider_id ? providerMap.get(connection.provider_id) : null;
            const isExpanded = expandedConnectionId === connection.id;
            const meterLineCount = connection.charge_lines.filter((line) => line.line_kind === "meter_register").length;
            const derivedLineCount = connection.charge_lines.filter((line) => line.line_kind === "derived").length;
            const fixedLineCount = connection.charge_lines.filter((line) => line.line_kind === "fixed").length;
            return (
              <div key={connection.id} className="service-connection-card">
                <div className="service-connection-head">
                  <div>
                    <strong>{service?.name || `Послуга #${connection.service_catalog_id}`}</strong>
                    <div className="helper">{CALCULATION_KIND_LABELS[service?.calculation_kind || "fixed"]} • {service?.unit_name || "—"}</div>
                  </div>
                  <span className={`status-pill ${connection.status === "active" ? "ok" : "draft"}`}>{connectionStatusLabel(connection.status)}</span>
                </div>
                <div className="service-connection-meta">
                  <span>Постачальник: <strong>{provider?.name_full || "Не задано"}</strong></span>
                  <span>Особовий рахунок: <strong>{connection.personal_account || "—"}</strong></span>
                  <span>Діє з: <strong>{connection.started_at}</strong></span>
                  <span>Завершення: <strong>{connection.ended_at || "без дати"}</strong></span>
                </div>
                <div className="service-connection-overview">
                  <span>Рядків: <strong>{connection.charge_lines.length}</strong></span>
                  {meterLineCount ? <span>За лічильником: <strong>{meterLineCount}</strong></span> : null}
                  {fixedLineCount ? <span>Фіксованих: <strong>{fixedLineCount}</strong></span> : null}
                  {derivedLineCount ? <span>Похідних: <strong>{derivedLineCount}</strong></span> : null}
                </div>
                {isExpanded ? (
                  <div className="service-connection-lines">
                    {connection.charge_lines.map((line) => {
                      const meter = line.meter_id ? meterMap.get(line.meter_id) : null;
                      const donor = line.derived_from_line_id ? derivedSourceOptions.find((item) => item.id === line.derived_from_line_id) : null;
                      return (
                        <div key={line.id} className={`service-line-chip ${lineToneClass(line)}`}>
                          <strong>{line.label}</strong>
                          {line.line_kind === "meter_register" ? <span>{METER_REGISTER_LABELS[line.meter_register] || "Реєстр лічильника"}</span> : null}
                          <span>Ціна: {line.price_per_unit} / {line.unit_name}</span>
                          <span>Логіка: {lineKindLabel(line.line_kind)}</span>
                          {meter ? <span>Лічильник: {(meter.display_name || meter.meter_type_name || "Лічильник")}{meter.serial_number ? ` (${meter.serial_number})` : ""}</span> : null}
                          {line.line_kind === "meter_register" ? (
                            <span>
                              Початковий показник:{" "}
                              {line.initial_reading !== null && line.initial_reading !== undefined && line.initial_reading !== ""
                                ? line.initial_reading
                                : "—"}
                            </span>
                          ) : null}
                          {donor ? <span>Джерело обсягу: {donor.label}</span> : null}
                          {line.quantity_source !== "fixed_1" ? <span>База: {QUANTITY_SOURCE_LABELS[line.quantity_source]}</span> : null}
                        </div>
                      );
                    })}
                  </div>
                ) : null}
                {connection.note ? <div className="helper">{connection.note}</div> : null}
                <div className="row-actions">
                  <button className="secondary" onClick={() => setExpandedConnectionId((current) => current === connection.id ? null : connection.id)}>
                    {isExpanded ? "Сховати деталі" : "Показати деталі"}
                  </button>
                  <button className="secondary" onClick={() => openEdit(connection)}>Редагувати</button>
                  <button className="danger" onClick={async () => { if (!window.confirm("Видалити це підключення послуги?")) return; await onDeleteConnection(connection.id); }}>Видалити</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="subcard">
        <h4>Поточна логіка</h4>
        <p className="helper">Первинне налаштування послуги, лічильника, тарифу і початкового показника виконується тут. Вкладка Розрахунок призначена вже для помісячної роботи з показниками та сумами.</p>
      </div>

      {open ? (
        <Modal title={editingConnectionId ? "Редагувати послугу об'єкта" : "Підключити послугу"} onClose={closeModal}>
          <div className="settings-grid">
            <div className="forms-grid compact-grid">
              <Se label="Послуга" tip="Послуга" help="Оберіть послугу з довідника. Від цього залежить форма нижче." value={form.service_catalog_id} onChange={(e) => { const nextId = e.target.value; const nextService = services.find((item) => String(item.id) === nextId) || null; setForm((current) => ({ ...current, service_catalog_id: nextId })); applyServiceTemplate(nextService, form.started_at, form.meter_mode); }}>
                <option value="">Оберіть послугу</option>
                {services.filter((item) => item.is_active || String(item.id) === form.service_catalog_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </Se>
              <Se label="Постачальник" tip="Постачальник" help="Постачальник з довідника." value={form.provider_id} onChange={(e) => setForm((current) => ({ ...current, provider_id: e.target.value }))}>
                <option value="">Без постачальника</option>
                {recommendedProviders.filter((item) => item.is_active || String(item.id) === form.provider_id).map((item) => <option key={item.id} value={item.id}>{item.name_full}</option>)}
              </Se>
              <In label="Особовий рахунок" tip="Особовий рахунок" help="Номер рахунку або об'єктовий номер у постачальника." value={form.personal_account} onChange={(e) => setForm((current) => ({ ...current, personal_account: e.target.value }))} />
              <In label="Дата початку дії" tip="Дата початку дії" type="date" help="З цієї дати послуга діє для об'єкта." value={form.started_at} onChange={(e) => { const nextDate = e.target.value; setForm((current) => ({ ...current, started_at: nextDate, charge_lines: current.charge_lines.map((line) => ({ ...line, effective_from: nextDate || line.effective_from })) })); }} />
              <In label="Дата завершення" tip="Дата завершення" type="date" help="Залиште порожнім, якщо послуга активна." value={form.ended_at} onChange={(e) => setForm((current) => ({ ...current, ended_at: e.target.value }))} />
              <Se label="Статус" tip="Статус" value={form.status} onChange={(e) => setForm((current) => ({ ...current, status: e.target.value as "active" | "inactive" }))}>
                <option value="active">Активна</option>
                <option value="inactive">Неактивна</option>
              </Se>
            </div>

            <Ta label="Примітка" tip="Примітка" help="Коротка службова примітка по цьому підключенню." rows={3} value={form.note} onChange={(e) => setForm((current) => ({ ...current, note: e.target.value }))} />

            {selectedService ? (
              <div className="subcard">
                <h4>Логіка послуги</h4>
                <div className="service-connection-meta">
                  <span>Тип: <strong>{CALCULATION_KIND_LABELS[selectedService.calculation_kind]}</strong></span>
                  <span>Одиниця: <strong>{selectedService.unit_name}</strong></span>
                  <span>Лічильник: <strong>{selectedService.requires_meter ? selectedService.allowed_meter_utility_type ? UTILITY_TYPE_LABELS[selectedService.allowed_meter_utility_type] : "так" : "не потрібен"}</strong></span>
                  <span>Рекомендований ресурс постачальника: <strong>{selectedService.default_provider_utility_type ? UTILITY_TYPE_LABELS[selectedService.default_provider_utility_type] : "не задано"}</strong></span>
                </div>
                <div className="tariff-scenario-grid">
                  <div className={`tariff-scenario-card ${selectedService.calculation_kind === "fixed" ? "active" : ""}`}>
                    <strong>Фіксована послуга</strong>
                    <span>Ціна задається напряму, за потреби можна помножити на площу або к-сть прописаних.</span>
                  </div>
                  <div className={`tariff-scenario-card ${selectedService.calculation_kind === "metered" ? "active" : ""}`}>
                    <strong>За лічильником</strong>
                    <span>Обирається лічильник, тариф і початковий показник для кожного реєстру.</span>
                  </div>
                  <div className={`tariff-scenario-card ${selectedService.calculation_kind === "derived" ? "active" : ""}`}>
                    <strong>Похідна послуга</strong>
                    <span>Обсяг береться з іншого рядка послуги, а тут задається тільки тариф і джерело.</span>
                  </div>
                </div>
                <div className="tariff-context-box">
                  <strong>Поточний сценарій:</strong> {CALCULATION_KIND_LABELS[selectedService.calculation_kind]}.{" "}
                  {CALCULATION_KIND_DESCRIPTIONS[selectedService.calculation_kind]}
                </div>
                {selectedProvider && selectedService.default_provider_utility_type && selectedProvider.utility_type !== selectedService.default_provider_utility_type ? (
                  <div className="automation-window-preview">
                    <strong>Увага:</strong> обраний постачальник має ресурс {selectedProvider.utility_type ? UTILITY_TYPE_LABELS[selectedProvider.utility_type] : "не задано"}, а для цієї послуги рекомендовано {UTILITY_TYPE_LABELS[selectedService.default_provider_utility_type]}.
                  </div>
                ) : null}
                {selectedService.calculation_kind === "metered" && selectedService.allowed_meter_utility_type === "electricity" ? (
                  <Se label="Режим електролічильника" tip="Режим електролічильника" help="Створює один, два або три рядки всередині послуги Електроенергія." value={form.meter_mode} onChange={(e) => { const nextMode = e.target.value as ConnectionEditorForm["meter_mode"]; setForm((current) => ({ ...current, meter_mode: nextMode })); applyServiceTemplate(selectedService, form.started_at, nextMode); }}>
                    <option value="single">Однотарифний</option>
                    <option value="day_night">День / Ніч</option>
                    <option value="tri_zone">Тризонний</option>
                  </Se>
                ) : null}
              </div>
            ) : null}

            <div className="subcard">
              <div className="header-tools">
                <div>
                  <h4>Рядки розрахунку</h4>
                  <p className="helper">
                    Структура рядків формується автоматично за типом послуги. Для електроенергії режим
                    (1/2/3 зони) автоматично створює потрібні рядки. Для рядків за лічильником тут же
                    задається початковий показник.
                  </p>
                </div>
              </div>
              <div className="service-line-editor-list">
                {form.charge_lines.map((line, index) => (
                  <div key={`${line.label}-${index}`} className={`service-line-editor ${lineToneClass(line)}`}>
                    <div className="service-line-editor-toolbar">
                      <div className="service-line-title">
                        <strong>{line.label || `Рядок ${index + 1}`}</strong>
                        <span className="helper">
                          {line.line_kind === "meter_register"
                            ? METER_REGISTER_LABELS[line.meter_register] || "Реєстр лічильника"
                            : line.line_kind === "derived"
                              ? "Обсяг береться з іншої послуги"
                              : "Розрахунок без показників лічильника"}
                        </span>
                      </div>
                      <div className="row-actions">
                        <span className="status-pill">{lineKindLabel(line.line_kind)}</span>
                      </div>
                    </div>
                    <div className="forms-grid compact-grid">
                      <In
                        label="Назва рядка"
                        tip="Назва рядка"
                        help={canEditLineLabels ? "Як цей рядок буде показаний у списках і розрахунку." : "Для електроенергії назва рядка формується автоматично."}
                        value={line.label}
                        onChange={(e) => updateLine(index, { label: e.target.value })}
                        disabled={!canEditLineLabels}
                      />
                      <In label="Ціна" tip="Ціна" type="number" help="Вартість одиниці для цього рядка." value={line.price_per_unit} onChange={(e) => updateLine(index, { price_per_unit: e.target.value })} />
                      <In
                        label="Одиниця тарифу"
                        tip="Одиниця тарифу"
                        help="Одиниця береться з довідника послуг."
                        value={line.unit_name}
                        onChange={(e) => updateLine(index, { unit_name: e.target.value })}
                        disabled
                      />
                      <In
                        label="Діє з"
                        tip="Діє з"
                        type="date"
                        value={line.effective_from}
                        onChange={(e) => updateLine(index, { effective_from: e.target.value })}
                        disabled
                      />
                      {line.line_kind === "meter_register" ? (
                        <>
                          <Se label="Лічильник" tip="Лічильник" help="Фізичний лічильник об'єкта, з якого береться споживання." value={line.meter_id} onChange={(e) => updateLine(index, { meter_id: e.target.value })}>
                            <option value="">Оберіть лічильник</option>
                            {compatibleMeters.map((meter) => <option key={meter.id} value={meter.id}>{(meter.display_name || meter.meter_type_name || "Лічильник")}{meter.serial_number ? ` (${meter.serial_number})` : ""}</option>)}
                          </Se>
                          <In
                            label="Початковий показник"
                            tip="Початковий показник"
                            type="number"
                            min="0"
                            step="0.001"
                            help="Стартове значення для цього рядка послуги. Воно використовується як база до першого місячного показника."
                            value={line.initial_reading}
                            onChange={(e) => updateLine(index, { initial_reading: e.target.value })}
                          />
                        </>
                      ) : null}
                      {line.line_kind === "derived" ? (
                        <Se label="Брати обсяг з" tip="Брати обсяг з" help="Оберіть рядок-джерело для похідної послуги." value={line.derived_from_line_id} onChange={(e) => updateLine(index, { derived_from_line_id: e.target.value })}>
                          <option value="">
                            {requiredDerivedService
                              ? `Спочатку підключіть "${requiredDerivedService.name}"`
                              : "Оберіть послугу-джерело"}
                          </option>
                          {derivedSourceOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                        </Se>
                      ) : null}
                      {line.line_kind === "fixed" ? (
                        <Se label="База множення" tip="База множення" help="Фіксована, від площі або від кількості прописаних." value={line.quantity_source} onChange={(e) => updateLine(index, { quantity_source: e.target.value as QuantitySource })}>
                          <option value="fixed_1">{QUANTITY_SOURCE_LABELS.fixed_1}</option>
                          <option value="registered_residents">{QUANTITY_SOURCE_LABELS.registered_residents}</option>
                          <option value="area_m2">{QUANTITY_SOURCE_LABELS.area_m2}</option>
                        </Se>
                      ) : (
                        <In
                          label="База множення"
                          tip="База множення"
                          value={QUANTITY_SOURCE_LABELS[line.quantity_source]}
                          onChange={() => {}}
                          disabled
                        />
                      )}
                      <In
                        label="Множник"
                        tip="Множник"
                        type="number"
                        help="Для більшості послуг лишається 1."
                        value={line.quantity_multiplier}
                        onChange={(e) => updateLine(index, { quantity_multiplier: e.target.value })}
                        disabled={line.line_kind !== "fixed"}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="automation-window-preview">
              <strong>Примітка:</strong> якщо послуга рахується за лічильником, початковий показник задається саме тут, у рядку розрахунку послуги. У вкладці Розрахунок надалі вносяться вже поточні місячні показники.
            </div>
            {validationMessage ? (
              <div className="automation-window-preview">
                <strong>Перевірка:</strong> {validationMessage}
              </div>
            ) : null}

            <div className="row-actions">
              <button onClick={save} disabled={!!validationMessage}>{editingConnectionId ? "Зберегти зміни" : "Підключити послугу"}</button>
              <button className="secondary" onClick={closeModal}>Скасувати</button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
