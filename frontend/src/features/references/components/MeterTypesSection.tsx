import { useMemo, useState } from "react";
import type { MeterTypeItem, UtilityType } from "@/shared/api/types";
import { Modal } from "@/shared/ui/modal";

type MeterTypeForm = {
  name: string;
  utility_type: UtilityType;
  sort_order: string;
  is_active: boolean;
};

const EMPTY_METER_TYPE_FORM: MeterTypeForm = {
  name: "",
  utility_type: "other",
  sort_order: "100",
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

type MeterTypePayload = {
  name: string;
  utility_type: UtilityType;
  sort_order: number;
  is_active: boolean;
};

export function MeterTypesSection({
  meterTypes,
  createMeterType,
  updateMeterType,
  deleteMeterType,
  confirmRun,
  pushToast,
}: {
  meterTypes: MeterTypeItem[];
  createMeterType: (payload: MeterTypePayload) => Promise<void>;
  updateMeterType: (meterTypeId: number, payload: MeterTypePayload) => Promise<void>;
  deleteMeterType: (meterTypeId: number) => Promise<void>;
  confirmRun: (title: string, message: string, action: () => void | Promise<void>) => void;
  pushToast: (message: string, type?: "info" | "success" | "error") => void;
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<MeterTypeForm>(EMPTY_METER_TYPE_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const sortedMeterTypes = useMemo(
    () => [...meterTypes].sort((a, b) => (a.sort_order - b.sort_order) || a.name.localeCompare(b.name, "uk")),
    [meterTypes],
  );

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_METER_TYPE_FORM);
    setFormOpen(true);
  };

  const openEdit = (item: MeterTypeItem) => {
    setEditingId(item.id);
    setForm({
      name: item.name || "",
      utility_type: item.utility_type || "other",
      sort_order: String(item.sort_order ?? 100),
      is_active: !!item.is_active,
    });
    setFormOpen(true);
  };

  const closeForm = () => {
    if (busy) return;
    setFormOpen(false);
    setEditingId(null);
    setForm(EMPTY_METER_TYPE_FORM);
  };

  const submit = async () => {
    if (!form.name.trim()) return;
    const payload: MeterTypePayload = {
      name: form.name.trim(),
      utility_type: form.utility_type,
      sort_order: Number(form.sort_order || 100),
      is_active: form.is_active,
    };
    setBusy(true);
    try {
      if (editingId) {
        await updateMeterType(editingId, payload);
      } else {
        await createMeterType(payload);
      }
      setFormOpen(false);
      setEditingId(null);
      setForm(EMPTY_METER_TYPE_FORM);
    } catch (error) {
      pushToast(error instanceof Error ? error.message : "Не вдалося зберегти тип лічильника", "error");
    } finally {
      setBusy(false);
    }
  };

  const askDelete = (item: MeterTypeItem) => {
    confirmRun(
      "Видалити тип лічильника",
      `Видалити тип лічильника "${item.name}"? Це можливо лише якщо він ще ніде не використовується.`,
      async () => {
        try {
          await deleteMeterType(item.id);
        } catch (error) {
          pushToast(error instanceof Error ? error.message : "Не вдалося видалити тип лічильника", "error");
        }
      },
    );
  };

  return (
    <div className="subcard">
      <p className="helper">Саме цей список використовується у формі створення лічильника. Користувач бачить лише назву типу, а вид ресурсу потрібен системі для тарифів, зон електрики та сумісних автоматизацій.</p>
      <p className="helper">Службовий код система формує автоматично, він у цьому інтерфейсі не показується.</p>

      <div className="row-actions">
        <button onClick={openCreate}>Створити тип лічильника</button>
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
                  <button className="secondary icon-btn" onClick={() => openEdit(item)}>
                    ✎
                  </button>{" "}
                  <button className="danger icon-btn" onClick={() => askDelete(item)}>
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

      {formOpen ? (
        <Modal title={editingId ? "Редагувати тип лічильника" : "Створити тип лічильника"} onClose={closeForm}>
          <div className="forms-grid compact-grid">
            <label className="field">
              <span className="field-label">Назва типу</span>
              <input
                title="Назва, яку користувач бачить у формі створення лічильника."
                value={form.name}
                onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Вид ресурсу</span>
              <select
                title="Визначає, для якого ресурсу цей тип лічильника буде доступний у тарифах та автоматизаціях."
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
              <span className="field-label">Порядок відображення</span>
              <input
                title="Менше число показується вище у списку типів лічильників."
                type="number"
                min="0"
                step="1"
                value={form.sort_order}
                onChange={(e) => setForm((s) => ({ ...s, sort_order: e.target.value }))}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((s) => ({ ...s, is_active: e.target.checked }))}
              />
              Активний тип
            </label>
          </div>

          <div className="row-actions top-gap">
            <button onClick={submit} disabled={busy || !form.name.trim() || !form.sort_order.trim()}>
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
