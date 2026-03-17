import { In, Se } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import type { Dispatch, SetStateAction } from "react";
import { useState } from "react";

type NewTenantForm = {
  full_name: string;
  phone: string;
  email: string;
  access_code: string;
  start_date: string;
  rent_amount: string;
  rent_currency: "UAH" | "USD" | "EUR";
  bank_statement_name: string;
};

type AssignExistingForm = { tenant_id: string; start_date: string };

type TenancyHistoryItem = {
  id: number;
  start_date: string;
  end_date: string | null;
  tenant: { id: number; full_name: string } | null;
};

export function TenantTab({
  detail,
  tenant,
  setTenant,
  tenancies,
  newTenant,
  setNewTenant,
  createTenantAndAssign,
  assignExisting,
  setAssignExisting,
  tenants,
  assignTenant,
  tenancyEndDate,
  setTenancyEndDate,
  saveTenant,
  endTenancy,
  dt,
}: {
  detail: { tenant?: { id: number; full_name: string } | null };
  tenant: {
    full_name: string;
    primary_phone: string;
    email: string;
    phones: string;
    contacts_text: string;
    bank_statement_name: string;
    rent_amount: string;
    rent_currency: "UAH" | "USD" | "EUR";
    passport_number: string;
    passport_issued_by: string;
    passport_issue_date: string;
    passport_expiry_date: string;
  };
  setTenant: Dispatch<
    SetStateAction<{
      full_name: string;
      primary_phone: string;
      email: string;
      phones: string;
      contacts_text: string;
      bank_statement_name: string;
      rent_amount: string;
      rent_currency: "UAH" | "USD" | "EUR";
      passport_number: string;
      passport_issued_by: string;
      passport_issue_date: string;
      passport_expiry_date: string;
    }>
  >;
  tenancies: TenancyHistoryItem[];
  newTenant: NewTenantForm;
  setNewTenant: Dispatch<SetStateAction<NewTenantForm>>;
  createTenantAndAssign: () => Promise<void>;
  assignExisting: AssignExistingForm;
  setAssignExisting: Dispatch<SetStateAction<AssignExistingForm>>;
  tenants: Array<{ id: number; full_name: string }>;
  assignTenant: () => Promise<void>;
  tenancyEndDate: string;
  setTenancyEndDate: Dispatch<SetStateAction<string>>;
  saveTenant: () => Promise<void>;
  endTenancy: (tenancyId: number, endDate: string) => Promise<void>;
  dt: (x: string | Date | null | undefined) => string;
}) {
  const activeTenancy = tenancies.find((x) => x.end_date === null);
  const [tenancyModalOpen, setTenancyModalOpen] = useState(false);
  const hasActiveTenancy = Boolean(activeTenancy && detail.tenant);

  return (
    <div className="forms-grid tab-pane-grid">
      <div className="subcard full-row">
        <div className="title-row">
          <h4>Історія оренди об&apos;єкта</h4>
          <button onClick={() => setTenancyModalOpen(true)}>
            {hasActiveTenancy ? "Редагувати оренду" : "Призначити орендаря"}
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Орендар</th>
                <th>Початок</th>
                <th>Завершення</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {tenancies.length === 0 && (
                <tr>
                  <td colSpan={4}>
                    <span className="helper">Історії оренди ще немає.</span>
                  </td>
                </tr>
              )}
              {tenancies.map((tenancy) => (
                <tr key={tenancy.id}>
                  <td>{tenancy.tenant?.full_name || "—"}</td>
                  <td>{dt(tenancy.start_date)}</td>
                  <td>{tenancy.end_date ? dt(tenancy.end_date) : "—"}</td>
                  <td>{tenancy.end_date ? "Завершено" : "Активна"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {tenancyModalOpen && (
        <Modal
          title={hasActiveTenancy ? "Редагувати оренду" : "Призначити орендаря"}
          onClose={() => setTenancyModalOpen(false)}
        >
          {!hasActiveTenancy ? (
            <div className="forms-grid tab-pane-grid">
              <div className="subcard">
                <h4>Створити нового орендаря і здати об&apos;єкт</h4>
                <div className="forms-grid compact-grid">
                  <In tip="ПІБ орендаря" value={newTenant.full_name} onChange={(e) => setNewTenant((s) => ({ ...s, full_name: e.target.value }))} />
                  <In tip="Телефон" value={newTenant.phone} onChange={(e) => setNewTenant((s) => ({ ...s, phone: e.target.value }))} />
                  <In tip="Дата початку оренди" type="date" value={newTenant.start_date} onChange={(e) => setNewTenant((s) => ({ ...s, start_date: e.target.value }))} />
                  <In tip="Email (логін орендаря)" value={newTenant.email} onChange={(e) => setNewTenant((s) => ({ ...s, email: e.target.value }))} />
                  <In tip="Код доступу" value={newTenant.access_code} onChange={(e) => setNewTenant((s) => ({ ...s, access_code: e.target.value }))} />
                  <In tip="Назва в банківській виписці" value={newTenant.bank_statement_name} onChange={(e) => setNewTenant((s) => ({ ...s, bank_statement_name: e.target.value }))} />
                  <In tip="Оренда за місяць" value={newTenant.rent_amount} onChange={(e) => setNewTenant((s) => ({ ...s, rent_amount: e.target.value }))} />
                  <Se tip="Валюта оренди" value={newTenant.rent_currency} onChange={(e) => setNewTenant((s) => ({ ...s, rent_currency: e.target.value as "UAH" | "USD" | "EUR" }))}>
                    <option value="UAH">UAH</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </Se>
                </div>
                <div className="row-actions">
                  <button
                    onClick={async () => {
                      await createTenantAndAssign();
                      setTenancyModalOpen(false);
                    }}
                  >
                    Створити і здати в оренду
                  </button>
                </div>
              </div>
              <div className="subcard">
                <h4>Обрати вже створеного орендаря</h4>
                <div className="forms-grid compact-grid">
                  <Se tip="Орендар" value={assignExisting.tenant_id} onChange={(e) => setAssignExisting((s) => ({ ...s, tenant_id: e.target.value }))}>
                    <option value="">Оберіть орендаря</option>
                    {tenants.map((tenantItem) => (
                      <option key={tenantItem.id} value={tenantItem.id}>
                        {tenantItem.full_name}
                      </option>
                    ))}
                  </Se>
                  <In tip="Дата початку оренди" type="date" value={assignExisting.start_date} onChange={(e) => setAssignExisting((s) => ({ ...s, start_date: e.target.value }))} />
                </div>
                <div className="row-actions">
                  <button
                    onClick={async () => {
                      await assignTenant();
                      setTenancyModalOpen(false);
                    }}
                  >
                    Призначити орендаря
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="tenant-grid">
              <p className="helper">
                {detail.tenant?.full_name} • з {dt(activeTenancy?.start_date)}
              </p>
              <div className="forms-grid compact-grid">
                <In tip="ПІБ орендаря" value={tenant.full_name} onChange={(e) => setTenant((s) => ({ ...s, full_name: e.target.value }))} />
                <In tip="Телефон" value={tenant.primary_phone} onChange={(e) => setTenant((s) => ({ ...s, primary_phone: e.target.value }))} />
                <In tip="Email (логін орендаря)" value={tenant.email} onChange={(e) => setTenant((s) => ({ ...s, email: e.target.value }))} />
                <In tip="Назва в банківській виписці" value={tenant.bank_statement_name} onChange={(e) => setTenant((s) => ({ ...s, bank_statement_name: e.target.value }))} />
                <In tip="Оренда за місяць" type="number" min="0" step="0.01" value={tenant.rent_amount} onChange={(e) => setTenant((s) => ({ ...s, rent_amount: e.target.value }))} />
                <Se tip="Валюта оренди" value={tenant.rent_currency} onChange={(e) => setTenant((s) => ({ ...s, rent_currency: e.target.value as "UAH" | "USD" | "EUR" }))}>
                  <option value="UAH">UAH</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </Se>
                <In tip="Дата припинення оренди" type="date" value={tenancyEndDate} onChange={(e) => setTenancyEndDate(e.target.value)} />
              </div>
              <div className="row-actions">
                <button
                  onClick={async () => {
                    await saveTenant();
                    setTenancyModalOpen(false);
                  }}
                >
                  Зберегти зміни
                </button>
                <button
                  className="danger"
                  onClick={async () => {
                    if (!activeTenancy) return;
                    await endTenancy(activeTenancy.id, tenancyEndDate);
                    setTenancyModalOpen(false);
                  }}
                >
                  Припинити оренду
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
