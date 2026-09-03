import { useMemo, useState } from "react";
import type { ProviderItem, UtilityType } from "@/shared/api/types";
import { Modal } from "@/shared/ui/modal";

type ProviderForm = {
  name_full: string;
  utility_type: UtilityType;
  adapter_code: string;
  is_active: boolean;
  note: string;
};

const EMPTY_PROVIDER_FORM: ProviderForm = {
  name_full: "",
  utility_type: "other",
  adapter_code: "manual_stub",
  is_active: true,
  note: "",
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

export function ProvidersSection({
  providers,
  createProvider,
  updateProvider,
  deleteProvider,
  confirmRun,
  pushToast,
}: {
  providers: ProviderItem[];
  createProvider: (payload: ProviderForm) => Promise<void>;
  updateProvider: (providerId: number, payload: ProviderForm) => Promise<void>;
  deleteProvider: (providerId: number) => Promise<void>;
  confirmRun: (title: string, message: string, action: () => void | Promise<void>) => void;
  pushToast: (message: string, type?: "info" | "success" | "error") => void;
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ProviderForm>(EMPTY_PROVIDER_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const sortedProviders = useMemo(
    () => [...providers].sort((a, b) => a.name_full.localeCompare(b.name_full, "uk")),
    [providers],
  );

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_PROVIDER_FORM);
    setFormOpen(true);
  };

  const openEdit = (item: ProviderItem) => {
    setEditingId(item.id);
    setForm({
      name_full: item.name_full || "",
      utility_type: item.utility_type || "other",
      adapter_code: item.adapter_code || "manual_stub",
      is_active: !!item.is_active,
      note: item.note || "",
    });
    setFormOpen(true);
  };

  const closeForm = () => {
    if (busy) return;
    setFormOpen(false);
    setEditingId(null);
    setForm(EMPTY_PROVIDER_FORM);
  };

  const submit = async () => {
    if (!form.name_full.trim()) return;
    setBusy(true);
    try {
      if (editingId) {
        await updateProvider(editingId, form);
      } else {
        await createProvider(form);
      }
      setFormOpen(false);
      setEditingId(null);
      setForm(EMPTY_PROVIDER_FORM);
    } catch (error) {
      pushToast(error instanceof Error ? error.message : "Не вдалося зберегти постачальника", "error");
    } finally {
      setBusy(false);
    }
  };

  const askDelete = (item: ProviderItem) => {
    confirmRun(
      "Видалити постачальника",
      `Видалити постачальника "${item.name_full}"? Це можливо лише якщо він ще ніде не використовується.`,
      async () => {
        try {
          await deleteProvider(item.id);
        } catch (error) {
          pushToast(error instanceof Error ? error.message : "Не вдалося видалити постачальника", "error");
        }
      },
    );
  };

  return (
    <div className="subcard">
      <p className="helper">Довідник постачальників і типів інтеграцій. Саме цей список використовується при створенні тарифів та автоматизацій.</p>

      <div className="row-actions">
        <button onClick={openCreate}>Створити постачальника</button>
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
                  <button className="secondary icon-btn" onClick={() => openEdit(item)}>
                    ✎
                  </button>{" "}
                  <button className="danger icon-btn" onClick={() => askDelete(item)}>
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

      {formOpen ? (
        <Modal title={editingId ? "Редагувати постачальника" : "Створити постачальника"} onClose={closeForm}>
          <div className="forms-grid compact-grid">
            <label className="field">
              <span className="field-label">Повна назва</span>
              <input
                title="Назва постачальника, яку буде видно в тарифах, автоматизаціях і списках."
                value={form.name_full}
                onChange={(e) => setForm((s) => ({ ...s, name_full: e.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Вид ресурсу</span>
              <select
                title="Основний ресурс або напрям послуг, з яким працює постачальник."
                value={form.utility_type}
                onChange={(e) => setForm((s) => ({ ...s, utility_type: e.target.value as UtilityType }))}
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
                value={getIntegrationType(form.adapter_code)}
                onChange={(e) =>
                  setForm((s) => ({
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
                value={form.note}
                onChange={(e) => setForm((s) => ({ ...s, note: e.target.value }))}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((s) => ({ ...s, is_active: e.target.checked }))}
              />
              Активний постачальник
            </label>
          </div>

          <div className="row-actions top-gap">
            <button onClick={submit} disabled={busy || !form.name_full.trim()}>
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
