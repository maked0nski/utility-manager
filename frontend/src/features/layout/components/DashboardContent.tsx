import { useRef } from "react";
import { CalculationTab } from "@/features/calculation/components/CalculationTab";
import { PaymentsTab } from "@/features/payments/components/PaymentsTab";
import { TenantTab } from "@/features/tenants/components/TenantTab";
import { AutomationsTab } from "@/features/tariffs/components/AutomationsTab";
import { OwnerCostsTab } from "@/features/expenses/components/OwnerCostsTab";
import { ReportTab } from "@/features/report/components/ReportTab";
import { ObjectServicesTab } from "@/features/services/components/ObjectServicesTab";
import { PropertyTab } from "@/features/properties/components/PropertyTab";
import { useDashboardContext } from "@/features/layout/context/dashboard-context";

export function DashboardContent() {
  const {
    apartmentsQuery,
    detailBundleQuery,
    sel,
    detail,
    shiftPeriod,
    onPickPeriod,
    maxPeriodInput,
    periodLabel,
    p,
    money,
    tab,
    setTab,
    dt,
    payments,
    prepareBillingStatement,
    sendBillingStatement,
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
    confirmMonth,
    reopenMonth,
    resetSortDefault,
    accr,
    history,
    openBatchReadingModal,
    batchReadingMeterOptions,
    batchReadingModalOpen,
    closeBatchReadingModal,
    batchReadingMetas,
    batchReadingDraft,
    setBatchReadingDraft,
    saveBatchReadings,
    batchReadingSaving,
    newTenant,
    setNewTenant,
    createTenantAndAssign,
    tenant,
    setTenant,
    assignExisting,
    setAssignExisting,
    tenants,
    assignTenant,
    tenancies,
    tenancyEndDate,
    setTenancyEndDate,
    saveTenant,
    endTenancy,
    createPayment,
    updatePayment,
    deletePayment,
    meters,
    equipment,
    equipmentForm,
    setEquipmentForm,
    submitEquipment,
    startEditEquipment,
    askDeleteEquipment,
    resetEquipmentForm,
    automations,
    automationTemplates,
    automationsLoading,
    saveAutomation,
    runAutomation,
    createAutomationTemplate,
    updateAutomationTemplate,
    deleteAutomationTemplate,
    connectTemplateToApartment,
    disconnectTemplateFromApartment,
    fetchAutomationLogs,
    revealAutomationPassword,
    runAutomationCycle,
    previewAutomationCycle,
    automationCycleRuns,
    fetchAutomationCycleRunDetail,
    selectedApartmentId,
    providers,
    meterTypes,
    serviceCatalog,
    serviceConnections,
    serviceConnectionsLoading,
    createServiceConnection,
    updateServiceConnection,
    deleteServiceConnection,
    electricityPlanForm,
    setElectricityPlanForm,
    electricityMeters,
    saveElectricityPlan,
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
    submitMeter,
    startEditMeter,
    askDeleteMeter,
    resetMeterForm,
    replacingMeterId,
    replacementForm,
    setReplacementForm,
    startReplaceMeter,
    submitReplacement,
    resetReplacementForm,
  } = useDashboardContext();

  const periodPickerRef = useRef<HTMLInputElement | null>(null);

  const periodEndIso = `${String(p.year).padStart(4, "0")}-${String(p.month).padStart(2, "0")}-${String(
    new Date(p.year, p.month, 0).getDate(),
  ).padStart(2, "0")}`;
  const latestPaymentInPeriod = [...payments]
    .filter((row) => {
      const paidAt = String(row?.paid_at || "");
      return paidAt && paidAt <= periodEndIso;
    })
    .sort((a, b) => {
    const dateCmp = String(b.paid_at || "").localeCompare(String(a.paid_at || ""));
    if (dateCmp !== 0) return dateCmp;
    return b.id - a.id;
    })[0] || null;
  const liveSummary = detail?.live_balance_summary || null;
  const liveLatestPayment = liveSummary?.latest_payment_date
    ? {
        amount: liveSummary?.latest_payment_amount ?? null,
        paid_at: liveSummary?.latest_payment_date ?? null,
        note: liveSummary?.latest_payment_note ?? null,
      }
    : null;
  const monthSnapshot = detail?.billing_period_summary?.month_snapshot || null;
  const openingBalanceValue = monthSnapshot?.opening_balance ?? detail?.utility_balance?.previous_month_debt ?? 0;
  const monthAccrualValue = monthSnapshot?.month_total ?? detail?.utility_balance?.month_charges ?? 0;
  const monthPaymentsValue = monthSnapshot?.payments_in_month ?? detail?.utility_balance?.month_payments ?? 0;
  const closingBalanceValue = monthSnapshot?.closing_balance ?? detail?.utility_balance?.current_balance ?? 0;
  const liveCurrentBalanceValue = liveSummary?.current_balance ?? detail?.utility_balance?.actual_current_balance ?? closingBalanceValue;

  const openPeriodPicker = () => {
    const picker = periodPickerRef.current;
    if (!picker) return;
    const pickerWithApi = picker as HTMLInputElement & { showPicker?: () => void };
    if (typeof pickerWithApi.showPicker === "function") {
      pickerWithApi.showPicker();
      return;
    }
    picker.click();
  };

  return (
    <section className="card content">
      {apartmentsQuery.isLoading && <p className="helper">Завантаження списку нерухомості...</p>}
      <div className="period-refresh-hint" aria-live="polite">
        {detailBundleQuery.isFetching && sel ? "Оновлення даних обраного періоду..." : " "}
      </div>
      {!sel && <p>Оберіть об&apos;єкт.</p>}
      {sel && detail && (
        <>
          <div className="header-tools dashboard-header">
            <div>
              <h3>{detail.short_address || detail.address}</h3>
              <p className="helper dashboard-subtitle">
                Адреса: <strong>{detail.address || "—"}</strong>
              </p>
              <p className="helper dashboard-subtitle">
                Орендар: <strong>{detail.tenant?.full_name || "відсутній"}</strong>
              </p>
            </div>
            <div className="period-nav">
              <input
                ref={periodPickerRef}
                className="period-picker-input"
                type="month"
                value={`${p.year}-${String(p.month).padStart(2, "0")}`}
                max={maxPeriodInput}
                onChange={(e) => {
                  const value = e.target.value;
                  if (!value) return;
                  const [yearRaw, monthRaw] = value.split("-");
                  const year = Number(yearRaw);
                  const month = Number(monthRaw);
                  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) return;
                  onPickPeriod(year, month);
                }}
              />
              <button onClick={() => shiftPeriod(-1)}>◀</button>
              <button type="button" className="period-label-button" onClick={openPeriodPicker}>
                {periodLabel(p.year, p.month)}
              </button>
              <button onClick={() => shiftPeriod(1)}>▶</button>
              <span className={`status-pill ${detail.calc_locked ? "ok" : "draft"}`}>
                {detail.calc_locked ? "Підтверджено" : "Чернетка"}
              </span>
            </div>
          </div>
          <div className="summary-grid dashboard-kpi-strip">
            <div className="metric">
              <div className="label">Борг на початок місяця</div>
              <div className="value">{money(openingBalanceValue)}</div>
            </div>
            <div className="metric">
              <div className="label">Нараховано за місяць</div>
              <div className="value">{money(monthAccrualValue)}</div>
            </div>
            <div className="metric">
              <div className="label">Оплачено в місяці</div>
              <div className="value">{money(monthPaymentsValue)}</div>
              <small>{`Станом на ${periodLabel(p.year, p.month)}`}</small>
            </div>
            <div className="metric">
              <div className="label">Борг на кінець місяця</div>
              <div className="value">{money(closingBalanceValue)}</div>
              <small>
                {latestPaymentInPeriod
                  ? `Остання оплата в межах місяця: ${money(latestPaymentInPeriod.amount)} • ${dt(latestPaymentInPeriod.paid_at)}`
                  : "Оплат у межах цього місяця ще немає"}
              </small>
            </div>
          </div>
          <p className="helper dashboard-live-strip-label">
            Стан на сьогодні (може відрізнятися від показників вище, якщо обраний місяць — не поточний):
          </p>
          <div className="summary-grid dashboard-live-strip">
            <div className="metric">
              <div className="label">Поточний баланс на сьогодні</div>
              <div className="value">{money(liveCurrentBalanceValue)}</div>
              <small>Живий стан взаєморозрахунків з урахуванням усіх отриманих оплат на сьогодні.</small>
            </div>
            <div className="metric">
              <div className="label">Остання отримана оплата</div>
              <div className="value">{liveLatestPayment ? money(liveLatestPayment.amount) : "—"}</div>
              <small>
                {liveLatestPayment
                  ? `${dt(liveLatestPayment.paid_at)}${liveLatestPayment.note ? ` • ${liveLatestPayment.note}` : ""}`
                  : "Ще немає жодної зафіксованої оплати"}
              </small>
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
            <button className={`tab ${tab === "payments" ? "active" : ""}`} onClick={() => setTab("payments")}>
              Оплати
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
              Послуги об&apos;єкта
            </button>
            <button
              className={`tab ${tab === "owner" ? "active" : ""}`}
              onClick={() => setTab("owner")}
            >
              Витрати
            </button>
            <button
              className={`tab ${tab === "automations" ? "active" : ""}`}
              onClick={() => setTab("automations")}
            >
              Автоматизації
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
              confirmMonth={confirmMonth}
              reopenMonth={reopenMonth}
              resetSortDefault={resetSortDefault}
              accr={accr}
              history={history}
              openBatchReadingModal={openBatchReadingModal}
              batchReadingMeterOptions={batchReadingMeterOptions}
              batchReadingModalOpen={batchReadingModalOpen}
              closeBatchReadingModal={closeBatchReadingModal}
              batchReadingMetas={batchReadingMetas}
              batchReadingDraft={batchReadingDraft}
              setBatchReadingDraft={setBatchReadingDraft}
              saveBatchReadings={saveBatchReadings}
              batchReadingSaving={batchReadingSaving}
            />
          )}
          {tab === "payments" && (
            <PaymentsTab
              money={money}
              dt={dt}
              payments={payments}
              loading={!!detailBundleQuery.isFetching}
              tenants={tenants}
              defaultPaidAt={detail.utility_balance?.month_payment_date || ""}
              selectedPeriod={p}
              createPayment={createPayment}
              updatePayment={updatePayment}
              deletePayment={deletePayment}
            />
          )}
          {tab === "tenant" && (
            <TenantTab
              detail={detail}
              newTenant={newTenant}
              setNewTenant={setNewTenant}
              createTenantAndAssign={createTenantAndAssign}
              tenant={tenant}
              setTenant={setTenant}
              assignExisting={assignExisting}
              setAssignExisting={setAssignExisting}
              tenants={tenants}
              assignTenant={assignTenant}
              tenancies={tenancies}
              tenancyEndDate={tenancyEndDate}
              setTenancyEndDate={setTenancyEndDate}
              saveTenant={saveTenant}
              endTenancy={endTenancy}
              dt={dt}
            />
          )}
          {tab === "tariffs" && (
            <ObjectServicesTab
              services={serviceCatalog}
              connections={serviceConnections}
              providers={providers}
              meters={meters}
              loading={!!serviceConnectionsLoading}
              onCreateConnection={createServiceConnection}
              onUpdateConnection={updateServiceConnection}
              onDeleteConnection={deleteServiceConnection}
              electricityPlanForm={electricityPlanForm}
              setElectricityPlanForm={setElectricityPlanForm}
              electricityMeters={electricityMeters}
              saveElectricityPlan={saveElectricityPlan}
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
              openOc={openOc}
              openMr={openMr}
              money={money}
              dt={dt}
            />
          )}
          {tab === "automations" && (
              <AutomationsTab
                automations={automations}
                templates={automationTemplates}
                loading={!!automationsLoading}
                saveAutomation={saveAutomation}
                runAutomation={runAutomation}
                createTemplate={createAutomationTemplate}
                updateTemplate={updateAutomationTemplate}
                deleteTemplate={deleteAutomationTemplate}
                connectTemplateToApartment={connectTemplateToApartment}
                disconnectTemplateFromApartment={disconnectTemplateFromApartment}
                fetchAutomationLogs={fetchAutomationLogs}
                revealAutomationPassword={revealAutomationPassword}
                runAutomationCycle={runAutomationCycle}
                previewAutomationCycle={previewAutomationCycle}
                automationCycleRuns={automationCycleRuns}
                fetchAutomationCycleRunDetail={fetchAutomationCycleRunDetail}
                selectedApartmentId={selectedApartmentId}
                providers={providers}
                onOpenTariffs={() => setTab("tariffs")}
              />
          )}
          {tab === "report" && (
            <ReportTab
              detail={detail}
              money={money}
              dt={dt}
              loading={!!detailBundleQuery.isFetching}
              accr={accr}
              rows={sortedRows}
              periodLabel={periodLabel(p.year, p.month)}
              prepareStatement={prepareBillingStatement}
              sendStatement={sendBillingStatement}
            />
          )}
          {tab === "property" && (
            <PropertyTab
              ap={ap}
              setAp={setAp}
              detail={detail}
              meters={meters}
              equipment={equipment}
              equipmentForm={equipmentForm}
              setEquipmentForm={setEquipmentForm}
              submitEquipment={submitEquipment}
              startEditEquipment={startEditEquipment}
              askDeleteEquipment={askDeleteEquipment}
              resetEquipmentForm={resetEquipmentForm}
              meterForm={meterForm}
              setMeterForm={setMeterForm}
              meterTypes={meterTypes}
              submitMeter={submitMeter}
              startEditMeter={startEditMeter}
              askDeleteMeter={askDeleteMeter}
              resetMeterForm={resetMeterForm}
              replacingMeterId={replacingMeterId}
              replacementForm={replacementForm}
              setReplacementForm={setReplacementForm}
              startReplaceMeter={startReplaceMeter}
              submitReplacement={submitReplacement}
              resetReplacementForm={resetReplacementForm}
              dt={dt}
              saveAp={saveAp}
              delAp={delAp}
              setTab={setTab}
            />
          )}
        </>
      )}
    </section>
  );
}
