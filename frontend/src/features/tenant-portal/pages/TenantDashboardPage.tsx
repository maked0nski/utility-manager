import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { money, periodLabel } from "@/shared/utils/format";
import { localizeApiError, nowYearMonth } from "@/features/tenant-portal/utils";
import type { MeterItem, TenantDashboard } from "@/shared/api/types";

function displayWholeConsumption(value: string | number): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return String(Math.round(parsed));
}

export function TenantDashboardPage({
  token,
  canSubmitMeterReadings,
  dashboard,
  meters,
  setError,
  setNotice,
}: {
  token: string;
  canSubmitMeterReadings: boolean;
  dashboard: UseQueryResult<TenantDashboard, Error>;
  meters: UseQueryResult<MeterItem[], Error>;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
}) {
  const queryClient = useQueryClient();
  const ym = useMemo(() => nowYearMonth(), []);
  const [reading, setReading] = useState({
    meter_id: "",
    register_name: "total",
    year: String(ym.year),
    month: String(ym.month),
    value: "",
  });

  useEffect(() => {
    if (!reading.meter_id && meters.data?.length) {
      setReading((prev) => ({ ...prev, meter_id: String(meters.data?.[0].id || "") }));
    }
  }, [meters.data, reading.meter_id]);

  const submitReadingMutation = useMutation({
    mutationFn: () =>
      api("/tenant/me/readings", token, {
        method: "POST",
        body: {
          meter_id: Number(reading.meter_id),
          register_name: reading.register_name.trim() || "total",
          year: Number(reading.year),
          month: Number(reading.month),
          value: reading.value,
        },
      }),
    onSuccess: () => {
      setError("");
      setNotice("Показники передано.");
      queryClient.invalidateQueries({ queryKey: ["tenant", "dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tenant", "history"] });
      setReading((prev) => ({ ...prev, value: "" }));
    },
    onError: (err) => setError(localizeApiError(err, "Не вдалося передати показники.")),
  });

  const readYear = Number(reading.year);
  const readMonth = Number(reading.month);
  const isReadingPeriodValid = Number.isInteger(readYear) && readYear >= 2000 && readYear <= 2100 && readMonth >= 1 && readMonth <= 12;
  const meterId = "tenant-reading-meter";
  const registerId = "tenant-reading-register";
  const yearId = "tenant-reading-year";
  const monthId = "tenant-reading-month";
  const valueId = "tenant-reading-value";

  return (
    <section className="tenant-card">
      <h2>Поточний стан</h2>
      {dashboard.isLoading ? <p className="tenant-muted">Завантаження дашборду...</p> : null}
      {dashboard.isError ? (
        <div className="tenant-error-box">
          <p>{localizeApiError(dashboard.error, "Не вдалося завантажити дашборд.")}</p>
          <button className="btn-primary" onClick={() => dashboard.refetch()}>Повторити</button>
        </div>
      ) : null}
      {dashboard.data ? (
        <>
          <p>{dashboard.data.apartment_code} · {dashboard.data.apartment_address}</p>
          <div className="tenant-summary-grid">
            <div className="tenant-summary-card">
              <span>Борг / баланс</span>
              <strong>{money(dashboard.data.current_debt)} грн</strong>
            </div>
            <div className="tenant-summary-card">
              <span>Поточне нарахування</span>
              <strong>{money(dashboard.data.current_invoice?.total_amount)} грн</strong>
            </div>
            <div className="tenant-summary-card">
              <span>Остання оплата</span>
              <strong>
                {dashboard.data.latest_payment_amount
                  ? `${money(dashboard.data.latest_payment_amount)} грн`
                  : "—"}
              </strong>
              <span>{dashboard.data.latest_payment_date || "—"}</span>
            </div>
            <div className="tenant-summary-card">
              <span>Період рахунку</span>
              <strong>
                {dashboard.data.current_invoice
                  ? periodLabel(dashboard.data.current_invoice.year, dashboard.data.current_invoice.month)
                  : "-"}
              </strong>
            </div>
          </div>
          {dashboard.data.current_invoice?.items?.length ? (
            <div className="tenant-table-wrap">
              <h3>Деталізація поточного рахунку</h3>
              <table>
                <thead>
                  <tr>
                    <th>Послуга</th>
                    <th>Обсяг</th>
                    <th>Ціна</th>
                    <th>Сума</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.data.current_invoice.items.map((item, index) => (
                    <tr key={`${item.service_name}-${index}`}>
                      <td>{item.service_name}</td>
                      <td>{displayWholeConsumption(item.consumption)} {item.unit_name}</td>
                      <td>{money(item.unit_price)}</td>
                      <td>{money(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
      {canSubmitMeterReadings ? (
        <div className="tenant-form-grid">
          <h3>Передати показники</h3>
          <label htmlFor={meterId}>Лічильник</label>
          <select
            id={meterId}
            value={reading.meter_id}
            onChange={(e) => setReading((prev) => ({ ...prev, meter_id: e.target.value }))}
            required
          >
            <option value="">Оберіть лічильник</option>
            {(meters.data || []).map((meter) => (
              <option key={meter.id} value={meter.id}>
                          {meter.display_name || meter.meter_type_name || "Лічильник"} ({meter.serial_number || "без серійного"}){meter.is_active ? "" : " [архів]"}
              </option>
            ))}
          </select>
          {meters.isLoading ? <p className="tenant-muted">Завантаження лічильників...</p> : null}
          {meters.isError ? <p className="tenant-error">{localizeApiError(meters.error, "Не вдалося завантажити лічильники.")}</p> : null}
          <label htmlFor={registerId}>Реєстр</label>
          <p className="tenant-muted">Для однотарифного лічильника залишайте `total`. Для багатозонного використовуйте `day`, `night`, `peak`, `semi_peak` або `off_peak`.</p>
          <input
            id={registerId}
            value={reading.register_name}
            onChange={(e) => setReading((prev) => ({ ...prev, register_name: e.target.value }))}
            placeholder="Наприклад: total або day"
          />
          <label htmlFor={yearId}>Період</label>
          <div className="tenant-inline-grid">
            <input
              id={yearId}
              value={reading.year}
              onChange={(e) => setReading((prev) => ({ ...prev, year: e.target.value.replace(/\D/g, "") }))}
              type="text"
              inputMode="numeric"
              aria-label="Рік періоду"
              placeholder="Рік"
            />
            <input
              id={monthId}
              value={reading.month}
              onChange={(e) => setReading((prev) => ({ ...prev, month: e.target.value.replace(/\D/g, "") }))}
              type="text"
              inputMode="numeric"
              aria-label="Місяць періоду"
              placeholder="Місяць"
            />
          </div>
          {!isReadingPeriodValid ? <p className="tenant-error">Вкажіть коректний період (місяць 1-12, рік 2000-2100).</p> : null}
          <label htmlFor={valueId}>Значення</label>
          <p className="tenant-muted">Вводьте поточний показник з лічильника без зменшення на попередні значення.</p>
          <input
            id={valueId}
            value={reading.value}
            onChange={(e) => setReading((prev) => ({ ...prev, value: e.target.value.replace(",", ".") }))}
            type="number"
            step="0.001"
            min="0"
          />
          <button className="btn-primary" onClick={() => submitReadingMutation.mutate()} disabled={submitReadingMutation.isPending || !reading.meter_id || !reading.value || !isReadingPeriodValid}>
            {submitReadingMutation.isPending ? "Надсилаю..." : "Передати"}
          </button>
        </div>
      ) : (
        <p className="tenant-muted">Передача показників наразі вимкнена адміністратором.</p>
      )}
    </section>
  );
}
