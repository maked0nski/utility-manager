import { useMemo, useState } from "react";
import { In, Se } from "@/shared/ui/form-controls";
import type { UtilityPaymentItem } from "@/shared/api/types";

type PaymentFormState = {
  amount: string;
  paid_at: string;
  note: string;
  payer_type: "tenant" | "owner";
  tenant_id: string;
};

const emptyForm = (today = ""): PaymentFormState => ({
  amount: "",
  paid_at: today,
  note: "",
  payer_type: "tenant",
  tenant_id: "",
});

const matchesPeriodByPaidAt = (paidAt: string, selectedPeriod: { year: number; month: number }) => {
  if (!paidAt) return false;
  const [year, month] = paidAt.split("-").map(Number);
  return year === selectedPeriod.year && month === selectedPeriod.month;
};

export function PaymentsTab({
  money,
  dt,
  payments,
  loading,
  tenants,
  defaultPaidAt,
  selectedPeriod,
  createPayment,
  updatePayment,
  deletePayment,
}: {
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  payments: UtilityPaymentItem[];
  loading?: boolean;
  tenants: Array<{ id: number; full_name: string }>;
  defaultPaidAt: string;
  selectedPeriod: { year: number; month: number };
  createPayment: (payload: {
    amount: number;
    paid_at: string;
    note: string | null;
    payer_type: "tenant" | "owner";
    tenant_id: number | null;
  }) => Promise<void>;
  updatePayment: (
    paymentId: number,
    payload: {
      amount: number;
      paid_at: string;
      note: string | null;
      payer_type: "tenant" | "owner";
      tenant_id: number | null;
    },
  ) => Promise<void>;
  deletePayment: (paymentId: number) => Promise<void>;
}) {
  const [form, setForm] = useState<PaymentFormState>(emptyForm(defaultPaidAt));
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<PaymentFormState>(emptyForm(defaultPaidAt));

  const sortedPayments = useMemo(
    () =>
      [...payments].sort((a, b) => {
        const dateCmp = String(b.paid_at || "").localeCompare(String(a.paid_at || ""));
        if (dateCmp !== 0) return dateCmp;
        return b.id - a.id;
      }),
    [payments],
  );

  const monthPaidTotal = useMemo(
    () =>
      sortedPayments
        .filter((row) => matchesPeriodByPaidAt(row.paid_at, selectedPeriod))
        .reduce((sum, row) => sum + Number(row.amount || 0), 0),
    [selectedPeriod, sortedPayments],
  );

  const totalPaid = useMemo(
    () => sortedPayments.reduce((sum, row) => sum + Number(row.amount || 0), 0),
    [sortedPayments],
  );

  const latestPayment = sortedPayments[0] || null;

  const startEdit = (row: UtilityPaymentItem) => {
    setEditingId(row.id);
    setEditForm({
      amount: String(row.amount || ""),
      paid_at: row.paid_at,
      note: row.note || "",
      payer_type: row.payer_type || "tenant",
      tenant_id: row.tenant_id ? String(row.tenant_id) : "",
    });
  };

  return (
    <div className="forms-grid tab-pane-grid">
      <div className="subcard full-row">
        <h4>Журнал оплат по квартирі</h4>
        <div className="summary-grid tab-pane-kpi">
          <div className="metric">
            <div className="label">Оплати за обраний місяць</div>
            <div className="value">{money(monthPaidTotal)}</div>
          </div>
          <div className="metric">
            <div className="label">Остання оплата</div>
            <div className="value">{latestPayment ? money(latestPayment.amount) : "—"}</div>
            <small>{latestPayment ? dt(latestPayment.paid_at) : "Ще немає оплат"}</small>
          </div>
          <div className="metric">
            <div className="label">Усього оплат</div>
            <div className="value">{money(totalPaid)}</div>
          </div>
        </div>
        <p className="helper">
          Тут показується повний список усіх оплат по квартирі. Оплата потрапляє в баланс за фактичною датою
          отримання.
        </p>
      </div>
      <div className="subcard full-row">
        <h4>Нова оплата</h4>
        <div className="forms-grid compact-grid">
          <In
            tip="Сума"
            type="number"
            min="0.01"
            step="0.01"
            value={form.amount}
            onChange={(e) => setForm((s) => ({ ...s, amount: e.target.value }))}
          />
          <In
            tip="Дата отримання"
            help="Саме ця дата визначає, в який місяць потрапить оплата."
            type="date"
            value={form.paid_at}
            onChange={(e) => setForm((s) => ({ ...s, paid_at: e.target.value }))}
          />
          <Se
            tip="Платник"
            value={form.payer_type}
            onChange={(e) =>
              setForm((s) => ({
                ...s,
                payer_type: e.target.value as "tenant" | "owner",
                tenant_id: e.target.value === "owner" ? "" : s.tenant_id,
              }))
            }
          >
            <option value="tenant">Орендар</option>
            <option value="owner">Власник</option>
          </Se>
          <Se
            tip="Орендар"
            value={form.tenant_id}
            disabled={form.payer_type !== "tenant"}
            onChange={(e) => setForm((s) => ({ ...s, tenant_id: e.target.value }))}
          >
            <option value="">Автовизначення</option>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.full_name}
              </option>
            ))}
          </Se>
          <In
            tip="Примітка"
            value={form.note}
            onChange={(e) => setForm((s) => ({ ...s, note: e.target.value }))}
          />
        </div>
        <div className="row-actions">
          <button
            onClick={async () => {
              await createPayment({
                amount: Number(form.amount || 0),
                paid_at: form.paid_at,
                note: form.note.trim() || null,
                payer_type: form.payer_type,
                tenant_id: form.payer_type === "tenant" && form.tenant_id ? Number(form.tenant_id) : null,
              });
              setForm(emptyForm(defaultPaidAt));
            }}
          >
            Додати оплату
          </button>
        </div>
      </div>
      <div className="subcard full-row">
        <h4>Усі оплати</h4>
        {loading ? (
          <div className="skeleton-block" aria-hidden="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}
        <div className="table-wrap mobile-hide-table">
          <table>
            <thead>
              <tr>
                <th>Дата отримання</th>
                <th>Сума</th>
                <th>Платник</th>
                <th>Примітка</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {payments.length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <span className="helper">Оплат по квартирі ще немає.</span>
                  </td>
                </tr>
              )}
              {sortedPayments.map((row) => {
                const editing = editingId === row.id;
                return (
                  <tr key={row.id}>
                    <td>
                      {editing ? (
                        <In
                          tip="Дата отримання"
                          type="date"
                          value={editForm.paid_at}
                          onChange={(e) => setEditForm((s) => ({ ...s, paid_at: e.target.value }))}
                        />
                      ) : (
                        dt(row.paid_at)
                      )}
                    </td>
                    <td>
                      {editing ? (
                        <In
                          tip="Сума"
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={editForm.amount}
                          onChange={(e) => setEditForm((s) => ({ ...s, amount: e.target.value }))}
                        />
                      ) : (
                        money(row.amount)
                      )}
                    </td>
                    <td>
                      {editing ? (
                        <div className="forms-grid compact-grid">
                          <Se
                            tip="Платник"
                            value={editForm.payer_type}
                            onChange={(e) =>
                              setEditForm((s) => ({
                                ...s,
                                payer_type: e.target.value as "tenant" | "owner",
                                tenant_id: e.target.value === "owner" ? "" : s.tenant_id,
                              }))
                            }
                          >
                            <option value="tenant">Орендар</option>
                            <option value="owner">Власник</option>
                          </Se>
                          <Se
                            tip="Орендар"
                            value={editForm.tenant_id}
                            disabled={editForm.payer_type !== "tenant"}
                            onChange={(e) => setEditForm((s) => ({ ...s, tenant_id: e.target.value }))}
                          >
                            <option value="">Автовизначення</option>
                            {tenants.map((tenant) => (
                              <option key={tenant.id} value={tenant.id}>
                                {tenant.full_name}
                              </option>
                            ))}
                          </Se>
                        </div>
                      ) : row.payer_type === "owner" ? (
                        "Власник"
                      ) : (
                        row.tenant_name || "Орендар"
                      )}
                    </td>
                    <td>
                      {editing ? (
                        <In
                          tip="Примітка"
                          value={editForm.note}
                          onChange={(e) => setEditForm((s) => ({ ...s, note: e.target.value }))}
                        />
                      ) : (
                        row.note || "—"
                      )}
                    </td>
                    <td>
                      {editing ? (
                        <div className="row-actions">
                          <button
                            onClick={async () => {
                              await updatePayment(row.id, {
                                amount: Number(editForm.amount || 0),
                                paid_at: editForm.paid_at,
                                note: editForm.note.trim() || null,
                                payer_type: editForm.payer_type,
                                tenant_id:
                                  editForm.payer_type === "tenant" && editForm.tenant_id
                                    ? Number(editForm.tenant_id)
                                    : null,
                              });
                              setEditingId(null);
                            }}
                          >
                            Зберегти
                          </button>
                          <button className="secondary" onClick={() => setEditingId(null)}>
                            Скасувати
                          </button>
                        </div>
                      ) : (
                        <div className="row-actions">
                          <button className="secondary" onClick={() => startEdit(row)}>
                            Змінити
                          </button>
                          <button className="danger" onClick={() => deletePayment(row.id)}>
                            Видалити
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mobile-cards">
          {payments.length === 0 && !loading ? <span className="helper">Оплат по квартирі ще немає.</span> : null}
          {sortedPayments.map((row) => {
            const editing = editingId === row.id;
            return (
              <article className="mobile-card" key={`mobile-${row.id}`}>
                <div className="mobile-card-title">
                  <strong>{dt(row.paid_at)}</strong>
                  <span>{money(row.amount)}</span>
                </div>
                <div className="mobile-card-meta">
                  {row.payer_type === "owner" ? "Власник" : row.tenant_name || "Орендар"}
                </div>
                <div className="mobile-card-meta">{row.note || "—"}</div>
                {editing ? (
                  <div className="row-actions top-gap">
                    <button
                      onClick={async () => {
                        await updatePayment(row.id, {
                          amount: Number(editForm.amount || 0),
                          paid_at: editForm.paid_at,
                          note: editForm.note.trim() || null,
                          payer_type: editForm.payer_type,
                          tenant_id: editForm.payer_type === "tenant" && editForm.tenant_id ? Number(editForm.tenant_id) : null,
                        });
                        setEditingId(null);
                      }}
                    >
                      Зберегти
                    </button>
                    <button className="secondary" onClick={() => setEditingId(null)}>
                      Скасувати
                    </button>
                  </div>
                ) : (
                  <div className="row-actions top-gap">
                    <button className="secondary" onClick={() => startEdit(row)}>
                      Змінити
                    </button>
                    <button className="danger" onClick={() => deletePayment(row.id)}>
                      Видалити
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
