import { In, Se } from "@/shared/ui/form-controls";
import { TariffRow } from "@/features/tariffs/components/TariffRow";
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
  personal_account: string;
  meter_id: string;
  meter_register: string;
  source_service_name: string;
};

export function TariffsTab({
  tar,
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
  money,
}: {
  tar: any[];
  openT: (row: any) => void;
  newTar: NewTariffForm;
  setNewTar: Dispatch<SetStateAction<NewTariffForm>>;
  createTariff: () => Promise<void>;
  meters: Array<{ id: number; service_name: string; serial_number?: string | null }>;
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
  money: (v: unknown) => string;
}) {
  const sourceOptions = tar
    .map((x) => x.service_name)
    .filter((name, idx, arr) => !!name && arr.indexOf(name) === idx && name !== newTar.service_name);
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Послуга</th>
              <th>Тариф</th>
              <th>Одиниця</th>
              <th>Особовий рахунок</th>
              <th>Статус</th>
              <th>Остання звірка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>{tar.map((r) => <TariffRow key={r.service_name} row={r} open={openT} />)}</tbody>
        </table>
      </div>
      <div className="subcard top-gap">
        <h4>Додати тариф</h4>
        <div className="forms-grid">
          <In tip="Назва послуги" placeholder="Послуга" value={newTar.service_name} onChange={(e) => setNewTar((s) => ({ ...s, service_name: e.target.value }))} />
          <Se tip="Спосіб нарахування" value={newTar.charge_mode} onChange={(e) => setNewTar((s) => ({ ...s, charge_mode: e.target.value }))}>
            <option value="fixed">Фіксований</option>
            <option value="metered">За лічильником</option>
          </Se>
          <In tip="Тариф за одиницю" placeholder="Ціна" value={newTar.price_per_unit} onChange={(e) => setNewTar((s) => ({ ...s, price_per_unit: e.target.value }))} />
          <Se tip="Одиниця тарифу" value={newTar.unit_name} onChange={(e) => setNewTar((s) => ({ ...s, unit_name: e.target.value }))}>
            <option value="kWh">1 кВт·год</option>
            <option value="m3">1 м3</option>
            <option value="month">місяць</option>
          </Se>
          <In tip="Дата початку дії тарифу" type="date" value={newTar.effective_from} onChange={(e) => setNewTar((s) => ({ ...s, effective_from: e.target.value }))} />
          <In tip="Особовий рахунок у постачальника" placeholder="Особовий рахунок" value={newTar.personal_account} onChange={(e) => setNewTar((s) => ({ ...s, personal_account: e.target.value }))} />
          <Se tip="Статус послуги у розрахунках" value={newTar.service_status} onChange={(e) => setNewTar((s) => ({ ...s, service_status: e.target.value }))}>
            <option value="active">Активна</option>
            <option value="inactive">Неактивна</option>
          </Se>
          {newTar.service_status === "inactive" && <In tip="Місяць, з якого послуга вимикається" type="month" value={newTar.disable_from_month} onChange={(e) => setNewTar((s) => ({ ...s, disable_from_month: e.target.value }))} />}
          {newTar.charge_mode === "metered" && <>
            <Se
              tip="Лічильник для цієї послуги (якщо не розрахунок від іншої послуги)"
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
                  {m.service_name}{m.serial_number ? ` (${m.serial_number})` : ""}
                </option>
              ))}
            </Se>
            <In
              tip="Реєстр показника лічильника (наприклад total/day/night)"
              placeholder="register_name"
              value={newTar.meter_register}
              onChange={(e) => setNewTar((s) => ({ ...s, meter_register: e.target.value }))}
            />
            <Se
              tip="Розрахунок від послуги (для похідних послуг, напр. водовідведення)"
              value={newTar.source_service_name}
              onChange={(e) => setNewTar((s) => ({ ...s, source_service_name: e.target.value, meter_id: e.target.value ? "" : s.meter_id }))}
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
                <In tip="Початковий показник лічильника" placeholder="Початковий показник" value={newTar.initial_meter_reading} onChange={(e) => setNewTar((s) => ({ ...s, initial_meter_reading: e.target.value }))} />
                <In tip="Серійний номер лічильника (необов'язково)" placeholder="Серійний номер" value={newTar.meter_serial_number} onChange={(e) => setNewTar((s) => ({ ...s, meter_serial_number: e.target.value }))} />
              </>
            )}
          </>}
        </div>
        <button onClick={createTariff}>Додати тариф</button>
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
                        <td>{String(row.month).padStart(2, "0")}.{row.year}</td>
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
