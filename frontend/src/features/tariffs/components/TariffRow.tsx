import { dt, money, unitLabel } from "@/shared/utils/format";

type TariffRowData = {
  service_name: string;
  price_per_unit: string | number;
  unit_name: string;
  personal_account?: string | null;
  provider_name?: string | null;
  automation_connected?: boolean;
  is_active_for_period?: boolean;
  last_tariff_check_at?: string | null;
  auto_check_status?: string | null;
  auto_check_message?: string | null;
  submit_enabled?: boolean;
  submit_completed_for_period?: boolean;
  submit_state_reason?: string | null;
  charge_mode?: "fixed" | "metered";
  fixed_quantity_source?: "auto" | "unit" | "apartment_registered_residents" | "apartment_area_m2";
  fixed_quantity_multiplier?: string | number;
};

const fixedFormulaLabel = (row: TariffRowData) => {
  if (row.charge_mode !== "fixed") return "";
  const source = row.fixed_quantity_source || "auto";
  const multiplier = Number(row.fixed_quantity_multiplier || 1);
  const multLabel = Number.isFinite(multiplier) ? multiplier.toString() : "1";
  if (source === "apartment_registered_residents") return `тариф × прописані × ${multLabel}`;
  if (source === "apartment_area_m2") return `тариф × м² × ${multLabel}`;
  if (source === "unit") return `тариф × ${multLabel}`;
  return `авто × ${multLabel}`;
};

const statusLabel = (status?: string | null) => {
  if (status === "updated") return "✅ Оновлено";
  if (status === "no_change") return "✅ Без змін";
  if (status === "waiting") return "⏳ Очікування";
  if (status === "error") return "⚠ Помилка";
  return "";
};

export const submitBadge = (row: TariffRowData) => {
  if (!row.automation_connected || !row.submit_enabled) return "";
  if (row.submit_completed_for_period) return "📤 Подано";
  if ((row.submit_state_reason || "").toLowerCase().includes("немає показника")) return "🧾 Чекає показник";
  if ((row.submit_state_reason || "").toLowerCase().includes("готово")) return "📨 Готово до подачі";
  return "⏳ Submit";
};

export const TariffRow = ({ row, open }: { row: TariffRowData; open: (row: TariffRowData) => void }) => {
  return (
    <tr>
      <td>{row.service_name}</td>
      <td>{money(row.price_per_unit)}</td>
      <td>
        {unitLabel(row.unit_name)}
        {fixedFormulaLabel(row) ? <div className="helper">{fixedFormulaLabel(row)}</div> : null}
      </td>
      <td>{row.personal_account || ""}</td>
      <td>{row.provider_name || "—"}</td>
      <td>{row.is_active_for_period ? "Активна" : "Неактивна"}</td>
      <td title={row.auto_check_message || ""}>
        {row.automation_connected ? "Підключена" : "Не підключена"}
        {statusLabel(row.auto_check_status) ? <div className="helper">{statusLabel(row.auto_check_status)}</div> : null}
        {submitBadge(row) ? <div className="helper">{submitBadge(row)}</div> : null}
      </td>
      <td>{dt(row.last_tariff_check_at)}</td>
      <td>
        <button className="icon-btn" onClick={() => open(row)}>
          ✎
        </button>
      </td>
    </tr>
  );
};
