import { useMemo, useState } from "react";
import type { ServiceCalculationKind, ServiceCatalogItem, UtilityType } from "@/shared/api/types";
import { unitLabel } from "@/shared/utils/format";
import { Modal } from "@/shared/ui/modal";

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

type ServiceCatalogPayload = {
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
};

function slugifyServiceCode(value: string) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9а-яіїєґ]+/gi, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 64) || "service"
  );
}

export function ServiceCatalogSection({
  serviceCatalog,
  createServiceCatalogItem,
  updateServiceCatalogItem,
  deleteServiceCatalogItem,
  confirmRun,
  pushToast,
}: {
  serviceCatalog: ServiceCatalogItem[];
  createServiceCatalogItem: (payload: ServiceCatalogPayload) => Promise<void>;
  updateServiceCatalogItem: (serviceCatalogId: number, payload: ServiceCatalogPayload) => Promise<void>;
  deleteServiceCatalogItem: (serviceCatalogId: number) => Promise<void>;
  confirmRun: (title: string, message: string, action: () => void | Promise<void>) => void;
  pushToast: (message: string, type?: "info" | "success" | "error") => void;
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ServiceCatalogForm>(EMPTY_SERVICE_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const sortedServices = useMemo(
    () => [...serviceCatalog].sort((a, b) => (a.display_order - b.display_order) || a.name.localeCompare(b.name, "uk")),
    [serviceCatalog],
  );

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_SERVICE_FORM);
    setFormOpen(true);
  };

  const openEdit = (item: ServiceCatalogItem) => {
    setEditingId(item.id);
    setForm({
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
    setFormOpen(true);
  };

  const closeForm = () => {
    if (busy) return;
    setFormOpen(false);
    setEditingId(null);
    setForm(EMPTY_SERVICE_FORM);
  };

  const submit = async () => {
    if (!form.name.trim()) return;
    const cleanName = form.name.trim();
    const payload: ServiceCatalogPayload = {
      code: slugifyServiceCode(cleanName),
      name: cleanName,
      calculation_kind: form.calculation_kind,
      unit_name: form.unit_name.trim() || "month",
      requires_meter: form.calculation_kind === "metered" ? form.requires_meter : false,
      allowed_meter_utility_type:
        form.calculation_kind === "metered" && form.requires_meter && form.allowed_meter_utility_type
          ? form.allowed_meter_utility_type
          : null,
      default_provider_utility_type: form.default_provider_utility_type || null,
      derived_from_service_id:
        form.calculation_kind === "derived" && form.derived_from_service_id
          ? Number(form.derived_from_service_id)
          : null,
      display_order: Number(form.display_order || 100),
      is_active: form.is_active,
    };
    setBusy(true);
    try {
      if (editingId) {
        await updateServiceCatalogItem(editingId, payload);
      } else {
        await createServiceCatalogItem(payload);
      }
      setFormOpen(false);
      setEditingId(null);
      setForm(EMPTY_SERVICE_FORM);
    } catch (error) {
      pushToast(error instanceof Error ? error.message : "Не вдалося зберегти послугу", "error");
    } finally {
      setBusy(false);
    }
  };

  const askDelete = (item: ServiceCatalogItem) => {
    confirmRun(
      "Видалити послугу",
      `Видалити послугу "${item.name}"? Це можливо лише якщо вона ще ніде не використовується.`,
      async () => {
        try {
          await deleteServiceCatalogItem(item.id);
        } catch (error) {
          pushToast(error instanceof Error ? error.message : "Не вдалося видалити послугу", "error");
        }
      },
    );
  };

  return (
    <div className="subcard">
      <p className="helper">Довідник послуг визначає логіку майбутнього розрахунку. Тут задається назва послуги, тип розрахунку та базова одиниця.</p>

      <div className="row-actions">
        <button onClick={openCreate}>Створити послугу</button>
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
                <td>{unitLabel(item.unit_name)}</td>
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
                  <button className="secondary icon-btn" onClick={() => openEdit(item)}>
                    ✎
                  </button>{" "}
                  <button className="danger icon-btn" onClick={() => askDelete(item)}>
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

      {formOpen ? (
        <Modal title={editingId ? "Редагувати послугу" : "Створити послугу"} onClose={closeForm}>
          <div className="forms-grid compact-grid">
            <label className="field">
              <span className="field-label">Назва послуги</span>
              <input
                title="Назва, яку користувач бачить у довіднику послуг і в підключеннях об'єкта."
                value={form.name}
                onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Тип розрахунку</span>
              <select
                title="Фіксована, за лічильником або похідна від іншої послуги."
                value={form.calculation_kind}
                onChange={(e) =>
                  setForm((s) => ({
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
                value={form.unit_name}
                onChange={(e) => setForm((s) => ({ ...s, unit_name: e.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Порядок відображення</span>
              <input
                title="Менше число показується вище у списках послуг."
                type="number"
                min="0"
                step="1"
                value={form.display_order}
                onChange={(e) => setForm((s) => ({ ...s, display_order: e.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Бажаний ресурс постачальника</span>
              <select
                title="Який ресурс найчастіше буде у постачальника цієї послуги."
                value={form.default_provider_utility_type}
                onChange={(e) => setForm((s) => ({ ...s, default_provider_utility_type: e.target.value as UtilityType | "" }))}
              >
                <option value="">Не задано</option>
                {Object.entries(UTILITY_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {form.calculation_kind === "metered" ? (
              <>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={form.requires_meter}
                    onChange={(e) => setForm((s) => ({ ...s, requires_meter: e.target.checked }))}
                  />
                  Послуга використовує лічильник
                </label>
                <label className="field">
                  <span className="field-label">Який лічильник підходить</span>
                  <select
                    title="Обмежує вибір лічильників для цієї послуги при підключенні до об'єкта."
                    value={form.allowed_meter_utility_type}
                    onChange={(e) => setForm((s) => ({ ...s, allowed_meter_utility_type: e.target.value as UtilityType | "" }))}
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
            {form.calculation_kind === "derived" ? (
              <label className="field">
                <span className="field-label">Брати обсяг з послуги</span>
                <select
                  title="Донор обсягу для похідної послуги, наприклад Водовідведення від Водопостачання."
                  value={form.derived_from_service_id}
                  onChange={(e) => setForm((s) => ({ ...s, derived_from_service_id: e.target.value }))}
                >
                  <option value="">Оберіть послугу-джерело</option>
                  {sortedServices
                    .filter((item) => item.id !== editingId)
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
                checked={form.is_active}
                onChange={(e) => setForm((s) => ({ ...s, is_active: e.target.checked }))}
              />
              Активна послуга
            </label>
          </div>

          <div className="row-actions top-gap">
            <button onClick={submit} disabled={busy || !form.name.trim() || !form.display_order.trim()}>
              {editingId ? "Оновити" : "Створити"}
            </button>
            <button className="secondary" onClick={closeForm} disabled={busy}>
              Скасувати
            </button>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
