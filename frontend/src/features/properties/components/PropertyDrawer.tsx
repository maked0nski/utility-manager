import { useCallback, useState } from "react";
import { In, Se, Ta } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import type { Dispatch, SetStateAction } from "react";
import type { ApartmentProfileForm } from "@/shared/api/types";
import {
  buildApartmentFormFromGooglePlace,
  buildFullPropertyAddress,
  buildPropertyGoogleMapsUrl,
  buildShortPropertyAddress,
} from "@/features/properties/utils/address";
import { PlaceAutocompleteField } from "@/features/properties/components/PlaceAutocompleteField";

type ApartmentItem = {
  apartment_id: number;
  code?: string;
  address?: string;
  short_address?: string;
  total_balance?: string | number;
};

type TenantItem = {
  id: number;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  access_code?: string;
  bank_statement_name?: string | null;
  rent_amount?: string | number | null;
  rent_currency?: "UAH" | "USD" | "EUR";
  passport_number?: string | null;
  passport_issued_by?: string | null;
  passport_issue_date?: string | null;
  passport_expiry_date?: string | null;
  phones?: string[];
  contacts?: Array<{ id?: number; name: string; relation?: string | null; phone?: string | null; note?: string | null }>;
  is_active_now?: boolean;
  portal_enabled?: boolean;
  can_submit_meter_readings?: boolean;
};

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

type TenantEditForm = {
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
  portal_enabled: boolean;
  can_submit_meter_readings: boolean;
  portal_password: string;
};

export function PropertyDrawer({
  drawer,
  setDrawer,
  apartmentsQuery,
  ap,
  setAp,
  createAp,
  totals,
  money,
  props,
  tenants,
  sel,
  setSel,
  newTenant,
  setNewTenant,
  createTenantOnly,
  updateTenantById,
  deleteTenantById,
}: {
  drawer: boolean;
  setDrawer: (v: boolean) => void;
  apartmentsQuery: { refetch: () => Promise<unknown> };
  ap: ApartmentProfileForm;
  setAp: Dispatch<SetStateAction<ApartmentProfileForm>>;
  createAp: () => Promise<void>;
  totals: { utility: number; rent: number; total: number };
  money: (v: unknown) => string;
  props: ApartmentItem[];
  tenants: TenantItem[];
  sel: ApartmentItem | null;
  setSel: (v: ApartmentItem) => void;
  newTenant: NewTenantForm;
  setNewTenant: Dispatch<SetStateAction<NewTenantForm>>;
  createTenantOnly: () => Promise<void>;
  updateTenantById: (tenantId: number, payload: TenantEditForm) => Promise<void>;
  deleteTenantById: (tenantId: number) => Promise<void>;
}) {
  const [propertyExpanded, setPropertyExpanded] = useState(true);
  const [tenantsExpanded, setTenantsExpanded] = useState(true);
  const [addPropertyOpen, setAddPropertyOpen] = useState(false);
  const [addTenantOpen, setAddTenantOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<TenantItem | null>(null);
  const [tenantEditMode, setTenantEditMode] = useState(false);
  const [tenantActionError, setTenantActionError] = useState("");
  const [tenantEditForm, setTenantEditForm] = useState<TenantEditForm>({
    full_name: "",
    primary_phone: "",
    email: "",
    phones: "",
    contacts_text: "",
    bank_statement_name: "",
    rent_amount: "",
    rent_currency: "UAH",
    passport_number: "",
    passport_issued_by: "",
    passport_issue_date: "",
    passport_expiry_date: "",
    portal_enabled: false,
    can_submit_meter_readings: false,
    portal_password: "",
  });

  const sortedTenants = [...tenants].sort((a, b) => {
    const activeA = a.is_active_now ? 0 : 1;
    const activeB = b.is_active_now ? 0 : 1;
    if (activeA !== activeB) return activeA - activeB;
    return (a.full_name || "").localeCompare(b.full_name || "", "uk");
  });

  const openTenantModal = (tenant: TenantItem) => {
    setTenantActionError("");
    setSelectedTenant(tenant);
    setTenantEditMode(false);
    setTenantEditForm({
      full_name: tenant.full_name || "",
      primary_phone: tenant.phone || "",
      email: tenant.email || "",
      phones: (tenant.phones || []).join(", "),
      contacts_text: (tenant.contacts || [])
        .map((c) => `${c.name}|${c.relation || ""}|${c.phone || ""}|${c.note || ""}`)
        .join("\n"),
      bank_statement_name: tenant.bank_statement_name || "",
      rent_amount:
        tenant.rent_amount !== null && tenant.rent_amount !== undefined
          ? String(tenant.rent_amount)
          : "",
      rent_currency: tenant.rent_currency || "UAH",
      passport_number: tenant.passport_number || "",
      passport_issued_by: tenant.passport_issued_by || "",
      passport_issue_date: tenant.passport_issue_date || "",
      passport_expiry_date: tenant.passport_expiry_date || "",
      portal_enabled: Boolean(tenant.portal_enabled),
      can_submit_meter_readings: Boolean(tenant.can_submit_meter_readings),
      portal_password: "",
    });
  };
  const previewShortAddress = buildShortPropertyAddress(ap);
  const previewFullAddress = buildFullPropertyAddress(ap);
  const previewGoogleMapsUrl = buildPropertyGoogleMapsUrl(ap);
  const handlePlaceSelect = useCallback(
    async (place: any) => {
      setAp((current) => ({ ...current, ...buildApartmentFormFromGooglePlace(place, current) }));
    },
    [setAp],
  );
  const resetPropertyForm = () =>
    setAp({
      country: "Україна",
      region: "",
      locality: "",
      street: "",
      house_number: "",
      apartment_number: "",
      postal_code: "",
      address: "",
      short_address: "",
      registered_residents: "1",
      area_m2: "",
      living_area_m2: "",
      entrance: "",
      floor: "",
      room_count: "",
      latitude: "",
      longitude: "",
      google_maps_url: "",
      location_note: "",
      object_notes: "",
    });

  return (
    <>
      {drawer && <div className="drawer-backdrop" onClick={() => setDrawer(false)} />}
      <div className={`property-drawer ${drawer ? "open" : ""}`}>
        <div className="drawer-card">
          <div className="title-row">
            <h3>Нерухомість/орендарі</h3>
            <button className="secondary" onClick={() => apartmentsQuery.refetch()}>
              Оновити
            </button>
          </div>

          <p className="helper">
            Комуналка: {money(totals.utility)} | Оренда: {money(totals.rent)} | Разом: {money(totals.total)}
          </p>

          <div className="drawer-section">
            <div className="title-row">
              <button className="secondary" onClick={() => setPropertyExpanded((s) => !s)}>
                {propertyExpanded ? "▾ Нерухомість" : "▸ Нерухомість"}
              </button>
              <button
                onClick={() => {
                  resetPropertyForm();
                  setAddPropertyOpen(true);
                }}
              >
                Додати
              </button>
            </div>
            {propertyExpanded && (
              <div className="property-list scrollable">
                {props.map((x) => (
                  <button
                    key={x.apartment_id}
                    className={`property-item ${sel?.apartment_id === x.apartment_id ? "active" : ""}`}
                    onClick={() => {
                      setSel(x);
                      setDrawer(false);
                    }}
                  >
                    <div className="title-row">
                      <strong>{x.short_address || x.address || "—"}</strong>
                      <span className="badge">{money(x.total_balance)}</span>
                    </div>
                    {x.address && x.short_address && x.address !== x.short_address ? (
                      <div className="addr">{x.address}</div>
                    ) : null}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="drawer-section top-gap">
            <div className="title-row">
              <button className="secondary" onClick={() => setTenantsExpanded((s) => !s)}>
                {tenantsExpanded ? "▾ Орендарі" : "▸ Орендарі"}
              </button>
              <button
                onClick={() => {
                  setTenantActionError("");
                  setAddTenantOpen(true);
                }}
              >
                Додати
              </button>
            </div>
            {tenantsExpanded && (
              <div className="property-list scrollable">
                {sortedTenants.length === 0 && <span className="helper">Орендарів поки немає.</span>}
                {sortedTenants.map((tenant) => (
                  <button
                    key={tenant.id}
                    type="button"
                    className={`property-item tenant-item ${tenant.is_active_now ? "" : "inactive"}`}
                    onClick={() => openTenantModal(tenant)}
                  >
                    <div className="title-row">
                      <strong>{tenant.full_name}</strong>
                      <span className="badge">
                        {tenant.is_active_now ? "активний" : "неактивний"}
                      </span>
                    </div>
                    <div className="addr">
                      #{tenant.id}
                      {tenant.email ? ` • ${tenant.email}` : ""}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {addPropertyOpen && (
        <Modal title="Додати нерухомість" onClose={() => setAddPropertyOpen(false)}>
          <div className="forms-grid compact-grid">
            <div className="full-row">
              <PlaceAutocompleteField country={ap.country} onPlaceSelect={handlePlaceSelect} />
            </div>
            <In
              label="Країна"
              tip="Країна розташування нерухомості"
              placeholder="Україна"
              help="За замовчуванням Україна, але поле можна змінити."
              value={ap.country}
              onChange={(e) => setAp((s) => ({ ...s, country: e.target.value }))}
            />
            <In
              label="Область"
              tip="Область або регіон"
              placeholder="Івано-Франківська область"
              value={ap.region}
              onChange={(e) => setAp((s) => ({ ...s, region: e.target.value }))}
            />
            <In
              label="Місто / село"
              tip="Населений пункт"
              placeholder="Івано-Франківськ"
              value={ap.locality}
              onChange={(e) => setAp((s) => ({ ...s, locality: e.target.value }))}
            />
            <In
              label="Вулиця"
              tip="Назва вулиці"
              placeholder="Івасюка"
              help="Потрібна для короткої адреси в списках."
              value={ap.street}
              onChange={(e) => setAp((s) => ({ ...s, street: e.target.value }))}
            />
            <In
              label="Номер будинку"
              tip="Будинок"
              placeholder="11"
              value={ap.house_number}
              onChange={(e) => setAp((s) => ({ ...s, house_number: e.target.value }))}
            />
            <In
              label="Квартира"
              tip="Номер квартири, якщо є"
              placeholder="195"
              value={ap.apartment_number}
              onChange={(e) => setAp((s) => ({ ...s, apartment_number: e.target.value }))}
            />
            <In
              label="Поштовий індекс"
              tip="Поштовий індекс"
              placeholder="76000"
              value={ap.postal_code}
              onChange={(e) => setAp((s) => ({ ...s, postal_code: e.target.value }))}
            />
            <In
              label="Загальна площа, м²"
              tip="Загальна площа"
              type="number"
              min="0"
              step="0.01"
              value={ap.area_m2}
              onChange={(e) => setAp((s) => ({ ...s, area_m2: e.target.value }))}
            />
            <In
              label="Житлова площа, м²"
              tip="Житлова площа"
              type="number"
              min="0"
              step="0.01"
              value={ap.living_area_m2}
              onChange={(e) => setAp((s) => ({ ...s, living_area_m2: e.target.value }))}
            />
            <In
              label="Під'їзд"
              tip="Номер або позначення під'їзду"
              placeholder="2"
              value={ap.entrance}
              onChange={(e) => setAp((s) => ({ ...s, entrance: e.target.value }))}
            />
            <In
              label="Поверх"
              tip="Поверх"
              placeholder="7"
              value={ap.floor}
              onChange={(e) => setAp((s) => ({ ...s, floor: e.target.value }))}
            />
            <In
              label="К-сть кімнат"
              tip="Кількість кімнат"
              type="number"
              min="0"
              step="1"
              value={ap.room_count}
              onChange={(e) => setAp((s) => ({ ...s, room_count: e.target.value }))}
            />
            <In
              label="К-сть прописаних"
              tip="Кількість зареєстрованих мешканців"
              type="number"
              min="1"
              step="1"
              value={ap.registered_residents}
              onChange={(e) => setAp((s) => ({ ...s, registered_residents: e.target.value }))}
            />
            <In
              label="Широта"
              tip="Широта для точного позиціонування"
              type="number"
              min="-90"
              max="90"
              step="0.000001"
              value={ap.latitude}
              onChange={(e) => setAp((s) => ({ ...s, latitude: e.target.value }))}
            />
            <In
              label="Довгота"
              tip="Довгота для точного позиціонування"
              type="number"
              min="-180"
              max="180"
              step="0.000001"
              value={ap.longitude}
              onChange={(e) => setAp((s) => ({ ...s, longitude: e.target.value }))}
            />
            <Ta
              label="Технічні примітки"
              tip="Будь-які технічні деталі по об'єкту"
              placeholder="Домофон, код доступу, стан мереж, важливі нюанси..."
              rows={4}
              value={ap.object_notes}
              onChange={(e) => setAp((s) => ({ ...s, object_notes: e.target.value }))}
            />
            <Ta
              label="Примітка до локації"
              tip="Додаткові орієнтири для пошуку"
              placeholder="Вхід з двору, другий під'їзд ліворуч..."
              rows={3}
              value={ap.location_note}
              onChange={(e) => setAp((s) => ({ ...s, location_note: e.target.value }))}
            />
          </div>
          <div className="subcard top-gap">
            <h4>Попередній перегляд адреси</h4>
            <p className="helper">Коротка адреса: {previewShortAddress || "—"}</p>
            <p className="helper">Повна адреса: {previewFullAddress || "—"}</p>
            <p className="helper">
              Google Maps:{" "}
              {previewGoogleMapsUrl ? (
                <a href={previewGoogleMapsUrl} target="_blank" rel="noreferrer">
                  Відкрити на карті
                </a>
              ) : (
                "з'явиться після заповнення адреси або координат"
              )}
            </p>
          </div>
          <div className="row-actions top-gap">
            <button
              onClick={async () => {
                await createAp();
                setAddPropertyOpen(false);
              }}
            >
              Створити
            </button>
            <button className="secondary" onClick={() => setAddPropertyOpen(false)}>
              Скасувати
            </button>
          </div>
        </Modal>
      )}

      {addTenantOpen && (
        <Modal
          title="Додати орендаря"
          onClose={() => {
            setTenantActionError("");
            setAddTenantOpen(false);
          }}
        >
          <div className="forms-grid compact-grid">
            <In
              tip="ПІБ орендаря"
              value={newTenant.full_name}
              onChange={(e) => setNewTenant((s) => ({ ...s, full_name: e.target.value }))}
            />
            <In
              tip="Телефон"
              value={newTenant.phone}
              onChange={(e) => setNewTenant((s) => ({ ...s, phone: e.target.value }))}
            />
            <In
              tip="Дата початку оренди"
              type="date"
              value={newTenant.start_date}
              onChange={(e) => setNewTenant((s) => ({ ...s, start_date: e.target.value }))}
            />
            <In
              tip="Email (логін орендаря)"
              value={newTenant.email}
              onChange={(e) => setNewTenant((s) => ({ ...s, email: e.target.value }))}
            />
            <In
              tip="Код доступу"
              value={newTenant.access_code}
              onChange={(e) => setNewTenant((s) => ({ ...s, access_code: e.target.value }))}
            />
            <In
              tip="Назва в банківській виписці"
              value={newTenant.bank_statement_name}
              onChange={(e) =>
                setNewTenant((s) => ({ ...s, bank_statement_name: e.target.value }))
              }
            />
            <In
              tip="Оренда за місяць"
              type="number"
              min="0"
              step="0.01"
              value={newTenant.rent_amount}
              onChange={(e) => setNewTenant((s) => ({ ...s, rent_amount: e.target.value }))}
            />
            <Se
              tip="Валюта оренди"
              value={newTenant.rent_currency}
              onChange={(e) =>
                setNewTenant((s) => ({
                  ...s,
                  rent_currency: e.target.value as "UAH" | "USD" | "EUR",
                }))
              }
            >
              <option value="UAH">UAH</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
            </Se>
          </div>
          {tenantActionError && <p className="error">{tenantActionError}</p>}
          <div className="row-actions top-gap">
            <button
              onClick={async () => {
                try {
                  setTenantActionError("");
                  await createTenantOnly();
                  setAddTenantOpen(false);
                } catch (e) {
                  setTenantActionError(e instanceof Error ? e.message : "Не вдалося створити орендаря");
                }
              }}
            >
              Створити
            </button>
            <button
              className="secondary"
              onClick={() => {
                setTenantActionError("");
                setAddTenantOpen(false);
              }}
            >
              Скасувати
            </button>
          </div>
        </Modal>
      )}
      {selectedTenant && (
        <Modal
          title={`Орендар: ${selectedTenant.full_name}`}
          onClose={() => {
            setTenantActionError("");
            setSelectedTenant(null);
          }}
        >
          {!tenantEditMode ? (
            <div className="tenant-detail">
              <div><span className="helper">ПІБ</span><strong>{selectedTenant.full_name}</strong></div>
              <div><span className="helper">Email</span><strong>{selectedTenant.email || "—"}</strong></div>
              <div><span className="helper">Основний телефон</span><strong>{selectedTenant.phone || "—"}</strong></div>
              <div><span className="helper">Додаткові телефони</span><strong>{(selectedTenant.phones || []).join(", ") || "—"}</strong></div>
              <div><span className="helper">Код доступу</span><strong>{selectedTenant.access_code || "—"}</strong></div>
              <div><span className="helper">Оренда</span><strong>{selectedTenant.rent_amount || "—"} {selectedTenant.rent_currency || ""}</strong></div>
              <div><span className="helper">Банк. ім'я</span><strong>{selectedTenant.bank_statement_name || "—"}</strong></div>
              <div><span className="helper">Паспорт</span><strong>{selectedTenant.passport_number || "—"}</strong></div>
            </div>
          ) : (
            <div className="forms-grid compact-grid">
              <In tip="ПІБ" value={tenantEditForm.full_name} onChange={(e) => setTenantEditForm((s) => ({ ...s, full_name: e.target.value }))} />
              <In tip="Основний телефон" value={tenantEditForm.primary_phone} onChange={(e) => setTenantEditForm((s) => ({ ...s, primary_phone: e.target.value }))} />
              <In tip="Email" value={tenantEditForm.email} onChange={(e) => setTenantEditForm((s) => ({ ...s, email: e.target.value }))} />
              <In tip="Додаткові телефони (через кому)" value={tenantEditForm.phones} onChange={(e) => setTenantEditForm((s) => ({ ...s, phones: e.target.value }))} />
              <In tip="Ім'я у виписці" value={tenantEditForm.bank_statement_name} onChange={(e) => setTenantEditForm((s) => ({ ...s, bank_statement_name: e.target.value }))} />
              <In tip="Сума оренди" type="number" min="0" step="0.01" value={tenantEditForm.rent_amount} onChange={(e) => setTenantEditForm((s) => ({ ...s, rent_amount: e.target.value }))} />
              <Se tip="Валюта" value={tenantEditForm.rent_currency} onChange={(e) => setTenantEditForm((s) => ({ ...s, rent_currency: e.target.value as "UAH" | "USD" | "EUR" }))}>
                <option value="UAH">UAH</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </Se>
              <In tip="Номер паспорта" value={tenantEditForm.passport_number} onChange={(e) => setTenantEditForm((s) => ({ ...s, passport_number: e.target.value }))} />
              <In tip="Ким виданий" value={tenantEditForm.passport_issued_by} onChange={(e) => setTenantEditForm((s) => ({ ...s, passport_issued_by: e.target.value }))} />
              <In tip="Дата видачі" type="date" value={tenantEditForm.passport_issue_date} onChange={(e) => setTenantEditForm((s) => ({ ...s, passport_issue_date: e.target.value }))} />
              <In tip="Дата завершення" type="date" value={tenantEditForm.passport_expiry_date} onChange={(e) => setTenantEditForm((s) => ({ ...s, passport_expiry_date: e.target.value }))} />
              <In tip="Контакти (Ім'я|Зв'язок|Телефон|Примітка)" value={tenantEditForm.contacts_text} onChange={(e) => setTenantEditForm((s) => ({ ...s, contacts_text: e.target.value }))} />
              <label className="check">
                <input
                  type="checkbox"
                  checked={tenantEditForm.portal_enabled}
                  onChange={(e) =>
                    setTenantEditForm((s) => ({ ...s, portal_enabled: e.target.checked }))
                  }
                />
                Доступ до кабінету орендаря
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={tenantEditForm.can_submit_meter_readings}
                  onChange={(e) =>
                    setTenantEditForm((s) => ({
                      ...s,
                      can_submit_meter_readings: e.target.checked,
                    }))
                  }
                  disabled={!tenantEditForm.portal_enabled}
                />
                Дозволити вводити показники лічильників
              </label>
              <In
                tip="Новий пароль кабінету (необов'язково)"
                type="password"
                value={tenantEditForm.portal_password}
                onChange={(e) =>
                  setTenantEditForm((s) => ({ ...s, portal_password: e.target.value }))
                }
              />
            </div>
          )}
          {tenantActionError && <p className="error">{tenantActionError}</p>}
          <div className="row-actions top-gap">
            {!tenantEditMode ? (
              <button
                onClick={() => {
                  setTenantActionError("");
                  setTenantEditMode(true);
                }}
              >
                Змінити
              </button>
            ) : (
              <button
                onClick={async () => {
                  try {
                    setTenantActionError("");
                    await updateTenantById(selectedTenant.id, tenantEditForm);
                    setTenantEditMode(false);
                    setSelectedTenant(null);
                  } catch (e) {
                    setTenantActionError(e instanceof Error ? e.message : "Не вдалося оновити орендаря");
                  }
                }}
              >
                Зберегти
              </button>
            )}
            <button
              className="secondary"
              onClick={() => {
                setTenantActionError("");
                setSelectedTenant(null);
              }}
            >
              Закрити
            </button>
            <button
              className="danger"
              onClick={async () => {
                try {
                  setTenantActionError("");
                  await deleteTenantById(selectedTenant.id);
                  setSelectedTenant(null);
                } catch (e) {
                  setTenantActionError(e instanceof Error ? e.message : "Не вдалося видалити орендаря");
                }
              }}
            >
              Видалити
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
