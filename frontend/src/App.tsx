import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { asInt, dt, formatPhone, money, periodLabel } from "@/shared/utils/format";
import { calculateAccrualTotal, calculatePortfolioTotals } from "@/shared/utils/billing-selectors";
import { useBillingActions } from "@/features/calculation/hooks/use-billing-actions";
import { useRowEditing } from "@/features/calculation/hooks/use-row-editing";
import { useTenantActions } from "@/features/tenants/hooks/use-tenant-actions";
import { useTenantFormState } from "@/features/tenants/hooks/use-tenant-form-state";
import { useOwnerActions } from "@/features/expenses/hooks/use-owner-actions";
import { useOwnerFormState } from "@/features/expenses/hooks/use-owner-form-state";
import { useSession } from "@/shared/hooks/use-session";
import { usePeriod } from "@/shared/hooks/use-period";
import { useAppStore } from "@/shared/store/app-store";
import { LoginScreen } from "@/features/auth/components/LoginScreen";
import { AdminHeader } from "@/features/layout/components/AdminHeader";
import { useUiState } from "@/features/layout/hooks/use-ui-state";
import { useModalState } from "@/features/layout/hooks/use-modal-state";
import { useDashboardData } from "@/features/dashboard/hooks/use-dashboard-data";
import { useDashboardStateSync } from "@/features/dashboard/hooks/use-dashboard-state-sync";
import { useSortedRows } from "@/features/calculation/hooks/use-sorted-rows";
import { usePropertyActions } from "@/features/properties/hooks/use-property-actions";
import { useMeterActions } from "@/features/properties/hooks/use-meter-actions";
import { PropertyDrawer } from "@/features/properties/components/PropertyDrawer";
import { DashboardContent } from "@/features/layout/components/DashboardContent";
import { AppModals } from "@/features/layout/components/AppModals";
import { useAdminUserActions } from "@/features/auth/hooks/use-admin-user-actions";
import { useTariffActions } from "@/features/tariffs/hooks/use-tariff-actions";
import { useServiceLedgerActions } from "@/features/tariffs/hooks/use-service-ledger-actions";
import { useTariffFormState } from "@/features/tariffs/hooks/use-tariff-form-state";
import { useAuthActions } from "@/features/auth/hooks/use-auth-actions";
import type { BillingHistoryItem, MeterUpsertForm } from "@/shared/api/types";

type SelectedApartment = {
  apartment_id: number;
  code?: string;
  address?: string;
  total_balance?: string | number;
};
type DetailLike = {
  rows?: Array<{
    service_name: string;
    meter_id: number | null;
    previous_reading: string | null;
    current_reading: string | null;
    difference: string | null;
    unit_name: string;
    unit_price: string;
    amount: string;
    can_edit_previous?: boolean;
  }>;
  calc_locked?: boolean;
};

export default function App() {
  const queryClient = useQueryClient();
  const { token: tok, saveToken, clearToken, sessionError, setSessionError } = useSession();
  const { period: p, shiftPeriod } = usePeriod();
  const selectedApartmentId = useAppStore((s) => s.selectedApartmentId);
  const setSelectedApartmentId = useAppStore((s) => s.setSelectedApartmentId);
  const {
    cred,
    setCred,
    boot,
    setBoot,
    tab,
    setTab,
    err,
    setErr,
    drawer,
    setDrawer,
    addProp,
    setAddProp,
    pay,
    setPay,
    pwd,
    setPwd,
  } = useUiState();
  const {
    payModal,
    setPayModal,
    pwdModal,
    setPwdModal,
    adminsModal,
    setAdminsModal,
    toasts,
    setToasts,
    confirm,
    setConfirm,
    pushToast,
  } = useModalState();
  const [sel, setSel] = useState<SelectedApartment | null>(null);
  const [detail, setDetail] = useState<DetailLike | null>(null);
  const [history, setHistory] = useState<BillingHistoryItem[]>([]);
  const { tar, setTar, newTar, setNewTar, tModal, setTModal, tForm, setTForm } =
    useTariffFormState();
  const {
    oc,
    setOc,
    mr,
    setMr,
    own,
    setOwn,
    mnt,
    setMnt,
    ocModal,
    setOcModal,
    ocForm,
    setOcForm,
    mrModal,
    setMrModal,
    mrForm,
    setMrForm,
  } = useOwnerFormState();
  const {
    tenant,
    setTenant,
    tenants,
    setTenants,
    newTenant,
    setNewTenant,
    assignExisting,
    setAssignExisting,
  } = useTenantFormState();
  const [ap, setAp] = useState({ address: "" });
  const [meterForm, setMeterForm] = useState<MeterUpsertForm>({
    service_name: "",
    utility_type: "other",
    serial_number: "",
    initial_reading: "",
    installed_at: "",
  });
  const [editingMeterId, setEditingMeterId] = useState<number | null>(null);
  const confirmActionRef = useRef<null | (() => void | Promise<void>)>(null);
  const {
    apartmentsQuery,
    detailBundleQuery,
    adminUsersQuery,
    apartments: props,
    invalidateApartmentQueries,
    reload,
  } = useDashboardData({
    tok,
    sel,
    setSel,
    period: p,
    selectedApartmentId,
    setSelectedApartmentId,
    adminsModal,
    setErr,
    pushToast,
  });
  const { sortedRows, toggleSort, sortIcon, resetSortDefault } = useSortedRows(detail?.rows || []);
  const meters = detailBundleQuery.data?.meters || [];

  const totals = useMemo(() => calculatePortfolioTotals(props), [props]);
  const accr = useMemo(() => calculateAccrualTotal(detail?.rows || []), [detail?.rows]);

  useEffect(() => { if (sessionError) setErr(sessionError); }, [sessionError]);
  useEffect(() => {
    setEditingMeterId(null);
    setMeterForm({
      service_name: "",
      utility_type: "other",
      serial_number: "",
      initial_reading: "",
      installed_at: "",
    });
  }, [sel?.apartment_id]);

  const confirmRun = (
    title: string,
    message: string,
    action: () => void | Promise<void>,
  ) => {
    confirmActionRef.current = action;
    setConfirm({ open: true, title, message });
  };
  const { login, out, changePassword } = useAuthActions({
    tok,
    cred,
    pwd,
    setErr,
    setBoot,
    saveToken,
    clearToken,
    setSel,
    setSessionError,
    setPwdModal,
    setPwd,
    pushToast,
  });

  const { createAdminUserMutation, updateAdminUserMutation } = useAdminUserActions({
    tok,
    queryClient,
    pushToast,
  });

  useDashboardStateSync({
    detailBundleData: detailBundleQuery.data,
    setDetail,
    setHistory,
    setTar,
    setOc,
    setMr,
    setTenants,
    setAp,
    setPay,
    setTenant,
    period: p,
    setNewTar,
    setNewTenant,
    setAssignExisting,
  });
  const { editSrv, setEditSrv, draft, setDraft, editRef, start, changed } = useRowEditing({
    asInt,
  });

  const { savePay, saveRow, recalcMonth, toggleLockMonth } = useBillingActions({
    tok,
    apartmentId: sel?.apartment_id,
    period: p,
    pay,
    tar,
    draft,
    setEditSrv,
    setDraft,
    setPayModal,
    pushToast,
    reload,
    invalidateApartmentQueries,
    calcLocked: detail?.calc_locked,
  });
  const { saveTenant, assignTenant, createTenantAndAssign } = useTenantActions({
    tok,
    detail,
    sel,
    period: p,
    tenant,
    assignExisting,
    newTenant,
    setErr,
    setNewTenant,
    pushToast,
    reload,
  });
  const { createTariff, openT, saveT, delT } = useTariffActions({
    tok,
    sel,
    period: p,
    newTar,
    setNewTar,
    tModal,
    setTModal,
    tForm,
    setTForm,
    pushToast,
    confirmRun,
    invalidateApartmentQueries,
    reload,
  });
  const {
    fixedServiceNames,
    selectedService: selectedLedgerService,
    setSelectedService: setSelectedLedgerService,
    ledgerForm,
    setLedgerForm,
    ledgerHistory,
    ledgerHistoryLoading,
    saveServiceLedgerMonth,
  } = useServiceLedgerActions({
    tok,
    apartmentId: sel?.apartment_id,
    period: p,
    tariffs: tar,
    pushToast,
  });
  const { addOwner, addMaint, saveOc, delOc, saveMr, delMr, openOc, openMr } = useOwnerActions({
    tok,
    apartmentId: sel?.apartment_id,
    period: p,
    own,
    mnt,
    ocModal,
    ocForm,
    mrModal,
    mrForm,
    setOcModal,
    setOcForm,
    setMrModal,
    setMrForm,
    pushToast,
    confirmRun,
    reload,
  });
  const { saveAp, createAp, delAp } = usePropertyActions({
    tok,
    sel,
    ap,
    setSel,
    setDrawer,
    setAddProp,
    apartmentsQuery,
    pushToast,
    confirmRun,
    queryClient,
    reload,
  });
  const { submitMeter, startEditMeter, askDeleteMeter, resetMeterForm } = useMeterActions({
    tok,
    apartmentId: sel?.apartment_id,
    meterForm,
    editingMeterId,
    setMeterForm,
    setEditingMeterId,
    pushToast,
    confirmRun,
    reload,
  });

  if (!tok) return <LoginScreen cred={cred} setCred={setCred} login={login} boot={boot} err={err} />;

  return (
    <div className="app-shell">
      <AdminHeader
        boot={boot}
        onOpenDrawer={() => setDrawer(true)}
        onOpenAdmins={() => setAdminsModal(true)}
        onOpenChangePassword={() => setPwdModal(true)}
        onLogout={out}
      />
      <PropertyDrawer
        drawer={drawer}
        setDrawer={setDrawer}
        addProp={addProp}
        setAddProp={setAddProp}
        apartmentsQuery={apartmentsQuery}
        ap={ap}
        setAp={setAp}
        createAp={createAp}
        totals={totals}
        money={money}
        props={props}
        sel={sel}
        setSel={setSel}
      />
      <DashboardContent
        apartmentsQuery={apartmentsQuery}
        detailBundleQuery={detailBundleQuery}
        sel={sel}
        detail={detail}
        shiftPeriod={shiftPeriod}
        periodLabel={periodLabel}
        p={p}
        money={money}
        tab={tab}
        setTab={setTab}
        dt={dt}
        setPayModal={setPayModal}
        toggleSort={toggleSort}
        sortIcon={sortIcon}
        sortedRows={sortedRows}
        editSrv={editSrv}
        editRef={editRef}
        asInt={asInt}
        start={start}
        setEditSrv={setEditSrv}
        setDraft={setDraft}
        draft={draft}
        changed={changed}
        saveRow={saveRow}
        recalcMonth={recalcMonth}
        toggleLockMonth={toggleLockMonth}
        resetSortDefault={resetSortDefault}
        accr={accr}
        history={history}
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
        tar={tar}
        openT={openT}
        newTar={newTar}
        setNewTar={setNewTar}
        createTariff={createTariff}
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
        saveAp={saveAp}
        delAp={delAp}
        ap={ap}
        setAp={setAp}
        meters={meters}
        fixedServiceNames={fixedServiceNames}
        selectedLedgerService={selectedLedgerService}
        setSelectedLedgerService={setSelectedLedgerService}
        ledgerForm={ledgerForm}
        setLedgerForm={setLedgerForm}
        saveServiceLedgerMonth={saveServiceLedgerMonth}
        ledgerHistory={ledgerHistory}
        ledgerHistoryLoading={ledgerHistoryLoading}
        meterForm={meterForm}
        setMeterForm={setMeterForm}
        editingMeterId={editingMeterId}
        submitMeter={submitMeter}
        startEditMeter={startEditMeter}
        askDeleteMeter={askDeleteMeter}
        resetMeterForm={resetMeterForm}
      />
      <AppModals
        payModal={payModal}
        setPayModal={setPayModal}
        pay={pay}
        savePay={savePay}
        pwdModal={pwdModal}
        setPwdModal={setPwdModal}
        pwd={pwd}
        changePassword={changePassword}
        adminsModal={adminsModal}
        setAdminsModal={setAdminsModal}
        adminUsersQuery={adminUsersQuery}
        createAdminUserMutation={createAdminUserMutation}
        updateAdminUserMutation={updateAdminUserMutation}
        tModal={tModal}
        tForm={tForm}
        saveT={saveT}
        delT={delT}
        meters={meters}
        tariffServiceNames={tar.map((x: any) => x.service_name).filter(Boolean)}
        setTModal={setTModal}
        setTFormModal={setTForm}
        ocModal={ocModal}
        ocForm={ocForm}
        setOcModal={setOcModal}
        setOcForm={setOcForm}
        saveOc={saveOc}
        delOc={delOc}
        mrModal={mrModal}
        mrForm={mrForm}
        setMrModal={setMrModal}
        setMrForm={setMrForm}
        saveMr={saveMr}
        delMr={delMr}
        confirm={confirm}
        setConfirm={setConfirm}
        confirmActionRef={confirmActionRef}
        toasts={toasts}
        setToasts={setToasts}
      />
    </div>
  );
}
