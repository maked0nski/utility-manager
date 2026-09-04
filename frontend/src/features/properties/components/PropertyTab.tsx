import { In, Se, Ta } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import type { Dispatch, SetStateAction } from "react";
import { useCallback, useEffect, useState } from "react";
import type {
  ApartmentEquipmentForm,
  ApartmentEquipmentItem,
  ApartmentProfileForm,
  MeterItem,
  MeterTypeItem,
  MeterUpsertForm,
} from "@/shared/api/types";
import {
  buildApartmentFormFromGooglePlace,
  buildFullPropertyAddress,
  buildPropertyGoogleMapsUrl,
  buildShortPropertyAddress,
} from "@/features/properties/utils/address";
import { PlaceAutocompleteField } from "@/features/properties/components/PlaceAutocompleteField";

const UTILITY_TYPE_LABELS: Record<MeterItem["utility_type"], string> = {
  electricity: "Електроенергія",
  water: "Вода",
  gas: "Газ",
  heating: "Опалення",
  sewage: "Водовідведення",
  internet: "Інтернет",
  other: "Інше",
};

function showValue(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "—";
  const normalized = String(value).trim();
  return normalized ? normalized : "—";
}

function showMapLink(url: string) {
  if (!url) return "—";
  return (
    <a href={url} target="_blank" rel="noreferrer">
      Відкрити на Google Maps
    </a>
  );
}

export function PropertyTab({
  ap,
  setAp,
  detail,
  meters,
  equipment,
  equipmentForm,
  setEquipmentForm,
  submitEquipment,
  startEditEquipment,
  askDeleteEquipment,
  resetEquipmentForm,
  meterForm,
  setMeterForm,
  meterTypes,
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
  dt,
  saveAp,
  delAp,
  setTab,
}: {
  ap: ApartmentProfileForm;
  setAp: Dispatch<SetStateAction<ApartmentProfileForm>>;
  detail: any;
  meters: MeterItem[];
  equipment: ApartmentEquipmentItem[];
  equipmentForm: ApartmentEquipmentForm;
  setEquipmentForm: Dispatch<SetStateAction<ApartmentEquipmentForm>>;
  submitEquipment: () => Promise<void>;
  startEditEquipment: (item: ApartmentEquipmentItem) => void;
  askDeleteEquipment: (item: ApartmentEquipmentItem) => void;
  resetEquipmentForm: () => void;
  meterForm: MeterUpsertForm;
  setMeterForm: Dispatch<SetStateAction<MeterUpsertForm>>;
  meterTypes: MeterTypeItem[];
  submitMeter: () => Promise<boolean>;
  startEditMeter: (meter: MeterItem) => void;
  askDeleteMeter: (meter: MeterItem) => void;
  resetMeterForm: () => void;
  replacingMeterId: number | null;
  replacementForm: { serial_number: string; initial_reading: string; installed_at: string };
  setReplacementForm: Dispatch<
    SetStateAction<{ serial_number: string; initial_reading: string; installed_at: string }>
  >;
  startReplaceMeter: (meter: MeterItem) => void;
  submitReplacement: () => Promise<void>;
  resetReplacementForm: () => void;
  dt: (x: string | Date | null | undefined) => string;
  saveAp: () => Promise<void>;
  delAp: () => Promise<void>;
  setTab: (tab: "tariffs") => void;
}) {
  const [propertyEditOpen, setPropertyEditOpen] = useState(false);
  const [propertyDetailsOpen, setPropertyDetailsOpen] = useState(false);
  const [selectedMeter, setSelectedMeter] = useState<MeterItem | null>(null);
  const [addMeterOpen, setAddMeterOpen] = useState(false);
  const [replaceMode, setReplaceMode] = useState(false);
  const [selectedEquipment, setSelectedEquipment] = useState<ApartmentEquipmentItem | null>(null);
  const [addEquipmentOpen, setAddEquipmentOpen] = useState(false);

  useEffect(() => {
    if (!selectedMeter) {
      return;
    }
    const stillExists = meters.some((m) => m.id === selectedMeter.id);
    if (!stillExists) {
      setSelectedMeter(null);
      setReplaceMode(false);
      resetMeterForm();
      resetReplacementForm();
      return;
    }
    const fresh = meters.find((m) => m.id === selectedMeter.id);
    if (fresh) {
      setSelectedMeter(fresh);
    }
  }, [meters, selectedMeter, resetMeterForm, resetReplacementForm]);

  const openMeterModal = (meter: MeterItem) => {
    setAddMeterOpen(false);
    setSelectedMeter(meter);
    setReplaceMode(false);
    startEditMeter(meter);
    resetReplacementForm();
  };

  const openAddMeterModal = () => {
    resetMeterForm();
    resetReplacementForm();
    setReplaceMode(false);
    setSelectedMeter(null);
    setAddMeterOpen(true);
  };

  const closeMeterModal = () => {
    setSelectedMeter(null);
    setAddMeterOpen(false);
    setReplaceMode(false);
    resetMeterForm();
    resetReplacementForm();
  };

  const openEquipmentModal = (item: ApartmentEquipmentItem) => {
    setAddEquipmentOpen(false);
    setSelectedEquipment(item);
    startEditEquipment(item);
  };

  const openAddEquipmentModal = () => {
    resetEquipmentForm();
    setSelectedEquipment(null);
    setAddEquipmentOpen(true);
  };

  const closeEquipmentModal = () => {
    setSelectedEquipment(null);
    setAddEquipmentOpen(false);
    resetEquipmentForm();
  };
  const handlePlaceSelect = useCallback(
    async (place: any) => {
      setAp((current) => ({ ...current, ...buildApartmentFormFromGooglePlace(place, current) }));
    },
    [setAp],
  );
  const previewShortAddress = buildShortPropertyAddress(ap) || ap.short_address || detail?.short_address || "";
  const previewFullAddress = buildFullPropertyAddress(ap) || ap.address || detail?.address || "";
  const previewGoogleMapsUrl = buildPropertyGoogleMapsUrl(ap) || ap.google_maps_url || detail?.google_maps_url || "";

  return (
    <>
      <div className="property-sections">
        <div className="subcard">
          <h4>З чого почати</h4>
          <div className="property-steps">
            <div>
              <span className="helper">Крок 1</span>
              <strong>Перевірте дані об&apos;єкта</strong>
            </div>
            <div>
              <span className="helper">Крок 2</span>
              <strong>Додайте лічильники</strong>
            </div>
            <div>
              <span className="helper">Крок 3</span>
              <strong>Підключіть послуги об&apos;єкта</strong>
            </div>
            <div>
              <span className="helper">Крок 4</span>
              <strong>За потреби додайте обладнання</strong>
            </div>
          </div>
          <div className="row-actions top-gap">
            <button className="secondary" onClick={() => setTab("tariffs")}>
              Перейти до послуг об&apos;єкта
            </button>
          </div>
        </div>
        <div className="subcard">
          <h4>Інформація про об&apos;єкт</h4>
          <p className="helper">Показуємо тільки головне. Натисніть на картку нижче, щоб відкрити повну інформацію про об&apos;єкт.</p>
          <div
            className="property-overview-button"
            role="button"
            tabIndex={0}
            onClick={() => setPropertyDetailsOpen(true)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setPropertyDetailsOpen(true);
              }
            }}
          >
            <span className="property-overview-row">
              <span className="helper">Повна адреса</span>
              <strong>{showValue(previewFullAddress)}</strong>
            </span>
            <span className="property-overview-inline">
              <span>
                <span className="helper">Загальна площа, м²</span>
                <strong>{showValue(ap.area_m2)}</strong>
              </span>
              <span>
                <span className="helper">Житлова площа, м²</span>
                <strong>{showValue(ap.living_area_m2)}</strong>
              </span>
              <span>
                <span className="helper">Google Maps</span>
                <strong>{showMapLink(previewGoogleMapsUrl)}</strong>
              </span>
            </span>
          </div>
        </div>
        <div className="subcard">
          <h4>Лічильники</h4>
          <p className="helper">Тут створюються самі пристрої. Тарифи і стартові показники задаються пізніше у вкладці `Послуги об&apos;єкта`.</p>
          <div className="meter-list">
            {meters.length === 0 && <span className="helper">Лічильників ще немає.</span>}
            {meters.map((meter) => (
              <button
                key={meter.id}
                type="button"
                className={`meter-item ${meter.is_active === false ? "archived" : "active"}`}
                onClick={() => openMeterModal(meter)}
              >
                <div className="meter-item-top">
                <strong>{meter.display_name || meter.meter_type_name || "Лічильник"}</strong>
                  <span className={`status-pill ${meter.is_active === false ? "draft" : "ok"}`}>
                    {meter.is_active === false ? "Архівний" : "Активний"}
                  </span>
                </div>
                <div className="meter-item-meta">
                  {UTILITY_TYPE_LABELS[meter.utility_type] || meter.utility_type}
                  {" • "}
                  № {meter.serial_number || "—"}
                </div>
                <div className="meter-item-meta">Встановлено: {dt(meter.installed_at) || "—"}</div>
              </button>
            ))}
          </div>
          <div className="row-actions">
            <button onClick={openAddMeterModal}>Додати лічильник</button>
          </div>
        </div>
        <div className="subcard">
          <h4>Обладнання</h4>
          <p className="helper">Необов&apos;язковий блок. Використовуйте його тільки якщо потрібно вести сервісний графік техніки в об&apos;єкті.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Назва</th>
                  <th>Категорія</th>
                  <th>Модель/серійний</th>
                  <th>Останній/наступний сервіс</th>
                  <th>Інтервал (днів)</th>
                  <th>Статус</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {equipment.length === 0 && (
                  <tr>
                    <td colSpan={7}>
                      <span className="helper">Обладнання ще не додано.</span>
                    </td>
                  </tr>
                )}
                {equipment.map((item) => (
                  <tr key={item.id}>
                    <td>{item.name}</td>
                    <td>{item.category}</td>
                    <td>
                      {item.model_name || "—"}
                      {item.serial_number ? ` / ${item.serial_number}` : ""}
                    </td>
                    <td>
                      {dt(item.last_service_at) || "—"} / {dt(item.next_service_at) || "—"}
                    </td>
                    <td>{item.service_interval_days ?? "—"}</td>
                    <td>{item.is_active ? "Активне" : "Архів"}</td>
                    <td>
                      <button className="secondary icon-btn" onClick={() => openEquipmentModal(item)}>
                        ✎
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row-actions">
            <button onClick={openAddEquipmentModal}>Додати обладнання</button>
          </div>
        </div>
      </div>
      {propertyEditOpen && (
        <Modal title="Редагувати об'єкт" onClose={() => setPropertyEditOpen(false)}>
          <div className="forms-grid compact-grid">
            <div className="full-row">
              <PlaceAutocompleteField country={ap.country} onPlaceSelect={handlePlaceSelect} />
            </div>
            <In
              label="Країна"
              tip="Країна розташування нерухомості"
              placeholder="Україна"
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
              value={ap.entrance}
              onChange={(e) => setAp((s) => ({ ...s, entrance: e.target.value }))}
            />
            <In
              label="Поверх"
              tip="Поверх"
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
              label="Націнка над тарифом з кабінету, %"
              tip="Мінімальний відсоток, на який моя ціна має перевищувати тариф з кабінету постачальника"
              type="number"
              min="0"
              max="100"
              step="0.01"
              placeholder="10"
              value={ap.cabinet_markup_percent}
              onChange={(e) => setAp((s) => ({ ...s, cabinet_markup_percent: e.target.value }))}
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
            <p className="helper">Google Maps: {showMapLink(previewGoogleMapsUrl)}</p>
          </div>
          <div className="row-actions top-gap">
            <button
              onClick={async () => {
                await saveAp();
                setPropertyEditOpen(false);
              }}
            >
              Зберегти
            </button>
            <button className="secondary" onClick={() => setPropertyEditOpen(false)}>
              Скасувати
            </button>
          </div>
        </Modal>
      )}
      {propertyDetailsOpen && (
        <Modal title="Повна інформація про об'єкт" onClose={() => setPropertyDetailsOpen(false)}>
          <div className="property-summary">
            <div>
              <span className="helper">Коротка адреса</span>
              <strong>{showValue(previewShortAddress)}</strong>
            </div>
            <div>
              <span className="helper">Повна адреса</span>
              <strong>{showValue(previewFullAddress)}</strong>
            </div>
            <div>
              <span className="helper">Країна</span>
              <strong>{showValue(ap.country)}</strong>
            </div>
            <div>
              <span className="helper">Область</span>
              <strong>{showValue(ap.region)}</strong>
            </div>
            <div>
              <span className="helper">Місто / село</span>
              <strong>{showValue(ap.locality)}</strong>
            </div>
            <div>
              <span className="helper">Вулиця</span>
              <strong>{showValue(ap.street)}</strong>
            </div>
            <div>
              <span className="helper">Будинок / квартира</span>
              <strong>
                {showValue(
                  [ap.house_number, ap.apartment_number ? `кв ${ap.apartment_number}` : ""]
                    .filter(Boolean)
                    .join(", "),
                )}
              </strong>
            </div>
            <div>
              <span className="helper">Поштовий індекс</span>
              <strong>{showValue(ap.postal_code)}</strong>
            </div>
            <div>
              <span className="helper">Загальна площа, м²</span>
              <strong>{showValue(ap.area_m2)}</strong>
            </div>
            <div>
              <span className="helper">Житлова площа, м²</span>
              <strong>{showValue(ap.living_area_m2)}</strong>
            </div>
            <div>
              <span className="helper">Під'їзд / поверх</span>
              <strong>{showValue([ap.entrance, ap.floor].filter(Boolean).join(" / "))}</strong>
            </div>
            <div>
              <span className="helper">Кімнат / прописаних</span>
              <strong>{showValue([ap.room_count, ap.registered_residents].filter(Boolean).join(" / "))}</strong>
            </div>
            <div>
              <span className="helper">Google Maps</span>
              <strong>{showMapLink(previewGoogleMapsUrl)}</strong>
            </div>
            <div>
              <span className="helper">Широта / довгота</span>
              <strong>{showValue([ap.latitude, ap.longitude].filter(Boolean).join(" / "))}</strong>
            </div>
            <div>
              <span className="helper">Примітка до локації</span>
              <strong>{showValue(ap.location_note)}</strong>
            </div>
            <div>
              <span className="helper">Нотатки по об&apos;єкту</span>
              <strong>{showValue(ap.object_notes)}</strong>
            </div>
          </div>
          <div className="row-actions top-gap">
            <button
              onClick={() => {
                setPropertyDetailsOpen(false);
                setPropertyEditOpen(true);
              }}
            >
              Редагувати
            </button>
            <button className="danger" onClick={delAp}>
              Видалити
            </button>
            <button className="secondary" onClick={() => setPropertyDetailsOpen(false)}>
              Закрити
            </button>
          </div>
        </Modal>
      )}
      {(selectedMeter || addMeterOpen) && (
        <Modal
          title={selectedMeter ? `Лічильник: ${selectedMeter.display_name || selectedMeter.meter_type_name || "Лічильник"}` : "Додати лічильник"}
          onClose={closeMeterModal}
        >
          <div className="forms-grid compact-grid">
            <Se
              label="Тип лічильника"
              tip="Тип лічильника"
              help="Список типів налаштовується у вкладці довідників."
              value={meterForm.meter_type_id}
              onChange={(e) =>
                setMeterForm((s) => ({
                  ...s,
                  meter_type_id: e.target.value,
                }))
              }
            >
              <option value="">Оберіть тип лічильника</option>
              {meterTypes
                .filter((item) => item.is_active || String(item.id) === meterForm.meter_type_id)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} • {UTILITY_TYPE_LABELS[item.utility_type]}
                  </option>
                ))}
            </Se>
            <In
              label="Серійний номер"
              tip="Серійний номер"
              placeholder="Серійний номер (необов'язково)"
              value={meterForm.serial_number}
              onChange={(e) => setMeterForm((s) => ({ ...s, serial_number: e.target.value }))}
            />
            <In
              label="Дата встановлення"
              tip="Дата встановлення"
              type="date"
              value={meterForm.installed_at}
              onChange={(e) => setMeterForm((s) => ({ ...s, installed_at: e.target.value }))}
            />
          </div>
          <div className="row-actions top-gap">
            <button
              onClick={async () => {
                const saved = await submitMeter();
                if (saved) {
                  closeMeterModal();
                }
              }}
            >
              {selectedMeter ? "Зберегти зміни" : "Додати лічильник"}
            </button>
            {selectedMeter && (
              <button
                className="danger"
                onClick={() => {
                  askDeleteMeter(selectedMeter);
                  closeMeterModal();
                }}
              >
                Видалити
              </button>
            )}
            {selectedMeter && selectedMeter.is_active !== false && (
              <button
                className="secondary"
                onClick={() => {
                  if (replaceMode) {
                    setReplaceMode(false);
                    resetReplacementForm();
                    return;
                  }
                  setReplaceMode(true);
                  startReplaceMeter(selectedMeter);
                }}
              >
                {replaceMode ? "Скасувати заміну" : "Заміна лічильника"}
              </button>
            )}
            <button className="secondary" onClick={closeMeterModal}>
              Скасувати
            </button>
          </div>
          {selectedMeter &&
            replaceMode &&
            selectedMeter.is_active !== false &&
            replacingMeterId === selectedMeter.id && (
            <div className="subcard top-gap">
              <h4>Заміна лічильника</h4>
              <div className="forms-grid compact-grid">
                <In
                  tip="Новий серійний номер"
                  placeholder="Серійний номер"
                  value={replacementForm.serial_number}
                  onChange={(e) =>
                    setReplacementForm((s) => ({ ...s, serial_number: e.target.value }))
                  }
                />
                <In
                  label="Стартовий показник нового лічильника"
                  tip="Стартовий показник нового лічильника. Початкове значення нового лічильника на дату заміни."
                  placeholder="Введіть стартовий показник"
                  type="number"
                  min="0"
                  step="0.001"
                  value={replacementForm.initial_reading}
                  onChange={(e) =>
                    setReplacementForm((s) => ({ ...s, initial_reading: e.target.value }))
                  }
                />
                <In
                  tip="Дата заміни"
                  type="date"
                  value={replacementForm.installed_at}
                  onChange={(e) =>
                    setReplacementForm((s) => ({ ...s, installed_at: e.target.value }))
                  }
                />
              </div>
              <div className="row-actions">
                <button onClick={submitReplacement}>Підтвердити заміну</button>
                <button className="secondary" onClick={resetReplacementForm}>
                  Очистити поля
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
      {(selectedEquipment || addEquipmentOpen) && (
        <Modal
          title={selectedEquipment ? `Обладнання: ${selectedEquipment.name}` : "Додати обладнання"}
          onClose={closeEquipmentModal}
        >
          <div className="forms-grid compact-grid">
            <In
              tip="Назва обладнання"
              placeholder="Котел, бойлер, кондиціонер..."
              value={equipmentForm.name}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, name: e.target.value }))}
            />
            <In
              tip="Категорія"
              placeholder="heating/water/electricity/other"
              value={equipmentForm.category}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, category: e.target.value }))}
            />
            <In
              tip="Модель"
              placeholder="Модель"
              value={equipmentForm.model_name}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, model_name: e.target.value }))}
            />
            <In
              tip="Серійний номер"
              placeholder="Серійний номер"
              value={equipmentForm.serial_number}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, serial_number: e.target.value }))}
            />
            <In
              tip="Дата встановлення"
              type="date"
              value={equipmentForm.installed_at}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, installed_at: e.target.value }))}
            />
            <In
              tip="URL інструкції"
              placeholder="https://..."
              value={equipmentForm.manual_url}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, manual_url: e.target.value }))}
            />
            <In
              tip="Інтервал сервісу (днів)"
              type="number"
              min="1"
              value={equipmentForm.service_interval_days}
              onChange={(e) =>
                setEquipmentForm((s) => ({ ...s, service_interval_days: e.target.value }))
              }
            />
            <In
              tip="Останній сервіс"
              type="date"
              value={equipmentForm.last_service_at}
              onChange={(e) =>
                setEquipmentForm((s) => ({ ...s, last_service_at: e.target.value }))
              }
            />
            <In
              tip="Наступний сервіс"
              type="date"
              value={equipmentForm.next_service_at}
              onChange={(e) =>
                setEquipmentForm((s) => ({ ...s, next_service_at: e.target.value }))
              }
            />
            <In
              tip="Нотатка"
              placeholder="Деталі сервісу/вимоги"
              value={equipmentForm.note}
              onChange={(e) => setEquipmentForm((s) => ({ ...s, note: e.target.value }))}
            />
            <Se
              tip="Статус"
              value={equipmentForm.is_active ? "active" : "archived"}
              onChange={(e) =>
                setEquipmentForm((s) => ({ ...s, is_active: e.target.value === "active" }))
              }
            >
              <option value="active">Активне</option>
              <option value="archived">Архівне</option>
            </Se>
          </div>
          <div className="row-actions top-gap">
            <button
              onClick={async () => {
                await submitEquipment();
                closeEquipmentModal();
              }}
            >
              {selectedEquipment ? "Зберегти зміни" : "Додати обладнання"}
            </button>
            {selectedEquipment && (
              <button
                className="danger"
                onClick={() => {
                  askDeleteEquipment(selectedEquipment);
                  closeEquipmentModal();
                }}
              >
                Видалити
              </button>
            )}
            <button className="secondary" onClick={closeEquipmentModal}>
              Скасувати
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
