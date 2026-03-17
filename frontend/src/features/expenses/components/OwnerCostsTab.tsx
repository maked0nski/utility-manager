import { useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { In, Se, Ta } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";

type OwnerDraft = {
  kind: "owner_cost" | "reimbursement";
  category: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  event_date: string;
};

type MaintenanceDraft = {
  maintenance_type: "planned" | "unplanned";
  title: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  performed_at: string;
};

type CreateMode = "owner_cost" | "maintenance";

export function OwnerCostsTab({
  own,
  setOwn,
  addOwner,
  mnt,
  setMnt,
  addMaint,
  oc,
  mr,
  money,
  dt,
  openOc,
  openMr,
}: {
  own: OwnerDraft;
  setOwn: Dispatch<SetStateAction<OwnerDraft>>;
  addOwner: () => Promise<void>;
  mnt: MaintenanceDraft;
  setMnt: Dispatch<SetStateAction<MaintenanceDraft>>;
  addMaint: () => Promise<void>;
  oc: any[];
  mr: any[];
  money: (v: unknown) => string;
  dt: (x: string | Date | null | undefined) => string;
  openOc: (item: any) => void;
  openMr: (item: any) => void;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const [createMode, setCreateMode] = useState<CreateMode>("owner_cost");

  const journal = useMemo(
    () =>
      [
        ...oc.map((item) => ({
          id: `oc_${item.id}`,
          typeLabel: item.kind === "owner_cost" ? "Витрата" : "Відшкодування",
          name: item.category,
          description: item.description || "",
          amountLabel: `${money(item.amount)} ${item.currency}`,
          sortDate: item.event_date || "",
          dateLabel: dt(item.event_date),
          onEdit: () => openOc(item),
        })),
        ...mr.map((item) => ({
          id: `mr_${item.id}`,
          typeLabel: item.maintenance_type === "planned" ? "Планове обслуговування" : "Позаплановий ремонт",
          name: item.title,
          description: item.description || "",
          amountLabel: item.amount ? `${money(item.amount)} ${item.currency}` : "Без суми",
          sortDate: item.performed_at || "",
          dateLabel: dt(item.performed_at),
          onEdit: () => openMr(item),
        })),
      ].sort((a, b) => String(b.sortDate).localeCompare(String(a.sortDate), "uk")),
    [dt, money, mr, oc, openMr, openOc],
  );

  const submitCreate = async () => {
    if (createMode === "owner_cost") await addOwner();
    else await addMaint();
    setCreateOpen(false);
  };

  return (
    <div className="subcard">
      <div className="title-row">
        <div>
          <h4>Витрати</h4>
          <p className="helper">Один журнал для витрат, відшкодувань і ремонтів. Додавання відкривається у формі, що змінюється за типом запису.</p>
        </div>
        <button type="button" onClick={() => setCreateOpen(true)}>
          Додати запис
        </button>
      </div>

      <div className="table-wrap top-gap">
        <table>
          <thead>
            <tr>
              <th>Тип</th>
              <th>Назва</th>
              <th>Опис</th>
              <th>Сума</th>
              <th>Дата</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {journal.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.typeLabel}</td>
                <td>{entry.name}</td>
                <td>{entry.description || "—"}</td>
                <td>{entry.amountLabel}</td>
                <td>{entry.dateLabel}</td>
                <td>
                  <button className="icon-btn secondary" type="button" onClick={entry.onEdit}>
                    ✎
                  </button>
                </td>
              </tr>
            ))}
            {journal.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <span className="helper">Журнал витрат поки порожній.</span>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {createOpen ? (
        <Modal title={createMode === "owner_cost" ? "Новий запис витрат" : "Новий запис ремонту"} onClose={() => setCreateOpen(false)}>
          <div className="owner-expense-modal">
            <Se
              tip="Тип запису"
              value={createMode}
              help="Оберіть, що саме додаєте. Форма нижче зміниться автоматично."
              onChange={(e) => setCreateMode(e.target.value as CreateMode)}
            >
              <option value="owner_cost">Витрата або відшкодування</option>
              <option value="maintenance">Ремонт або обслуговування</option>
            </Se>

            {createMode === "owner_cost" ? (
              <div className="forms-grid compact-grid">
                <Se
                  tip="Тип операції"
                  value={own.kind}
                  help="Витрата враховується як кошти власника, відшкодування показує повернення коштів."
                  onChange={(e) => setOwn((s) => ({ ...s, kind: e.target.value as OwnerDraft["kind"] }))}
                >
                  <option value="owner_cost">Витрата</option>
                  <option value="reimbursement">Відшкодування</option>
                </Se>
                <In
                  tip="Категорія"
                  placeholder="Наприклад: клінінг, інтернет, дрібний ремонт"
                  help="Коротка назва, за якою зручно буде шукати запис у журналі."
                  value={own.category}
                  onChange={(e) => setOwn((s) => ({ ...s, category: e.target.value }))}
                />
                <Ta
                  tip="Опис"
                  placeholder="Що саме було оплачено або відшкодовано"
                  help="Можна вказати деталі робіт, причину платежу або примітку для себе."
                  value={own.description}
                  onChange={(e) => setOwn((s) => ({ ...s, description: e.target.value }))}
                />
                <In
                  tip="Сума"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  help="Введіть фактичну суму платежу."
                  value={own.amount}
                  onChange={(e) => setOwn((s) => ({ ...s, amount: e.target.value }))}
                />
                <Se tip="Валюта" value={own.currency} onChange={(e) => setOwn((s) => ({ ...s, currency: e.target.value as OwnerDraft["currency"] }))}>
                  <option value="UAH">UAH</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </Se>
                <In
                  tip="Дата операції"
                  type="date"
                  help="Дата фактичного платежу або відшкодування."
                  value={own.event_date}
                  onChange={(e) => setOwn((s) => ({ ...s, event_date: e.target.value }))}
                />
              </div>
            ) : (
              <div className="forms-grid compact-grid">
                <Se
                  tip="Тип робіт"
                  value={mnt.maintenance_type}
                  help="Планове обслуговування для регулярних робіт, позаплановий ремонт для аварійних або разових задач."
                  onChange={(e) => setMnt((s) => ({ ...s, maintenance_type: e.target.value as MaintenanceDraft["maintenance_type"] }))}
                >
                  <option value="planned">Планове обслуговування</option>
                  <option value="unplanned">Позаплановий ремонт</option>
                </Se>
                <In
                  tip="Назва робіт"
                  placeholder="Наприклад: сервіс котла"
                  help="Короткий заголовок, який буде видно в журналі."
                  value={mnt.title}
                  onChange={(e) => setMnt((s) => ({ ...s, title: e.target.value }))}
                />
                <Ta
                  tip="Опис робіт"
                  placeholder="Що зробили, хто виконував, які є домовленості"
                  help="Корисно зазначити деталі, які знадобляться при наступному сервісі."
                  value={mnt.description}
                  onChange={(e) => setMnt((s) => ({ ...s, description: e.target.value }))}
                />
                <In
                  tip="Сума"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  help="Поле можна лишити порожнім, якщо сума ще невідома."
                  value={mnt.amount}
                  onChange={(e) => setMnt((s) => ({ ...s, amount: e.target.value }))}
                />
                <Se tip="Валюта" value={mnt.currency} onChange={(e) => setMnt((s) => ({ ...s, currency: e.target.value as MaintenanceDraft["currency"] }))}>
                  <option value="UAH">UAH</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </Se>
                <In
                  tip="Дата виконання"
                  type="date"
                  help="Дата, коли роботи реально були виконані."
                  value={mnt.performed_at}
                  onChange={(e) => setMnt((s) => ({ ...s, performed_at: e.target.value }))}
                />
              </div>
            )}

            <div className="row-actions top-gap">
              <button type="button" onClick={submitCreate}>
                Зберегти запис
              </button>
              <button type="button" className="secondary" onClick={() => setCreateOpen(false)}>
                Скасувати
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
