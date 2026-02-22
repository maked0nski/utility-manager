import { In, Se, Ta } from "@/shared/ui/form-controls";
import type { Dispatch, SetStateAction } from "react";

type TenantForm = {
  full_name: string;
  primary_phone: string;
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

type NewTenantForm = {
  full_name: string;
  phone: string;
  access_code: string;
  start_date: string;
  rent_amount: string;
  rent_currency: "UAH" | "USD" | "EUR";
  bank_statement_name: string;
};

type AssignExistingForm = { tenant_id: string; start_date: string };

export function TenantTab({
  detail,
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
}: {
  detail: { tenant?: { id: number } | null };
  newTenant: NewTenantForm;
  setNewTenant: Dispatch<SetStateAction<NewTenantForm>>;
  createTenantAndAssign: () => Promise<void>;
  assignExisting: AssignExistingForm;
  setAssignExisting: Dispatch<SetStateAction<AssignExistingForm>>;
  tenants: Array<{ id: number; full_name: string }>;
  assignTenant: () => Promise<void>;
  tenant: TenantForm;
  setTenant: Dispatch<SetStateAction<TenantForm>>;
  formatPhone: (value: unknown) => string;
  saveTenant: () => Promise<void>;
}) {
  return (
    <div className="forms-grid">
      {!detail.tenant && (
        <div className="subcard">
          <h4>Створити орендаря і призначити</h4>
          <In tip="ПІБ нового орендаря" placeholder="ПІБ" value={newTenant.full_name} onChange={(e) => setNewTenant((s) => ({ ...s, full_name: e.target.value }))} />
          <In tip="Основний телефон" placeholder="Телефон" value={newTenant.phone} onChange={(e) => setNewTenant((s) => ({ ...s, phone: e.target.value }))} />
          <In tip="Код доступу орендаря (необов'язково)" placeholder="Код доступу (необов'язково)" value={newTenant.access_code} onChange={(e) => setNewTenant((s) => ({ ...s, access_code: e.target.value }))} />
          <In tip="Ім'я у банківській виписці" placeholder="Ім'я у виписці" value={newTenant.bank_statement_name} onChange={(e) => setNewTenant((s) => ({ ...s, bank_statement_name: e.target.value }))} />
          <In tip="Щомісячна вартість оренди" placeholder="Сума оренди" value={newTenant.rent_amount} onChange={(e) => setNewTenant((s) => ({ ...s, rent_amount: e.target.value }))} />
          <Se tip="Валюта оренди" value={newTenant.rent_currency} onChange={(e) => setNewTenant((s) => ({ ...s, rent_currency: e.target.value }))}>
            <option value="UAH">UAH</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </Se>
          <In tip="Дата початку оренди/призначення" type="date" value={newTenant.start_date} onChange={(e) => setNewTenant((s) => ({ ...s, start_date: e.target.value }))} />
          <button onClick={createTenantAndAssign}>Створити і призначити</button>
        </div>
      )}
      <div className="subcard">
        <h4>Призначити існуючого орендаря</h4>
        <Se tip="Оберіть орендаря зі списку" value={assignExisting.tenant_id} onChange={(e) => setAssignExisting((s) => ({ ...s, tenant_id: e.target.value }))}>
          <option value="">Оберіть орендаря</option>
          {tenants.map((t) => (
            <option key={t.id} value={t.id}>
              {t.full_name}
            </option>
          ))}
        </Se>
        <In tip="Дата, з якої орендар починає оренду" type="date" value={assignExisting.start_date} onChange={(e) => setAssignExisting((s) => ({ ...s, start_date: e.target.value }))} />
        <button onClick={assignTenant}>Призначити орендаря</button>
      </div>
      {detail.tenant && (
        <div className="subcard full-row tenant-grid">
          <h4>Дані орендаря</h4>
          <In tip="Повне ПІБ орендаря" placeholder="ПІБ" value={tenant.full_name} onChange={(e) => setTenant((s) => ({ ...s, full_name: e.target.value }))} />
          <In tip="Основний телефон орендаря" placeholder="Основний телефон" value={tenant.primary_phone} onChange={(e) => setTenant((s) => ({ ...s, primary_phone: e.target.value }))} onBlur={() => setTenant((s) => ({ ...s, primary_phone: formatPhone(s.primary_phone) }))} />
          <In tip="Додаткові телефони через кому" placeholder="Додаткові телефони" value={tenant.phones} onChange={(e) => setTenant((s) => ({ ...s, phones: e.target.value }))} onBlur={() => setTenant((s) => ({ ...s, phones: s.phones.split(",").map((x) => formatPhone(x.trim())).filter(Boolean).join(", ") }))} />
          <In tip="Ім'я у банківській виписці" placeholder="Ім'я у виписці" value={tenant.bank_statement_name} onChange={(e) => setTenant((s) => ({ ...s, bank_statement_name: e.target.value }))} />
          <In tip="Щомісячна вартість оренди" placeholder="Сума оренди" value={tenant.rent_amount} onChange={(e) => setTenant((s) => ({ ...s, rent_amount: e.target.value }))} />
          <Se tip="Валюта оренди" value={tenant.rent_currency} onChange={(e) => setTenant((s) => ({ ...s, rent_currency: e.target.value }))}>
            <option value="UAH">UAH</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </Se>
          <In tip="Номер паспорта або ID" placeholder="Номер паспорта" value={tenant.passport_number} onChange={(e) => setTenant((s) => ({ ...s, passport_number: e.target.value }))} />
          <In tip="Орган, що видав документ" placeholder="Ким виданий" value={tenant.passport_issued_by} onChange={(e) => setTenant((s) => ({ ...s, passport_issued_by: e.target.value }))} />
          <In tip="Дата видачі документа" type="date" value={tenant.passport_issue_date} onChange={(e) => setTenant((s) => ({ ...s, passport_issue_date: e.target.value }))} />
          <In tip="Дата завершення документа" type="date" value={tenant.passport_expiry_date} onChange={(e) => setTenant((s) => ({ ...s, passport_expiry_date: e.target.value }))} />
          <Ta tip="Контакти: Ім'я|Зв'язок|Телефон|Примітка" rows={4} placeholder="Контакти: Ім'я|Зв'язок|Телефон|Примітка" value={tenant.contacts_text} onChange={(e) => setTenant((s) => ({ ...s, contacts_text: e.target.value }))} />
          <button onClick={saveTenant}>Зберегти</button>
        </div>
      )}
    </div>
  );
}
