import { useNavigate, useParams } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";
import { money, periodLabel } from "@/shared/utils/format";
import { invoiceStatusLabel, localizeApiError } from "@/features/tenant-portal/utils";
import type { TenantHistory } from "@/shared/api/types";

export function TenantInvoiceDetailsPage({ history }: { history: UseQueryResult<TenantHistory, Error> }) {
  const navigate = useNavigate();
  const params = useParams<{ invoiceId: string }>();
  const invoiceId = Number(params.invoiceId || 0);
  const invoice = (history.data?.invoices || []).find((x) => x.id === invoiceId);

  if (history.isLoading) {
    return <section className="tenant-card"><p className="tenant-muted">Завантаження рахунку...</p></section>;
  }

  if (history.isError) {
    return (
      <section className="tenant-card">
        <div className="tenant-error-box">
          <p>{localizeApiError(history.error, "Не вдалося завантажити рахунок.")}</p>
          <button className="btn-primary" onClick={() => history.refetch()}>Повторити</button>
        </div>
      </section>
    );
  }

  if (!invoice) {
    return (
      <section className="tenant-card">
        <p className="tenant-muted">Рахунок не знайдено.</p>
        <button className="tenant-link-btn" onClick={() => navigate("/history")}>Назад до історії</button>
      </section>
    );
  }

  return (
    <section className="tenant-card">
      <h2>Рахунок за {periodLabel(invoice.year, invoice.month)}</h2>
      <div className="tenant-summary-grid">
        <div className="tenant-summary-card">
          <span>Нараховано</span>
          <strong>{money(invoice.total_amount)} грн</strong>
        </div>
        <div className="tenant-summary-card">
          <span>Баланс</span>
          <strong>{money(invoice.closing_balance)} грн</strong>
        </div>
        <div className="tenant-summary-card">
          <span>Статус</span>
          <strong>{invoiceStatusLabel(invoice.status)}</strong>
        </div>
      </div>
      {invoice.items?.length ? (
        <div className="tenant-table-wrap">
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
              {invoice.items.map((item, index) => (
                <tr key={`${invoice.id}-${item.service_name}-${index}`}>
                  <td>{item.service_name}</td>
                  <td>{item.consumption} {item.unit_name}</td>
                  <td>{money(item.unit_price)}</td>
                  <td>{money(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="tenant-muted">Для цього періоду деталізація відсутня.</p>
      )}
      <button className="tenant-link-btn" onClick={() => navigate("/history")}>Назад до історії</button>
    </section>
  );
}
