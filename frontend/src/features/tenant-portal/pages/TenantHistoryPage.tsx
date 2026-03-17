import { useNavigate } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";
import { money, periodLabel } from "@/shared/utils/format";
import { localizeApiError } from "@/features/tenant-portal/utils";
import type { TenantHistory } from "@/shared/api/types";

function positiveAmount(value: string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return money(value);
  return money(Math.max(numeric, 0));
}

export function TenantHistoryPage({ history }: { history: UseQueryResult<TenantHistory, Error> }) {
  const navigate = useNavigate();

  return (
    <section className="tenant-card">
      <h2>Історія рахунків</h2>
      {history.isLoading ? <p className="tenant-muted">Завантаження історії...</p> : null}
      {history.isError ? (
        <div className="tenant-error-box">
          <p>{localizeApiError(history.error, "Не вдалося завантажити історію рахунків.")}</p>
          <button className="btn-primary" onClick={() => history.refetch()}>Повторити</button>
        </div>
      ) : null}
      {!history.isLoading && !history.isError && !(history.data?.invoices || []).length ? <p className="tenant-muted">Історія рахунків поки порожня.</p> : null}
      {(history.data?.invoices || []).length ? (
        <div className="tenant-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Період</th>
                <th>Нараховано</th>
                <th>До оплати</th>
                <th>Оплачено</th>
                <th>Борг</th>
                <th>Переплата</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(history.data?.invoices || []).map((invoice) => (
                <tr key={invoice.id}>
                  <td>{periodLabel(invoice.year, invoice.month)}</td>
                  <td>{money(invoice.total_amount)}</td>
                  <td>{money(Number(invoice.carry_over_debt || 0) + Number(invoice.total_amount || 0))}</td>
                  <td>{money(invoice.utility_payment_received)}</td>
                  <td>{positiveAmount(invoice.closing_balance)}</td>
                  <td>{positiveAmount(String(-Number(invoice.closing_balance || 0)))}</td>
                  <td><button className="tenant-link-btn" onClick={() => navigate(`/history/${invoice.id}`)}>Деталі</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
