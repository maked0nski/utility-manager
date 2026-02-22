import { In, Se } from "@/shared/ui/form-controls";
import type { Dispatch, RefObject, SetStateAction } from "react";
import type { MeterItem, MeterUpsertForm } from "@/shared/api/types";
import { CalculationTab } from "@/features/calculation/components/CalculationTab";
import { TenantTab } from "@/features/tenants/components/TenantTab";
import { TariffsTab } from "@/features/tariffs/components/TariffsTab";
import { OwnerCostsTab } from "@/features/expenses/components/OwnerCostsTab";
import { ReportTab } from "@/features/report/components/ReportTab";

type TabKey = "calc" | "tenant" | "tariffs" | "owner" | "report" | "property";

export function DashboardContent({
  apartmentsQuery,
  detailBundleQuery,
  sel,
  detail,
  shiftPeriod,
  periodLabel,
  p,
  money,
  tab,
  setTab,
  dt,
  setPayModal,
  toggleSort,
  sortIcon,
  sortedRows,
  editSrv,
  editRef,
  asInt,
  start,
  setEditSrv,
  setDraft,
  draft,
  changed,
  saveRow,
  recalcMonth,
  toggleLockMonth,
  resetSortDefault,
  accr,
  history,
  newTenant,
  setNewTenant,
  createTenantAndAssign,
  assignExisting,
  setAssignExisting,
  tenants,
  assignTenant,
  tenant,
  setTenant,
  formatPhone,
  saveTenant,
  tar,
  openT,
  newTar,
  setNewTar,
  createTariff,
  meters,
  own,
  setOwn,
  addOwner,
  mnt,
  setMnt,
  addMaint,
  oc,
  mr,
  openOc,
  openMr,
  saveAp,
  delAp,
  ap,
  setAp,
  meterForm,
  setMeterForm,
  editingMeterId,
  submitMeter,
  startEditMeter,
  askDeleteMeter,
  resetMeterForm,
}: {
  apartmentsQuery: { isLoading?: boolean };
  detailBundleQuery: { isFetching?: boolean };
  sel: any;
  detail: any;
  shiftPeriod: (delta: number) => void;
  periodLabel: (year: number, month: number) => string;
  p: { year: number; month: number };
  money: (v: unknown) => string;
  tab: TabKey;
  setTab: (tab: TabKey) => void;
  dt: (x: string | Date | null | undefined) => string;
  setPayModal: (open: boolean) => void;
  toggleSort: any;
  sortIcon: any;
  sortedRows: any[];
  editSrv: string | null;
  editRef: RefObject<HTMLTableRowElement | null>;
  asInt: (v: unknown) => string;
  start: (row: any) => void;
  setEditSrv: (v: string | null) => void;
  setDraft: (v: any) => void;
  draft: any;
  changed: (row: any) => boolean;
  saveRow: (row: any) => Promise<void>;
  recalcMonth: () => Promise<void>;
  toggleLockMonth: () => Promise<void>;
  resetSortDefault: () => void;
  accr: number;
  history: any[];
  newTenant: any;
  setNewTenant: (v: any) => void;
  createTenantAndAssign: () => Promise<void>;
  assignExisting: any;
  setAssignExisting: (v: any) => void;
  tenants: any[];
  assignTenant: () => Promise<void>;
  tenant: any;
  setTenant: (v: any) => void;
  formatPhone: (v: unknown) => string;
  saveTenant: () => Promise<void>;
  tar: any[];
  openT: (item: any) => void;
  newTar: any;
  setNewTar: (v: any) => void;
  createTariff: () => Promise<void>;
  meters: MeterItem[];
  own: any;
  setOwn: (v: any) => void;
  addOwner: () => Promise<void>;
  mnt: any;
  setMnt: (v: any) => void;
  addMaint: () => Promise<void>;
  oc: any[];
  mr: any[];
  openOc: (item: any) => void;
  openMr: (item: any) => void;
  saveAp: () => Promise<void>;
  delAp: () => Promise<void>;
  ap: { address: string };
  setAp: Dispatch<SetStateAction<{ address: string }>>;
  meterForm: MeterUpsertForm;
  setMeterForm: Dispatch<SetStateAction<MeterUpsertForm>>;
  editingMeterId: number | null;
  submitMeter: () => Promise<void>;
  startEditMeter: (meter: MeterItem) => void;
  askDeleteMeter: (meter: MeterItem) => void;
  resetMeterForm: () => void;
}) {
  return (
    <section className="card content">
      {apartmentsQuery.isLoading && <p className="helper">Завантаження списку нерухомості...</p>}
      {detailBundleQuery.isFetching && sel && (
        <p className="helper">Оновлення даних обраного періоду...</p>
      )}
      {!sel && <p>Оберіть об&apos;єкт.</p>}
      {sel && detail && (
        <>
          <div className="header-tools">
            <h3>
              {detail.address} | Орендар: {detail.tenant?.full_name || "відсутній"}
            </h3>
            <div className="period-nav">
              <button onClick={() => shiftPeriod(-1)}>◀</button>
              <span>{periodLabel(p.year, p.month)}</span>
              <button onClick={() => shiftPeriod(1)}>▶</button>
              <span className={`status-pill ${detail.calc_locked ? "ok" : "draft"}`}>
                {detail.calc_locked ? "Підтверджено" : "Чернетка"}
              </span>
            </div>
          </div>
          <p className={detail.rent?.confirmed ? "helper" : "error"}>
            {detail.rent?.confirmed
              ? `Оренда підтверджена (${money(detail.rent.payment_amount)} ${detail.rent.currency})`
              : "Оренда не підтверджена"}
          </p>
          <div className="tabs">
            <button className={`tab ${tab === "calc" ? "active" : ""}`} onClick={() => setTab("calc")}>
              Розрахунок
            </button>
            <button
              className={`tab ${tab === "tenant" ? "active" : ""}`}
              onClick={() => setTab("tenant")}
            >
              Орендар
            </button>
            <button
              className={`tab ${tab === "tariffs" ? "active" : ""}`}
              onClick={() => setTab("tariffs")}
            >
              Тарифи
            </button>
            <button
              className={`tab ${tab === "owner" ? "active" : ""}`}
              onClick={() => setTab("owner")}
            >
              Витрати власника
            </button>
            <button
              className={`tab ${tab === "report" ? "active" : ""}`}
              onClick={() => setTab("report")}
            >
              Звіт за місяць
            </button>
            <button
              className={`tab ${tab === "property" ? "active" : ""}`}
              onClick={() => setTab("property")}
            >
              Об&apos;єкт
            </button>
          </div>

          {tab === "calc" && (
            <CalculationTab
              detail={detail}
              money={money}
              dt={dt}
              setPayModal={setPayModal}
              toggleSort={toggleSort}
              sortIcon={sortIcon}
              sortedRows={sortedRows}
              editSrv={editSrv}
              editRef={editRef}
              asInt={asInt}
              start={start}
              stopEdit={() => {
                setEditSrv(null);
                setDraft({});
              }}
              setDraft={setDraft}
              draft={draft}
              changed={changed}
              saveRow={saveRow}
              recalcMonth={recalcMonth}
              toggleLockMonth={toggleLockMonth}
              resetSortDefault={resetSortDefault}
              accr={accr}
              history={history}
            />
          )}

          {tab === "tenant" && (
            <TenantTab
              detail={detail}
              newTenant={newTenant}
              setNewTenant={setNewTenant}
              createTenantAndAssign={createTenantAndAssign}
              assignExisting={assignExisting}
              setAssignExisting={setAssignExisting}
              tenants={tenants}
              assignTenant={assignTenant}
              tenant={tenant}
              setTenant={setTenant}
              formatPhone={formatPhone}
              saveTenant={saveTenant}
            />
          )}

          {tab === "tariffs" && (
            <TariffsTab
              tar={tar}
              openT={openT}
              newTar={newTar}
              setNewTar={setNewTar}
              createTariff={createTariff}
              meters={meters}
            />
          )}

          {tab === "owner" && (
            <OwnerCostsTab
              own={own}
              setOwn={setOwn}
              addOwner={addOwner}
              mnt={mnt}
              setMnt={setMnt}
              addMaint={addMaint}
              oc={oc}
              mr={mr}
              money={money}
              dt={dt}
              openOc={openOc}
              openMr={openMr}
            />
          )}

          {tab === "report" && (
            <ReportTab
              detail={detail}
              money={money}
              dt={dt}
              accr={accr}
              rows={sortedRows}
              periodLabel={periodLabel(p.year, p.month)}
            />
          )}
          {tab === "property" && (
            <div className="forms-grid">
              <div className="subcard">
                <h4>Редагувати об&apos;єкт</h4>
                <In
                  tip="Адреса об'єкта"
                  placeholder="Адреса"
                  value={ap.address}
                  onChange={(e) => setAp((s) => ({ ...s, address: e.target.value }))}
                />
                <button onClick={saveAp}>Зберегти</button>
                <button className="danger" onClick={delAp}>
                  Видалити
                </button>
              </div>
              <div className="subcard full-row">
                <h4>Встановлені лічильники</h4>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Послуга</th>
                        <th>Тип</th>
                        <th>Серійний номер</th>
                        <th>Початковий показник</th>
                        <th>Дата встановлення</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {meters.length === 0 && (
                        <tr>
                          <td colSpan={6}>
                            <span className="helper">Лічильників ще немає.</span>
                          </td>
                        </tr>
                      )}
                      {meters.map((meter) => (
                        <tr key={meter.id}>
                          <td>{meter.service_name}</td>
                          <td>{meter.utility_type}</td>
                          <td>{meter.serial_number || "—"}</td>
                          <td>{meter.initial_reading ?? "0"}</td>
                          <td>{meter.installed_at || "—"}</td>
                          <td>
                            <div className="row-actions">
                              <button className="secondary icon-btn" onClick={() => startEditMeter(meter)}>
                                ✎
                              </button>
                              <button className="danger icon-btn" onClick={() => askDeleteMeter(meter)}>
                                🗑
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="forms-grid top-gap">
                  <In
                    tip="Послуга лічильника"
                    placeholder="Назва послуги"
                    value={meterForm.service_name}
                    onChange={(e) => setMeterForm((s) => ({ ...s, service_name: e.target.value }))}
                  />
                  <Se
                    tip="Тип лічильника"
                    value={meterForm.utility_type}
                    onChange={(e) =>
                      setMeterForm((s) => ({
                        ...s,
                        utility_type: e.target.value as MeterUpsertForm["utility_type"],
                      }))
                    }
                  >
                    <option value="electricity">Електроенергія</option>
                    <option value="water">Вода</option>
                    <option value="gas">Газ</option>
                    <option value="heating">Опалення</option>
                    <option value="sewage">Водовідведення</option>
                    <option value="internet">Інтернет</option>
                    <option value="other">Інше</option>
                  </Se>
                  <In
                    tip="Серійний номер"
                    placeholder="Серійний номер (необов'язково)"
                    value={meterForm.serial_number}
                    onChange={(e) => setMeterForm((s) => ({ ...s, serial_number: e.target.value }))}
                  />
                  <In
                    tip="Початковий показник"
                    placeholder="0"
                    value={meterForm.initial_reading}
                    onChange={(e) => setMeterForm((s) => ({ ...s, initial_reading: e.target.value }))}
                  />
                  <In
                    tip="Дата встановлення"
                    type="date"
                    value={meterForm.installed_at}
                    onChange={(e) => setMeterForm((s) => ({ ...s, installed_at: e.target.value }))}
                  />
                </div>
                <div className="row-actions">
                  <button onClick={submitMeter}>
                    {editingMeterId ? "Зберегти лічильник" : "Додати лічильник"}
                  </button>
                  {editingMeterId && (
                    <button className="secondary" onClick={resetMeterForm}>
                      Скасувати
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
