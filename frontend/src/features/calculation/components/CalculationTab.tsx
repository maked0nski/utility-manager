import { In } from "@/shared/ui/form-controls";
import type { ChangeEvent, Dispatch, RefObject, SetStateAction } from "react";
import type { BillingHistoryItem, CalculationRow } from "@/shared/api/types";

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
    month_payments: string;
    month_payment_date?: string | null;
  };
  calc_locked?: boolean;
}

interface CalculationTabProps {
  detail: DetailLike;
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  setPayModal: (open: boolean) => void;
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
  toggleLockMonth: () => Promise<void>;
  resetSortDefault: () => void;
  accr: number;
  history?: BillingHistoryItem[];
}

export function CalculationTab({
  detail,
  money,
  dt,
  setPayModal,
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
  toggleLockMonth,
  resetSortDefault,
  accr,
  history = [],
}: CalculationTabProps) {
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

  return (
    <>
      <div className="summary-grid">
        <div className="metric">
          <div className="label">Борг з минулого</div>
          <div className="value">{money(detail.utility_balance.previous_month_debt)}</div>
        </div>
        <div className="metric">
          <div className="label">Борг на зараз</div>
          <div className="value">{money(detail.utility_balance.current_balance)}</div>
        </div>
        <div className="metric">
          <div className="label row-inline">
            <span>Оплачено</span>
            <button className="icon-btn" onClick={() => setPayModal(true)}>
              ✎
            </button>
          </div>
          <div className="value">{money(detail.utility_balance.month_payments)}</div>
          <small>{dt(detail.utility_balance.month_payment_date)}</small>
        </div>
      </div>
      {detail.calc_locked && <p className="ok">Місяць підтверджено: його баланс враховується у наступних періодах.</p>}
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
            {sortedRows.map((r, idx) => {
              const e = editSrv === r.service_name;
              const hm = !!r.meter_id;
              const editable = !r.service_name.startsWith("Відшкодування:");
              const rowChanged = changed(r);
              return (
                <tr key={`${r.service_name}_${idx}`} ref={e ? editRef : null} className={e && rowChanged ? "row-changed" : ""}>
                  <td>{r.service_name}</td>
                  <td>
                    {e && hm && r.can_edit_previous ? (
                      <In
                        tip="Попередній показник"
                        placeholder="Попередній показник"
                        onKeyDown={() => {}}
                        value={draft.previous_reading ?? ""}
                        onChange={(x: InputEvt) =>
                          setDraft((s) => ({ ...s, previous_reading: x.target.value }))
                        }
                      />
                    ) : (
                      asInt(r.previous_reading)
                    )}
                  </td>
                  <td>
                    {e && hm ? (
                      <In
                        tip="Поточний показник"
                        placeholder="Поточний показник"
                        onKeyDown={() => {}}
                        value={draft.current_reading ?? ""}
                        onChange={(x: InputEvt) =>
                          setDraft((s) => ({ ...s, current_reading: x.target.value }))
                        }
                      />
                    ) : (
                      asInt(r.current_reading)
                    )}
                  </td>
                  <td>{hm ? asInt(r.difference) : ""}</td>
                  <td>
                    {e && editable ? (
                      <In
                        tip="Тариф"
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
          <button className="secondary" onClick={toggleLockMonth}>
            {detail.calc_locked ? "Зняти підтвердження місяця" : "Підтвердити нарахування"}
          </button>
          <button className="secondary" onClick={resetSortDefault}>
            Порядок за замовчуванням
          </button>
        </div>
        <strong>Усього нараховано: {money(accr)}</strong>
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
    </>
  );
}
