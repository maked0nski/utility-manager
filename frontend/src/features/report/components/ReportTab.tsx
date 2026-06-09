import { useMemo, useRef, useState } from "react";
import { todayIso } from "@/shared/utils/date";
import type { BillingPeriodSummaryItem, CalculationRow } from "@/shared/api/types";

const REPORT_EXPORT_SAFE_CSS = `
[data-report-export-root="true"] {
  background: #ffffff !important;
  color: #0f172a !important;
  border-color: #d7dde6 !important;
  box-shadow: none !important;
  filter: none !important;
}
[data-report-export-root="true"] * {
  color: #0f172a !important;
  border-color: #d7dde6 !important;
  box-shadow: none !important;
  text-shadow: none !important;
  filter: none !important;
}
[data-report-export-root="true"] .report-print-sheet,
[data-report-export-root="true"].report-print-sheet,
[data-report-export-root="true"] .subcard,
[data-report-export-root="true"] .mobile-card,
[data-report-export-root="true"] .report-totals > div,
[data-report-export-root="true"] .calc-group-row,
[data-report-export-root="true"] .calc-child-row {
  background: #ffffff !important;
}
[data-report-export-root="true"] .calc-group-row {
  background: #f3f6fb !important;
}
[data-report-export-root="true"] .calc-child-row {
  background: #fafbfc !important;
}
[data-report-export-root="true"] table,
[data-report-export-root="true"] th,
[data-report-export-root="true"] td {
  background: #ffffff !important;
  border-color: #d7dde6 !important;
}
[data-report-export-root="true"] [data-report-history="true"] {
  display: none !important;
}
`;

type DetailLike = {
  apartment_id: number;
  year: number;
  month: number;
  address: string;
  calc_locked?: boolean;
  tenant?: { full_name?: string } | null;
  billing_period_summary?: BillingPeriodSummaryItem | null;
  utility_balance: {
    previous_month_debt: string;
    month_payments: string;
    current_balance: string;
    actual_current_balance?: string;
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
  prepareStatement,
  sendStatement,
}: {
  detail: DetailLike;
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  loading?: boolean;
  accr: number;
  rows: CalculationRow[];
  periodLabel: string;
  prepareStatement: () => Promise<void>;
  sendStatement: (statementId: number) => Promise<void>;
}) {
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const [compactVersion, setCompactVersion] = useState(true);
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
  const snapshot = detail.billing_period_summary?.month_snapshot || null;
  const statement = detail.billing_period_summary?.current_statement || null;
  const statements = detail.billing_period_summary?.statements || [];
  const monthOpening = snapshot?.opening_balance ?? detail.utility_balance.previous_month_debt;
  const monthPayments = snapshot?.payments_in_month ?? detail.utility_balance.month_payments;
  const monthClosing = snapshot?.closing_balance ?? detail.utility_balance.current_balance;
  const monthAccrual = snapshot?.utility_accrual ?? String(utilityAccrual);
  const monthCompensation = snapshot?.compensation_total ?? String(Math.abs(compensationTotal));
  const monthTotal = snapshot?.month_total ?? String(accrualWithCompensation || accr);
  const reportGeneratedAt = statement?.generated_at || todayIso();
  const reportPayments = statement?.payments_after_month_to_generated_at ?? "0.00";
  const reportBalance = statement?.balance_due_on_generated_at ?? monthClosing;
  const statementStatusLabel = (status?: string | null) => {
    if (status === "sent") return "Відправлено";
    if (status === "prepared") return "Підготовлено";
    if (status === "draft") return "Чернетка";
    if (status === "cancelled") return "Скасовано";
    return "Ще не сформовано";
  };

  const printReport = () => {
    if (!detail.calc_locked) return;
    window.print();
  };

  const captureSheet = async () => {
    if (!detail.calc_locked) {
      throw new Error("Експорт доступний лише для підтверджених нарахувань.");
    }
    if (!sheetRef.current) throw new Error("Не знайдено блок фактури.");
    sheetRef.current.setAttribute("data-report-export-root", "true");
    if (compactVersion) sheetRef.current.setAttribute("data-report-compact", "true");
    const { default: html2canvas } = await import("html2canvas");
    try {
      return await html2canvas(sheetRef.current, {
        scale: 2,
        backgroundColor: "#ffffff",
        useCORS: true,
        onclone: (clonedDocument) => {
          const style = clonedDocument.createElement("style");
          style.textContent = REPORT_EXPORT_SAFE_CSS;
          clonedDocument.head.appendChild(style);
        },
      });
    } finally {
      sheetRef.current.removeAttribute("data-report-export-root");
      sheetRef.current.removeAttribute("data-report-compact");
    }
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
        <label className="report-version-toggle">
          <input
            type="checkbox"
            checked={compactVersion}
            onChange={(event) => setCompactVersion(event.target.checked)}
          />
          <span>Скорочена версія</span>
        </label>
        <button onClick={() => void prepareStatement()} disabled={!detail.calc_locked}>
          Підготувати рахунок
        </button>
        <button
          className="secondary"
          onClick={() => {
            if (statement?.id) void sendStatement(statement.id);
          }}
          disabled={!statement?.id}
        >
          Позначити як відправлений
        </button>
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
      <div className="report-print-sheet" ref={sheetRef} data-report-compact={compactVersion ? "true" : "false"}>
        <div className="report-header">
          <div>
            <h4>РОЗРАХУНОК КОМУНАЛЬНИХ ПОСЛУГ</h4>
            <div className="mini-row">{periodLabel}</div>
          </div>
          <div className="mini-row">Дата формування: {dt(reportGeneratedAt)}</div>
        </div>

        <div className="report-meta">
          <div><strong>Об&apos;єкт:</strong> {detail.address}</div>
          {!compactVersion ? <div><strong>Орендар:</strong> {detail.tenant?.full_name || "відсутній"}</div> : null}
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

        {compactVersion ? (
          <div className="report-totals report-totals-compact">
            <div><span>Разом за місяць:</span><strong>{money(monthTotal)}</strong></div>
            <div><span>Отримано після закриття місяця:</span><strong>{money(reportPayments)}</strong></div>
            <div><span>До сплати:</span><strong>{money(reportBalance)}</strong></div>
          </div>
        ) : (
          <>
            <div className="report-totals">
              <div><span>Борг на початок місяця:</span><strong>{money(monthOpening)}</strong></div>
              <div><span>Нараховано (комунальні):</span><strong>{money(monthAccrual)}</strong></div>
              <div><span>Компенсації / відшкодування:</span><strong>{money(`-${monthCompensation}`)}</strong></div>
              <div><span>Разом за місяць:</span><strong>{money(monthTotal)}</strong></div>
              <div><span>Оплачено в місяці:</span><strong>{money(monthPayments)}</strong></div>
              <div><span>Борг на кінець місяця:</span><strong>{money(monthClosing)}</strong></div>
            </div>
            <div className="report-totals top-gap">
              <div>
                <span>Статус рахунку:</span>
                <strong>{statementStatusLabel(statement?.status)}</strong>
              </div>
              <div>
                <span>Дата формування рахунку:</span>
                <strong>{dt(reportGeneratedAt)}</strong>
              </div>
              <div>
                <span>Отримано після закриття місяця:</span>
                <strong>{money(reportPayments)}</strong>
              </div>
              <div>
                <span>До сплати станом на {dt(reportGeneratedAt)}:</span>
                <strong>{money(reportBalance)}</strong>
              </div>
            </div>
          </>
        )}
        <div className="subcard top-gap" data-report-history="true">
          <h4>Історія рахунків за місяць</h4>
          {!statements.length ? (
            <p className="helper">Рахунок для цього місяця ще не формувався.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Версія</th>
                    <th>Статус</th>
                    <th>Сформовано</th>
                    <th>Відправлено</th>
                    <th>До сплати</th>
                  </tr>
                </thead>
                <tbody>
                  {statements.map((item) => (
                    <tr key={item.id}>
                      <td>#{item.version}</td>
                      <td>{statementStatusLabel(item.status)}</td>
                      <td>{dt(item.generated_at)}</td>
                      <td>{dt(item.sent_at)}</td>
                      <td>{money(item.balance_due_on_generated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
