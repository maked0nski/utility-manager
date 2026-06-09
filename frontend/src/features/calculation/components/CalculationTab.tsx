import { useState } from "react";
import { In } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import type { ChangeEvent, Dispatch, RefObject, SetStateAction } from "react";
import type { BillingHistoryItem, CalculationRow, MeterExpectedRegistersResult } from "@/shared/api/types";

type RowDraft = {
  previous_reading?: string;
  current_reading?: string;
  unit_price?: string;
};

type InputEvt = ChangeEvent<HTMLInputElement>;

interface DetailLike {
  utility_balance: {
    previous_month_debt: string;
    current_balance: string;
  };
  calc_locked?: boolean;
}

interface CalculationTabProps {
  detail: DetailLike;
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  toggleSort: (
    key:
      | "default"
      | "service_name"
      | "previous_reading"
      | "current_reading"
      | "difference"
      | "unit_price"
      | "amount",
  ) => void;
  sortIcon: (
    key:
      | "default"
      | "service_name"
      | "previous_reading"
      | "current_reading"
      | "difference"
      | "unit_price"
      | "amount",
  ) => string;
  sortedRows: CalculationRow[];
  editSrv: string | null;
  editRef: RefObject<HTMLTableRowElement | null>;
  asInt: (v: unknown) => string;
  start: (row: CalculationRow) => void;
  stopEdit: () => void;
  setDraft: Dispatch<SetStateAction<RowDraft>>;
  draft: RowDraft;
  changed: (row: CalculationRow) => boolean;
  saveRow: (row: CalculationRow) => Promise<void>;
  recalcMonth: () => Promise<void>;
  confirmMonth: () => Promise<void>;
  reopenMonth: (reason: string) => Promise<void>;
  resetSortDefault: () => void;
  accr: number;
  history?: BillingHistoryItem[];
  openBatchReadingModal: () => Promise<void>;
  batchReadingMeterOptions: Array<{ meter_id: number; label: string }>;
  batchReadingModalOpen: boolean;
  closeBatchReadingModal: () => void;
  batchReadingMetas: Record<string, MeterExpectedRegistersResult>;
  batchReadingDraft: Record<string, Record<string, string>>;
  setBatchReadingDraft: Dispatch<SetStateAction<Record<string, Record<string, string>>>>;
  saveBatchReadings: () => Promise<void>;
  batchReadingSaving?: boolean;
}

type DisplayRow =
  | { type: "group"; key: string; label: string; subtotal: number }
  | { type: "row"; key: string; row: CalculationRow; childOfGroup: boolean };

function normalizeGroupedServiceLabel(row: CalculationRow) {
  if (row.service_group_label) return row.service_group_label;
  const serviceName = (row.service_name || "").trim();
  if (!row.meter_plan_mode || !row.meter_register || row.meter_register === "total") return null;
  if (row.meter_plan_mode === "single") return null;
  if (serviceName.toLowerCase().includes("електро")) return "Електроенергія";
  return null;
}

export function CalculationTab({
  detail,
  money,
  dt,
  toggleSort,
  sortIcon,
  sortedRows,
  editSrv,
  editRef,
  asInt,
  start,
  stopEdit,
  setDraft,
  draft,
  changed,
  saveRow,
  recalcMonth,
  confirmMonth,
  reopenMonth,
  resetSortDefault,
  accr,
  history = [],
  openBatchReadingModal,
  batchReadingMeterOptions,
  batchReadingModalOpen,
  closeBatchReadingModal,
  batchReadingMetas,
  batchReadingDraft,
  setBatchReadingDraft,
  saveBatchReadings,
  batchReadingSaving,
}: CalculationTabProps) {
  const isCompensationRow = (row: CalculationRow) => row.service_name.startsWith("Відшкодування:");
  const rowByLineId = new Map<number, CalculationRow>();
  for (const row of sortedRows) {
    if (row.line_id) rowByLineId.set(row.line_id, row);
  }
  const displayRows: DisplayRow[] = (() => {
    const grouped = new Map<string, { label: string; subtotal: number; rows: CalculationRow[] }>();
    const orderedKeys: string[] = [];
    const plainRows: DisplayRow[] = [];
    for (const row of sortedRows) {
      const label = normalizeGroupedServiceLabel(row);
      if (!label) {
        plainRows.push({ type: "row", key: `row:${row.service_name}:${plainRows.length}`, row, childOfGroup: false });
        continue;
      }
      const key = row.service_group_key || `${label}:${row.meter_id || "no-meter"}`;
      if (!grouped.has(key)) {
        grouped.set(key, { label, subtotal: 0, rows: [] });
        orderedKeys.push(key);
      }
      const bucket = grouped.get(key)!;
      bucket.rows.push(row);
      bucket.subtotal += Number(row.amount || 0);
    }
    const result: DisplayRow[] = [];
    const usedKeys = new Set<string>();
    for (const row of sortedRows) {
      const label = normalizeGroupedServiceLabel(row);
      if (!label) {
        const next = plainRows.shift();
        if (next) result.push(next);
        continue;
      }
      const key = row.service_group_key || `${label}:${row.meter_id || "no-meter"}`;
      if (usedKeys.has(key)) continue;
      usedKeys.add(key);
      const bucket = grouped.get(key);
      if (!bucket) continue;
      result.push({ type: "group", key: `group:${key}`, label: bucket.label, subtotal: bucket.subtotal });
      bucket.rows.forEach((child, index) => {
        result.push({
          type: "row",
          key: `row:${key}:${index}:${child.service_name}`,
          row: child,
          childOfGroup: true,
        });
      });
    }
    return result;
  })();
  const utilityAccrual = sortedRows
    .filter((row) => !isCompensationRow(row))
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const compensationTotal = sortedRows
    .filter((row) => isCompensationRow(row))
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const accrualWithCompensation = utilityAccrual + compensationTotal;
  const actionLabel = (action: string) =>
    (
      {
        tariff_created: "Створено тариф",
        tariff_updated: "Оновлено тариф",
        tariff_applied_from_period: "Змінено тариф з періоду",
        tariff_deleted: "Видалено тариф",
        reading_created: "Додано показник",
        reading_updated: "Оновлено показник",
        meter_initial_reading_updated: "Оновлено стартовий показник",
        month_recalculated: "Перераховано місяць",
        month_locked: "Підтверджено місяць",
        month_unlocked: "Знято підтвердження місяця",
        utility_payment_saved: "Збережено оплату комуналки",
        utility_payment_updated: "Оновлено оплату комуналки",
        utility_payment_deleted: "Видалено оплату комуналки",
        owner_charge_created: "Додано витрату/відшкодування",
        owner_charge_updated: "Оновлено витрату/відшкодування",
        owner_charge_deleted: "Видалено витрату/відшкодування",
      }[action] || action
    );
  const fmtDetails = (entry: BillingHistoryItem) => {
    const d = entry?.details || {};
    if (!d || typeof d !== "object") return "";
    const pairs = Object.entries(d).filter(([, v]) => v !== null && v !== undefined && String(v) !== "");
    return pairs.map(([k, v]) => `${k}: ${v}`).join("; ");
  };
  const dtTime = (x: string | null | undefined) => {
    if (!x) return "";
    const d = new Date(x);
    if (Number.isNaN(d.getTime())) return "";
    return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };
  const planModeLabel = (mode?: string | null) => {
    if (mode === "single") return "Однотарифний";
    if (mode === "day_night") return "День/Ніч";
    if (mode === "tri_zone") return "Тризонний";
    return mode || "";
  };
  const [reopenModalOpen, setReopenModalOpen] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [reopenSaving, setReopenSaving] = useState(false);

  const handleLockAction = async () => {
    if (!detail.calc_locked) {
      await confirmMonth();
      return;
    }
    setReopenModalOpen(true);
  };

  const submitReopen = async () => {
    const reason = reopenReason.trim();
    if (!reason) return;
    setReopenSaving(true);
    try {
      await reopenMonth(reason);
      setReopenModalOpen(false);
      setReopenReason("");
    } finally {
      setReopenSaving(false);
    }
  };

  return (
    <>
      {detail.calc_locked && <p className="ok">Місяць підтверджено: його баланс враховується у наступних періодах.</p>}
      <p className="helper">
        Вкладка Розрахунок призначена для помісячного внесення поточних показників і перевірки сум. Початкові
        показники лічильників налаштовуються у вкладці Послуги об&apos;єкта.
      </p>
      <div className={`table-wrap mobile-sticky ${detail.calc_locked ? "locked-table" : ""}`}>
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort("service_name")} style={{ cursor: "pointer" }}>
                Послуга{sortIcon("service_name")}
              </th>
              <th onClick={() => toggleSort("previous_reading")} style={{ cursor: "pointer" }}>
                Попер.{sortIcon("previous_reading")}
              </th>
              <th onClick={() => toggleSort("current_reading")} style={{ cursor: "pointer" }}>
                Поточний{sortIcon("current_reading")}
              </th>
              <th onClick={() => toggleSort("difference")} style={{ cursor: "pointer" }}>
                Різниця{sortIcon("difference")}
              </th>
              <th onClick={() => toggleSort("unit_price")} style={{ cursor: "pointer" }}>
                Тариф{sortIcon("unit_price")}
              </th>
              <th onClick={() => toggleSort("amount")} style={{ cursor: "pointer" }}>
                Сума{sortIcon("amount")}
              </th>
              <th className="right-sticky"></th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((item, idx) => {
              if (item.type === "group") {
                return (
                  <tr key={item.key} className="calc-group-row">
                    <td>
                      <strong>{item.label}</strong>
                      <div className="helper">Згруповано за багатозонним режимом лічильника</div>
                    </td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td>
                      <strong>{money(item.subtotal)}</strong>
                    </td>
                    <td className="right-sticky"></td>
                  </tr>
                );
              }
              const r = item.row;
              const e = editSrv === r.service_name;
              const hm = !!r.meter_id;
              const editable = !r.service_name.startsWith("Відшкодування:");
              const rowChanged = changed(r);
              const sourceRow =
                r.source_line_id !== null && r.source_line_id !== undefined
                  ? rowByLineId.get(r.source_line_id) || null
                  : null;
              const previousReading = r.previous_reading ?? sourceRow?.previous_reading ?? null;
              const currentReading = r.current_reading ?? sourceRow?.current_reading ?? null;
              const difference = r.difference ?? sourceRow?.difference ?? null;
              return (
                <tr key={item.key || `${r.service_name}_${idx}`} ref={e ? editRef : null} className={`${e && rowChanged ? "row-changed" : ""} ${item.childOfGroup ? "calc-child-row" : ""}`.trim()}>
                  <td>
                    {item.childOfGroup ? (r.service_line_label || r.meter_register_label || r.service_name) : r.service_name}
                    {!item.childOfGroup && r.meter_register_label ? (
                      <div className="helper">{r.meter_register_label}</div>
                    ) : null}
                    {r.meter_plan_mode ? (
                      <div className="helper">
                        режим: {planModeLabel(r.meter_plan_mode)}
                        {r.meter_expected_registers?.length ? ` • очікуються: ${r.meter_expected_registers.join(", ")}` : ""}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    {e && hm && r.can_edit_previous ? (
                      <>
                        <In
                          label="Стартове значення"
                          tip="Стартове значення"
                          help="Використовуйте лише якщо потрібно службово скоригувати перший базовий показник до появи історії."
                          placeholder="Стартове значення"
                          onKeyDown={() => {}}
                          value={draft.previous_reading ?? ""}
                          onChange={(x: InputEvt) =>
                            setDraft((s) => ({ ...s, previous_reading: x.target.value }))
                          }
                        />
                        <div className="helper">Базове налаштування краще виконувати у Послугах об&apos;єкта.</div>
                      </>
                    ) : (
                      asInt(previousReading)
                    )}
                  </td>
                  <td>
                    {e && hm ? (
                      <In
                        tip="Поточний показник"
                        help="Внесіть фактичне поточне значення з лічильника для цього місяця."
                        placeholder="Поточний показник"
                        onKeyDown={() => {}}
                        value={draft.current_reading ?? ""}
                        onChange={(x: InputEvt) =>
                          setDraft((s) => ({ ...s, current_reading: x.target.value }))
                        }
                      />
                    ) : (
                      asInt(currentReading)
                    )}
                  </td>
                  <td>{difference !== null && difference !== undefined ? asInt(difference) : ""}</td>
                  <td>
                    {e && editable ? (
                      <In
                        tip="Тариф"
                        help="Службове редагування ціни для цього рядка поточного місяця."
                        placeholder="Тариф"
                        onKeyDown={() => {}}
                        value={draft.unit_price ?? ""}
                        onChange={(x: InputEvt) =>
                          setDraft((s) => ({ ...s, unit_price: x.target.value }))
                        }
                      />
                    ) : (
                      money(r.unit_price)
                    )}
                  </td>
                  <td>
                    {money(r.amount)}
                    {e && editable && (
                      <div>
                        <button disabled={!rowChanged} onClick={() => saveRow(r)}>
                          Зберегти
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="right-sticky">
                    {!r.service_name.startsWith("Відшкодування:") && (
                      <button className="icon-btn" onClick={() => (e ? stopEdit() : start(r))}>
                        ✎
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="row-inline top-gap">
        <div className="row-actions">
          <button onClick={recalcMonth}>Заповнити місяць послугами</button>
          <button className="secondary" onClick={() => void openBatchReadingModal()}>
            Внести показники
          </button>
          <button className="secondary" onClick={() => void handleLockAction()}>
            {detail.calc_locked ? "Розблокувати місяць" : "Підтвердити нарахування"}
          </button>
          <button className="secondary" onClick={resetSortDefault}>
            Порядок за замовчуванням
          </button>
        </div>
        <div className="calc-totals">
          <strong>Нараховано (комунальні): {money(utilityAccrual)}</strong>
          <strong>Компенсація: {money(compensationTotal)}</strong>
          <strong>Усього до оплати: {money(accrualWithCompensation || accr)}</strong>
        </div>
      </div>
      <div className="subcard top-gap">
        <h4>Історія змін місяця</h4>
        {!history.length && <p className="helper">Змін для цього періоду ще немає.</p>}
        {!!history.length && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Коли</th>
                  <th>Користувач</th>
                  <th>Дія</th>
                  <th>Послуга</th>
                  <th>Деталі</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}>
                    <td>{dtTime(item.created_at)}</td>
                    <td>{item.actor_username}</td>
                    <td>{actionLabel(item.action)}</td>
                    <td>{item.service_name || ""}</td>
                    <td>{fmtDetails(item)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {batchReadingModalOpen && (
        <Modal title="Внести показники лічильників" onClose={closeBatchReadingModal}>
          {!batchReadingMeterOptions.length ? (
            <p className="helper">Немає доступних лічильників для внесення показників.</p>
          ) : (
            <>
              <p className="helper">
                У цьому вікні можна одразу внести всі або лише частину показників для наявних лічильників за вибраний місяць.
              </p>
              <p className="helper">
                Доступно лічильників: <strong>{batchReadingMeterOptions.length}</strong>. Порожні поля не зберігаються.
              </p>
              {batchReadingMeterOptions.map((item) => {
                const meta = batchReadingMetas[String(item.meter_id)];
                if (!meta) return null;
                const meterDraft = batchReadingDraft[String(item.meter_id)] || {};
                return (
                  <div key={item.meter_id} className="subcard top-gap">
                    <h4>{meta.meter_service_name}</h4>
                    <div className="helper">
                      режим: {meta.plan_mode}
                      {meta.effective_from ? ` • діє з ${meta.effective_from}` : ""}
                    </div>
                    <div className="forms-grid compact-grid top-gap">
                      {meta.registers.map((register) => (
                        <In
                          key={`${item.meter_id}:${register.register_name}`}
                          tip={`${register.label}${register.service_name ? ` • ${register.service_name}` : ""}`}
                          help={`Поточний показник по цьому реєстру на кінець вибраного місяця.${register.previous_reading !== null && register.previous_reading !== undefined ? ` Попередній показник: ${register.previous_reading}. Нове значення має бути не меншим.` : ""}`}
                          placeholder="Поточний показник"
                          type="number"
                          min={register.previous_reading ?? "0"}
                          step="0.001"
                          value={meterDraft[register.register_name] ?? (register.current_reading || "")}
                          onChange={(e) =>
                            setBatchReadingDraft((state) => ({
                              ...state,
                              [String(item.meter_id)]: {
                                ...(state[String(item.meter_id)] || {}),
                                [register.register_name]: e.target.value,
                              },
                            }))
                          }
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
              <div className="row-actions top-gap">
                <button onClick={saveBatchReadings} disabled={!!batchReadingSaving}>
                  {batchReadingSaving ? "Збереження..." : "Зберегти показники"}
                </button>
                <button className="secondary" onClick={closeBatchReadingModal}>
                  Скасувати
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
      {reopenModalOpen && (
        <Modal title="Розблокувати підтверджений місяць" onClose={() => setReopenModalOpen(false)}>
          <p className="helper">
            Після розблокування цей місяць можна буде змінювати. Наступні періоди можуть потребувати повторної
            перевірки та перерахунку.
          </p>
          <In
            label="Причина розблокування"
            tip="Причина розблокування"
            help="Коротко опишіть, чому потрібно змінити вже підтверджений місяць."
            placeholder="Наприклад: знайшли помилку в оплаті або компенсації"
            value={reopenReason}
            onChange={(e: InputEvt) => setReopenReason(e.target.value)}
            onKeyDown={() => {}}
          />
          <div className="row-actions top-gap">
            <button onClick={() => void submitReopen()} disabled={reopenSaving || !reopenReason.trim()}>
              {reopenSaving ? "Розблокування..." : "Розблокувати місяць"}
            </button>
            <button
              className="secondary"
              onClick={() => {
                setReopenModalOpen(false);
                setReopenReason("");
              }}
            >
              Скасувати
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
