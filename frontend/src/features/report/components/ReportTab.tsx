import { useRef } from "react";
import { todayIso } from "@/shared/utils/date";
import type { CalculationRow } from "@/shared/api/types";

type DetailLike = {
  apartment_id: number;
  year: number;
  month: number;
  address: string;
  tenant?: { full_name?: string } | null;
  utility_balance: {
    previous_month_debt: string;
    month_payments: string;
    current_balance: string;
  };
};

export function ReportTab({
  detail,
  money,
  dt,
  accr,
  rows,
  periodLabel,
}: {
  detail: DetailLike;
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  accr: number;
  rows: CalculationRow[];
  periodLabel: string;
}) {
  const sheetRef = useRef<HTMLDivElement | null>(null);

  const printReport = () => {
    window.print();
  };

  const captureSheet = async () => {
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
        <button onClick={printReport}>Друк фактури (A5 landscape)</button>
        <button className="secondary" onClick={exportPdf}>
          Експорт PDF
        </button>
        <button className="secondary" onClick={exportJpeg}>
          Експорт JPEG
        </button>
      </div>
      <div className="report-print-sheet" ref={sheetRef}>
        <div className="report-header">
          <div>
            <h4>ФАКТУРА КОМУНАЛЬНИХ ПОСЛУГ</h4>
            <div className="mini-row">{periodLabel}</div>
          </div>
          <div className="mini-row">Дата формування: {dt(todayIso())}</div>
        </div>

        <div className="report-meta">
          <div><strong>Об&apos;єкт:</strong> {detail.address}</div>
          <div><strong>Орендар:</strong> {detail.tenant?.full_name || "відсутній"}</div>
        </div>

        <div className="table-wrap report-table">
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
              {(rows || []).map((r, idx) => (
                <tr key={`${r.service_name}_${idx}`}>
                  <td>{r.service_name}</td>
                  <td>{r.previous_reading ?? ""}</td>
                  <td>{r.current_reading ?? ""}</td>
                  <td>{r.difference ?? ""}</td>
                  <td>{money(r.unit_price)}</td>
                  <td>{money(r.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="report-totals">
          <div><span>Борг з минулого:</span><strong>{money(detail.utility_balance.previous_month_debt)}</strong></div>
          <div><span>Нараховано:</span><strong>{money(accr)}</strong></div>
          <div><span>Оплачено:</span><strong>{money(detail.utility_balance.month_payments)}</strong></div>
          <div><span>До сплати (борг на зараз):</span><strong>{money(detail.utility_balance.current_balance)}</strong></div>
        </div>
      </div>
    </div>
  );
}
