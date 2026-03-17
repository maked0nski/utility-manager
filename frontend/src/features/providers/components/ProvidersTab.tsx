import { useMemo, useState } from "react";
import type {
  MeterTypeItem,
  ProviderItem,
  ServiceCalculationKind,
  ServiceCatalogItem,
  UtilityType,
} from "@/shared/api/types";

type ProviderForm = {
  name_full: string;
  utility_type: UtilityType;
  adapter_code: string;
  is_active: boolean;
  note: string;
};

type MeterTypeForm = {
  name: string;
  utility_type: UtilityType;
  sort_order: string;
  is_active: boolean;
};

type ServiceCatalogForm = {
  name: string;
  calculation_kind: ServiceCalculationKind;
  unit_name: string;
  requires_meter: boolean;
  allowed_meter_utility_type: UtilityType | "";
  default_provider_utility_type: UtilityType | "";
  derived_from_service_id: string;
  display_order: string;
  is_active: boolean;
};

const EMPTY_PROVIDER_FORM: ProviderForm = {
  name_full: "",
  utility_type: "other",
  adapter_code: "manual_stub",
  is_active: true,
  note: "",
};

const EMPTY_METER_TYPE_FORM: MeterTypeForm = {
  name: "",
  utility_type: "other",
  sort_order: "100",
  is_active: true,
};

const EMPTY_SERVICE_FORM: ServiceCatalogForm = {
  name: "",
  calculation_kind: "fixed",
  unit_name: "month",
  requires_meter: false,
  allowed_meter_utility_type: "",
  default_provider_utility_type: "",
  derived_from_service_id: "",
  display_order: "100",
  is_active: true,
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

const SERVICE_CALCULATION_LABELS: Record<ServiceCalculationKind, string> = {
  fixed: "Фіксована сума",
  metered: "За лічильником",
  derived: "Похідна від іншої послуги",
};

const INTEGRATION_TYPE_LABELS = {
  manual_stub: "Ручне ведення",
  auto_connected: "Автоматичне підключення",
} as const;

function getIntegrationType(adapterCode: string) {
  return adapterCode === "manual_stub" ? "manual_stub" : "auto_connected";
}

function getAdapterCodeFromIntegrationType(value: "manual_stub" | "auto_connected", currentAdapterCode: string) {
  if (value === "manual_stub") return "manual_stub";
  if (currentAdapterCode && currentAdapterCode !== "manual_stub") return currentAdapterCode;
  return "auto_connected";
}

export function ProvidersTab({
  providers,
  meterTypes,
  serviceCatalog,
  createProvider,
  updateProvider,
  deleteProvider,
  createMeterType,
  updateMeterType,
  deleteMeterType,
  createServiceCatalogItem,
  updateServiceCatalogItem,
  deleteServiceCatalogItem,
}: {
  providers: ProviderItem[];
  meterTypes: MeterTypeItem[];
  serviceCatalog: ServiceCatalogItem[];
  createProvider: (payload: ProviderForm) => Promise<void>;
  updateProvider: (providerId: number, payload: ProviderForm) => Promise<void>;
  deleteProvider: (providerId: number) => Promise<void>;
  createMeterType: (payload: {
    name: string;
    utility_type: UtilityType;
    sort_order: number;
    is_active: boolean;
  }) => Promise<void>;
  updateMeterType: (
    meterTypeId: number,
    payload: {
      name: string;
      utility_type: UtilityType;
      sort_order: number;
      is_active: boolean;
    },
  ) => Promise<void>;
  deleteMeterType: (meterTypeId: number) => Promise<void>;
  createServiceCatalogItem: (payload: {
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
  }) => Promise<void>;
  updateServiceCatalogItem: (
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
  ) => Promise<void>;
  deleteServiceCatalogItem: (serviceCatalogId: number) => Promise<void>;
}) {
  const [providerForm, setProviderForm] = useState<ProviderForm>(EMPTY_PROVIDER_FORM);
  const [providerEditingId, setProviderEditingId] = useState<number | null>(null);
  const [providerBusyId, setProviderBusyId] = useState<number | null>(null);

  const [meterTypeForm, setMeterTypeForm] = useState<MeterTypeForm>(EMPTY_METER_TYPE_FORM);
  const [meterTypeEditingId, setMeterTypeEditingId] = useState<number | null>(null);
  const [meterTypeBusyId, setMeterTypeBusyId] = useState<number | null>(null);
  const [serviceForm, setServiceForm] = useState<ServiceCatalogForm>(EMPTY_SERVICE_FORM);
  const [serviceEditingId, setServiceEditingId] = useState<number | null>(null);
  const [serviceBusyId, setServiceBusyId] = useState<number | null>(null);

  const sortedProviders = useMemo(
    () => [...providers].sort((a, b) => a.name_full.localeCompare(b.name_full, "uk")),
    [providers],
  );
  const sortedMeterTypes = useMemo(
    () => [...meterTypes].sort((a, b) => (a.sort_order - b.sort_order) || a.name.localeCompare(b.name, "uk")),
    [meterTypes],
  );
  const sortedServices = useMemo(
    () => [...serviceCatalog].sort((a, b) => (a.display_order - b.display_order) || a.name.localeCompare(b.name, "uk")),
    [serviceCatalog],
  );

  const resetProviderForm = () => {
    setProviderForm(EMPTY_PROVIDER_FORM);
    setProviderEditingId(null);
  };

  const startEditProvider = (item: ProviderItem) => {
    setProviderEditingId(item.id);
    setProviderForm({
      name_full: item.name_full || "",
      utility_type: item.utility_type || "other",
      adapter_code: item.adapter_code || "manual_stub",
      is_active: !!item.is_active,
      note: item.note || "",
    });
  };

  const submitProvider = async () => {
    if (!providerForm.name_full.trim()) return;
    if (providerEditingId) {
      setProviderBusyId(providerEditingId);
      try {
        await updateProvider(providerEditingId, providerForm);
        resetProviderForm();
      } finally {
        setProviderBusyId(null);
      }
      return;
    }
    setProviderBusyId(0);
    try {
      await createProvider(providerForm);
      resetProviderForm();
    } finally {
      setProviderBusyId(null);
    }
  };

  const resetMeterTypeForm = () => {
    setMeterTypeForm(EMPTY_METER_TYPE_FORM);
    setMeterTypeEditingId(null);
  };

  const slugifyServiceCode = (value: string) =>
    value
      .toLowerCase()
      .replace(/[^a-z0-9а-яіїєґ]+/gi, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 64) || "service";

  const startEditMeterType = (item: MeterTypeItem) => {
    setMeterTypeEditingId(item.id);
    setMeterTypeForm({
      name: item.name || "",
      utility_type: item.utility_type || "other",
      sort_order: String(item.sort_order ?? 100),
      is_active: !!item.is_active,
    });
  };

  const submitMeterType = async () => {
    if (!meterTypeForm.name.trim()) return;
    const cleanName = meterTypeForm.name.trim();
    const payload = {
      name: cleanName,
      utility_type: meterTypeForm.utility_type,
      sort_order: Number(meterTypeForm.sort_order || 100),
      is_active: meterTypeForm.is_active,
    };
    if (meterTypeEditingId) {
      setMeterTypeBusyId(meterTypeEditingId);
      try {
        await updateMeterType(meterTypeEditingId, payload);
        resetMeterTypeForm();
      } finally {
        setMeterTypeBusyId(null);
      }
      return;
    }
    setMeterTypeBusyId(0);
    try {
      await createMeterType(payload);
      resetMeterTypeForm();
    } finally {
      setMeterTypeBusyId(null);
    }
  };

  const resetServiceForm = () => {
    setServiceForm(EMPTY_SERVICE_FORM);
    setServiceEditingId(null);
  };

  const startEditService = (item: ServiceCatalogItem) => {
    setServiceEditingId(item.id);
    setServiceForm({
      name: item.name || "",
      calculation_kind: item.calculation_kind,
      unit_name: item.unit_name || "month",
      requires_meter: !!item.requires_meter,
      allowed_meter_utility_type: item.allowed_meter_utility_type || "",
      default_provider_utility_type: item.default_provider_utility_type || "",
      derived_from_service_id: item.derived_from_service_id ? String(item.derived_from_service_id) : "",
      display_order: String(item.display_order ?? 100),
      is_active: !!item.is_active,
    });
  };

  const submitService = async () => {
    if (!serviceForm.name.trim()) return;
    const cleanName = serviceForm.name.trim();
    const payload = {
      code: slugifyServiceCode(cleanName),
      name: cleanName,
      calculation_kind: serviceForm.calculation_kind,
      unit_name: serviceForm.unit_name.trim() || "month",
      requires_meter: serviceForm.calculation_kind === "metered" ? serviceForm.requires_meter : false,
      allowed_meter_utility_type:
        serviceForm.calculation_kind === "metered" && serviceForm.requires_meter && serviceForm.allowed_meter_utility_type
          ? serviceForm.allowed_meter_utility_type
          : null,
      default_provider_utility_type: serviceForm.default_provider_utility_type || null,
      derived_from_service_id:
        serviceForm.calculation_kind === "derived" && serviceForm.derived_from_service_id
          ? Number(serviceForm.derived_from_service_id)
          : null,
      display_order: Number(serviceForm.display_order || 100),
      is_active: serviceForm.is_active,
    };
    if (serviceEditingId) {
      setServiceBusyId(serviceEditingId);
      try {
        await updateServiceCatalogItem(serviceEditingId, payload);
        resetServiceForm();
      } finally {
        setServiceBusyId(null);
      }
      return;
    }
    setServiceBusyId(0);
    try {
      await createServiceCatalogItem(payload);
      resetServiceForm();
    } finally {
      setServiceBusyId(null);
    }
  };

  return (
    <div className="property-sections">
      <div className="subcard">
        <h4>Початкове налаштування</h4>
        <div className="property-steps">
          <div>
            <span className="helper">Крок 1</span>
            <strong>Створіть типи лічильників</strong>
            <span className="helper">Наприклад: Електролічильник, Лічильник води, Газовий лічильник.</span>
          </div>
          <div>
            <span className="helper">Крок 2</span>
            <strong>Додайте постачальників</strong>
            <span className="helper">Ці записи потім використовуються у тарифах та автоматизаціях.</span>
          </div>
          <div>
            <span className="helper">Крок 3</span>
            <strong>Поверніться до об&apos;єкта</strong>
            <span className="helper">Після цього можна створювати лічильники, орендаря і тарифи.</span>
          </div>
        </div>
      </div>

      <div className="subcard">
        <h4>Допоміжні списки</h4>
        <p className="helper">Тут зібрані початкові довідники, які використовуються далі в тарифах, автоматизаціях і при створенні лічильників.</p>
        <p className="helper">Рекомендований порядок заповнення: 1. Послуги, 2. Типи лічильників, 3. Постачальники.</p>
      </div>

      <div className="subcard">
        <h4>Послуги</h4>
        <p className="helper">Довідник послуг визначає логіку майбутнього розрахунку. Тут задається назва послуги, тип розрахунку та базова одиниця.</p>

        <div className="forms-grid compact-grid">
          <label className="field">
            <span className="field-label">Назва послуги</span>
            <input
              title="Назва, яку користувач бачить у довіднику послуг і в підключеннях об'єкта."
              value={serviceForm.name}
              onChange={(e) => setServiceForm((s) => ({ ...s, name: e.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Тип розрахунку</span>
            <select
              title="Фіксована, за лічильником або похідна від іншої послуги."
              value={serviceForm.calculation_kind}
              onChange={(e) =>
                setServiceForm((s) => ({
                  ...s,
                  calculation_kind: e.target.value as ServiceCalculationKind,
                  requires_meter: e.target.value === "metered" ? s.requires_meter : false,
                  derived_from_service_id: e.target.value === "derived" ? s.derived_from_service_id : "",
                }))
              }
            >
              {Object.entries(SERVICE_CALCULATION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Одиниця тарифу</span>
            <input
              title="Місяць, м3, кВт·год або інша одиниця, яка використовується в розрахунку."
              value={serviceForm.unit_name}
              onChange={(e) => setServiceForm((s) => ({ ...s, unit_name: e.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Порядок відображення</span>
            <input
              title="Менше число показується вище у списках послуг."
              type="number"
              min="0"
              step="1"
              value={serviceForm.display_order}
              onChange={(e) => setServiceForm((s) => ({ ...s, display_order: e.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Бажаний ресурс постачальника</span>
            <select
              title="Який ресурс найчастіше буде у постачальника цієї послуги."
              value={serviceForm.default_provider_utility_type}
              onChange={(e) => setServiceForm((s) => ({ ...s, default_provider_utility_type: e.target.value as UtilityType | "" }))}
            >
              <option value="">Не задано</option>
              {Object.entries(UTILITY_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {serviceForm.calculation_kind === "metered" ? (
            <>
              <label className="check">
                <input
                  type="checkbox"
                  checked={serviceForm.requires_meter}
                  onChange={(e) => setServiceForm((s) => ({ ...s, requires_meter: e.target.checked }))}
                />
                Послуга використовує лічильник
              </label>
              <label className="field">
                <span className="field-label">Який лічильник підходить</span>
                <select
                  title="Обмежує вибір лічильників для цієї послуги при підключенні до об'єкта."
                  value={serviceForm.allowed_meter_utility_type}
                  onChange={(e) => setServiceForm((s) => ({ ...s, allowed_meter_utility_type: e.target.value as UtilityType | "" }))}
                >
                  <option value="">Не задано</option>
                  {Object.entries(UTILITY_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          {serviceForm.calculation_kind === "derived" ? (
            <label className="field">
              <span className="field-label">Брати обсяг з послуги</span>
              <select
                title="Донор обсягу для похідної послуги, наприклад Водовідведення від Водопостачання."
                value={serviceForm.derived_from_service_id}
                onChange={(e) => setServiceForm((s) => ({ ...s, derived_from_service_id: e.target.value }))}
              >
                <option value="">Оберіть послугу-джерело</option>
                {sortedServices
                  .filter((item) => item.id !== serviceEditingId)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
              </select>
            </label>
          ) : null}
          <label className="check">
            <input
              type="checkbox"
              checked={serviceForm.is_active}
              onChange={(e) => setServiceForm((s) => ({ ...s, is_active: e.target.checked }))}
            />
            Активна послуга
          </label>
        </div>

        <div className="row-actions">
          <button
            onClick={submitService}
            disabled={serviceBusyId !== null || !serviceForm.name.trim() || !serviceForm.display_order.trim()}
          >
            {serviceEditingId ? "Оновити" : "Створити"}
          </button>
          {serviceEditingId ? (
            <button className="secondary" onClick={resetServiceForm} disabled={serviceBusyId !== null}>
              Скасувати
            </button>
          ) : null}
        </div>

        <div className="table-wrap top-gap">
          <table>
            <thead>
              <tr>
                <th>Назва</th>
                <th>Тип розрахунку</th>
                <th>Одиниця</th>
                <th>Лічильник / джерело</th>
                <th>Порядок</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedServices.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{SERVICE_CALCULATION_LABELS[item.calculation_kind]}</td>
                  <td>{item.unit_name}</td>
                  <td>
                    {item.calculation_kind === "metered"
                      ? item.allowed_meter_utility_type
                        ? UTILITY_TYPE_LABELS[item.allowed_meter_utility_type]
                        : "Визначається пізніше"
                      : item.calculation_kind === "derived"
                        ? sortedServices.find((service) => service.id === item.derived_from_service_id)?.name || "Не задано"
                        : "Не потрібен"}
                  </td>
                  <td>{item.display_order}</td>
                  <td>{item.is_active ? "Активна" : "Вимкнена"}</td>
                  <td>
                    <button className="secondary icon-btn" onClick={() => startEditService(item)}>
                      ✎
                    </button>
                    {" "}
                    <button
                      className="danger icon-btn"
                      onClick={async () => {
                        setServiceBusyId(item.id);
                        try {
                          await deleteServiceCatalogItem(item.id);
                          if (serviceEditingId === item.id) resetServiceForm();
                        } finally {
                          setServiceBusyId(null);
                        }
                      }}
                      disabled={serviceBusyId !== null}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
              {sortedServices.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <span className="helper">Послуг поки немає.</span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="subcard">
        <h4>Типи лічильників</h4>
        <p className="helper">Саме цей список використовується у формі створення лічильника. Користувач бачить лише назву типу, а вид ресурсу потрібен системі для тарифів, зон електрики та сумісних автоматизацій.</p>
        <p className="helper">Службовий код система формує автоматично, він у цьому інтерфейсі не показується.</p>

        <div className="forms-grid compact-grid">
          <label className="field">
            <span className="field-label">Назва типу</span>
            <input
              title="Назва, яку користувач бачить у формі створення лічильника."
              value={meterTypeForm.name}
              onChange={(e) => setMeterTypeForm((s) => ({ ...s, name: e.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Вид ресурсу</span>
            <select
              title="Визначає, для якого ресурсу цей тип лічильника буде доступний у тарифах та автоматизаціях."
              value={meterTypeForm.utility_type}
              onChange={(e) => setMeterTypeForm((s) => ({ ...s, utility_type: e.target.value as UtilityType }))}
            >
              {Object.entries(UTILITY_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Порядок відображення</span>
            <input
              title="Менше число показується вище у списку типів лічильників."
              type="number"
              min="0"
              step="1"
              value={meterTypeForm.sort_order}
              onChange={(e) => setMeterTypeForm((s) => ({ ...s, sort_order: e.target.value }))}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={meterTypeForm.is_active}
              onChange={(e) => setMeterTypeForm((s) => ({ ...s, is_active: e.target.checked }))}
            />
            Активний тип
          </label>
        </div>

        <div className="row-actions">
          <button
            onClick={submitMeterType}
            disabled={
              meterTypeBusyId !== null ||
              !meterTypeForm.name.trim() ||
              !meterTypeForm.sort_order.trim()
            }
          >
            {meterTypeEditingId ? "Оновити" : "Створити"}
          </button>
          {meterTypeEditingId ? (
            <button className="secondary" onClick={resetMeterTypeForm} disabled={meterTypeBusyId !== null}>
              Скасувати
            </button>
          ) : null}
        </div>

        <div className="table-wrap top-gap">
          <table>
            <thead>
              <tr>
                <th>Назва</th>
                <th>Вид ресурсу</th>
                <th>Порядок відображення</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedMeterTypes.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{UTILITY_TYPE_LABELS[item.utility_type]}</td>
                  <td>{item.sort_order}</td>
                  <td>{item.is_active ? "Активний" : "Вимкнений"}</td>
                  <td>
                    <button className="secondary icon-btn" onClick={() => startEditMeterType(item)}>
                      ✎
                    </button>
                    {" "}
                    <button
                      className="danger icon-btn"
                      onClick={async () => {
                        setMeterTypeBusyId(item.id);
                        try {
                          await deleteMeterType(item.id);
                          if (meterTypeEditingId === item.id) resetMeterTypeForm();
                        } finally {
                          setMeterTypeBusyId(null);
                        }
                      }}
                      disabled={meterTypeBusyId !== null}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
              {sortedMeterTypes.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <span className="helper">Типів лічильників поки немає.</span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="subcard">
        <h4>Постачальники</h4>
        <p className="helper">Довідник постачальників і типів інтеграцій. Саме цей список використовується при створенні тарифів та автоматизацій.</p>

        <div className="forms-grid compact-grid">
          <label className="field">
            <span className="field-label">Повна назва</span>
            <input
              title="Назва постачальника, яку буде видно в тарифах, автоматизаціях і списках."
              value={providerForm.name_full}
              onChange={(e) => setProviderForm((s) => ({ ...s, name_full: e.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Вид ресурсу</span>
            <select
              title="Основний ресурс або напрям послуг, з яким працює постачальник."
              value={providerForm.utility_type}
              onChange={(e) => setProviderForm((s) => ({ ...s, utility_type: e.target.value as UtilityType }))}
            >
              {Object.entries(UTILITY_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Тип інтеграції</span>
            <select
              title="Ручне ведення використовується без автоматизації, автоматичне підключення вмикає готову інтеграцію."
              value={getIntegrationType(providerForm.adapter_code)}
              onChange={(e) =>
                setProviderForm((s) => ({
                  ...s,
                  adapter_code: getAdapterCodeFromIntegrationType(
                    e.target.value as "manual_stub" | "auto_connected",
                    s.adapter_code,
                  ),
                }))
              }
            >
              <option value="manual_stub">{INTEGRATION_TYPE_LABELS.manual_stub}</option>
              <option value="auto_connected">{INTEGRATION_TYPE_LABELS.auto_connected}</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Примітка</span>
            <input
              title="Коротка внутрішня примітка про постачальника або особливості співпраці."
              value={providerForm.note}
              onChange={(e) => setProviderForm((s) => ({ ...s, note: e.target.value }))}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={providerForm.is_active}
              onChange={(e) => setProviderForm((s) => ({ ...s, is_active: e.target.checked }))}
            />
            Активний постачальник
          </label>
        </div>

        <div className="row-actions">
          <button onClick={submitProvider} disabled={providerBusyId !== null || !providerForm.name_full.trim()}>
            {providerEditingId ? "Оновити" : "Створити"}
          </button>
          {providerEditingId ? (
            <button className="secondary" onClick={resetProviderForm} disabled={providerBusyId !== null}>
              Скасувати
            </button>
          ) : null}
        </div>

        <div className="table-wrap top-gap">
          <table>
            <thead>
              <tr>
                <th>Назва</th>
                <th>Вид ресурсу</th>
                <th>Тип інтеграції</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedProviders.map((item) => (
                <tr key={item.id}>
                  <td>{item.name_full}</td>
                  <td>{item.utility_type ? UTILITY_TYPE_LABELS[item.utility_type] : "Не задано"}</td>
                  <td>{INTEGRATION_TYPE_LABELS[getIntegrationType(item.adapter_code)]}</td>
                  <td>{item.is_active ? "Активний" : "Вимкнений"}</td>
                  <td>
                    <button className="secondary icon-btn" onClick={() => startEditProvider(item)}>
                      ✎
                    </button>
                    {" "}
                    <button
                      className="danger icon-btn"
                      onClick={async () => {
                        setProviderBusyId(item.id);
                        try {
                          await deleteProvider(item.id);
                          if (providerEditingId === item.id) resetProviderForm();
                        } finally {
                          setProviderBusyId(null);
                        }
                      }}
                      disabled={providerBusyId !== null}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
              {sortedProviders.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <span className="helper">Постачальників поки немає.</span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
