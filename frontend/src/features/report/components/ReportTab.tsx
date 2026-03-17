import { useMemo, useRef } from "react";
import { todayIso } from "@/shared/utils/date";
import type { CalculationRow } from "@/shared/api/types";

type DetailLike = {
  apartment_id: number;
  year: number;
  month: number;
  address: string;
  calc_locked?: boolean;
  tenant?: { full_name?: string } | null;
  utility_balance: {
    previous_month_debt: string;
    month_payments: string;
    current_balance: string;
    actual_current_balance?: string;
    report_generated_at?: string | null;
    report_payments_to_date?: string | null;
    report_payment_date?: string | null;
    report_payment_note?: string | null;
    report_balance?: string | null;
  };
};

export function ReportTab({
  detail,
  money,
  dt,
  loading,
  accr,
  rows,
  periodLabel,
}: {
  detail: DetailLike;
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  loading?: boolean;
  accr: number;
  rows: CalculationRow[];
  periodLabel: string;
}) {
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const isCompensationRow = (row: CalculationRow) => row.service_name.startsWith("Відшкодування:");
  const displayRows = useMemo(() => {
    const grouped = new Map<string, { label: string; subtotal: number; rows: CalculationRow[] }>();
    const plainRows: Array<
      | { type: "group"; key: string; label: string; subtotal: number }
      | { type: "row"; key: string; row: CalculationRow; childOfGroup: boolean }
    > = [];
    for (const row of rows || []) {
      if (!row.service_group_label) {
        plainRows.push({ type: "row", key: `plain:${row.service_name}:${plainRows.length}`, row, childOfGroup: false });
        continue;
      }
      const key = row.service_group_key || `${row.service_group_label}:${row.meter_id || "no-meter"}`;
      if (!grouped.has(key)) grouped.set(key, { label: row.service_group_label, subtotal: 0, rows: [] });
      const bucket = grouped.get(key)!;
      bucket.rows.push(row);
      bucket.subtotal += Number(row.amount || 0);
    }
    const result: Array<
      | { type: "group"; key: string; label: string; subtotal: number }
      | { type: "row"; key: string; row: CalculationRow; childOfGroup: boolean }
    > = [];
    const usedKeys = new Set<string>();
    for (const row of rows || []) {
      if (!row.service_group_label) {
        const next = plainRows.shift();
        if (next) result.push(next);
        continue;
      }
      const key = row.service_group_key || `${row.service_group_label}:${row.meter_id || "no-meter"}`;
      if (usedKeys.has(key)) continue;
      usedKeys.add(key);
      const bucket = grouped.get(key);
      if (!bucket) continue;
      result.push({ type: "group", key: `group:${key}`, label: bucket.label, subtotal: bucket.subtotal });
      bucket.rows.forEach((groupedRow, index) => {
        result.push({ type: "row", key: `group-row:${key}:${index}`, row: groupedRow, childOfGroup: true });
      });
    }
    return result;
  }, [rows]);
  const utilityAccrual = (rows || [])
    .filter((row) => !isCompensationRow(row))
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const compensationTotal = (rows || [])
    .filter((row) => isCompensationRow(row))
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const accrualWithCompensation = utilityAccrual + compensationTotal;
  const reportGeneratedAt = detail.utility_balance.report_generated_at || todayIso();
  const reportPayments = detail.utility_balance.report_payments_to_date ?? detail.utility_balance.month_payments;
  const reportBalance = detail.utility_balance.report_balance ?? detail.utility_balance.current_balance;

  const printReport = () => {
    if (!detail.calc_locked) return;
    window.print();
  };

  const captureSheet = async () => {
    if (!detail.calc_locked) {
      throw new Error("Експорт доступний лише для підтверджених нарахувань.");
    }
    if (!sheetRef.current) throw new Error("Не знайдено блок фактури.");
    const { default: html2canvas } = await import("html2canvas");
    return html2canvas(sheetRef.current, {
      scale: 2,
      backgroundColor: "#ffffff",
      useCORS: true,
    });
  };

  const exportJpeg = async () => {
    try {
      const canvas = await captureSheet();
      const url = canvas.toDataURL("image/jpeg", 0.95);
      const link = document.createElement("a");
      link.href = url;
      link.download = `faktura_${detail.apartment_id}_${detail.year}_${String(detail.month).padStart(2, "0")}.jpg`;
      link.click();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      window.alert(`Не вдалося експортувати JPEG: ${message}`);
    }
  };

  const exportPdf = async () => {
    try {
      const canvas = await captureSheet();
      const { jsPDF } = await import("jspdf");
      const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a5", compress: true });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const margin = 5;
      const maxW = pageW - margin * 2;
      const maxH = pageH - margin * 2;
      const ratio = Math.min(maxW / canvas.width, maxH / canvas.height);
      const drawW = canvas.width * ratio;
      const drawH = canvas.height * ratio;
      const offsetX = (pageW - drawW) / 2;
      const offsetY = (pageH - drawH) / 2;
      pdf.addImage(canvas.toDataURL("image/jpeg", 0.95), "JPEG", offsetX, offsetY, drawW, drawH);
      pdf.save(`faktura_${detail.apartment_id}_${detail.year}_${String(detail.month).padStart(2, "0")}.pdf`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      window.alert(`Не вдалося експортувати PDF: ${message}`);
    }
  };

  return (
    <div className="report-screen">
      <div className="row-actions top-gap">
        <button onClick={printReport} disabled={!detail.calc_locked}>
          Друк фактури (A5 landscape)
        </button>
        <button className="secondary" onClick={exportPdf} disabled={!detail.calc_locked}>
          Експорт PDF
        </button>
        <button className="secondary" onClick={exportJpeg} disabled={!detail.calc_locked}>
          Експорт JPEG
        </button>
      </div>
      {!detail.calc_locked ? (
        <p className="helper top-gap">
          Це чернетковий період. Друк та експорт звіту доступні лише після підтвердження нарахувань.
        </p>
      ) : null}
      {loading ? (
        <div className="skeleton-block top-gap" aria-hidden="true">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      ) : null}
      <div className="report-print-sheet" ref={sheetRef}>
        <div className="report-header">
          <div>
            <h4>ФАКТУРА КОМУНАЛЬНИХ ПОСЛУГ</h4>
            <div className="mini-row">{periodLabel}</div>
          </div>
          <div className="mini-row">Дата формування: {dt(reportGeneratedAt)}</div>
        </div>

        <div className="report-meta">
          <div><strong>Об&apos;єкт:</strong> {detail.address}</div>
          <div><strong>Орендар:</strong> {detail.tenant?.full_name || "відсутній"}</div>
        </div>

        <div className="table-wrap report-table mobile-hide-table">
          <table>
            <thead>
              <tr>
                <th>Послуга</th>
                <th>Попер.</th>
                <th>Поточний</th>
                <th>Різниця</th>
                <th>Тариф</th>
                <th>Сума</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((item) => {
                if (item.type === "group") {
                  return (
                    <tr key={item.key} className="calc-group-row">
                      <td><strong>{item.label}</strong></td>
                      <td></td>
                      <td></td>
                      <td></td>
                      <td></td>
                      <td><strong>{money(item.subtotal)}</strong></td>
                    </tr>
                  );
                }
                const r = item.row;
                return (
                  <tr key={item.key} className={item.childOfGroup ? "calc-child-row" : ""}>
                    <td>{item.childOfGroup ? (r.service_line_label || r.meter_register_label || r.service_name) : r.service_name}</td>
                    <td>{r.previous_reading ?? ""}</td>
                    <td>{r.current_reading ?? ""}</td>
                    <td>{r.difference ?? ""}</td>
                    <td>{money(r.unit_price)}</td>
                    <td>{money(r.amount)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mobile-cards report-mobile-cards">
          {displayRows.map((item) => {
            if (item.type === "group") {
              return (
                <article className="mobile-card" key={item.key}>
                  <div className="mobile-card-title">
                    <strong>{item.label}</strong>
                    <span>{money(item.subtotal)}</span>
                  </div>
                  <div className="mobile-card-meta">Згруповано за багатозонним лічильником</div>
                </article>
              );
            }
            const r = item.row;
            return (
              <article className="mobile-card" key={item.key}>
                <div className="mobile-card-title">
                  <strong>{item.childOfGroup ? (r.service_line_label || r.meter_register_label || r.service_name) : r.service_name}</strong>
                  <span>{money(r.amount)}</span>
                </div>
                <div className="mobile-card-meta">
                  {r.previous_reading ?? "—"} → {r.current_reading ?? "—"} ({r.difference ?? "—"})
                </div>
                <div className="mobile-card-meta">Тариф: {money(r.unit_price)}</div>
              </article>
            );
          })}
        </div>

        <div className="report-totals">
          <div><span>Борг з минулого:</span><strong>{money(detail.utility_balance.previous_month_debt)}</strong></div>
          <div><span>Нараховано (комунальні):</span><strong>{money(utilityAccrual)}</strong></div>
          <div><span>Компенсація:</span><strong>{money(compensationTotal)}</strong></div>
          <div><span>Нараховано разом:</span><strong>{money(accrualWithCompensation || accr)}</strong></div>
          <div>
            <span>Оплачено станом на {dt(reportGeneratedAt)}:</span>
            <strong>{money(reportPayments)}</strong>
          </div>
          <div>
            <span>До сплати станом на {dt(reportGeneratedAt)}:</span>
            <strong>{money(reportBalance)}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}
