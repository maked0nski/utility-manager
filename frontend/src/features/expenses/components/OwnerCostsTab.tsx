import { In, Se, Ta } from "@/shared/ui/form-controls";
import type { Dispatch, SetStateAction } from "react";

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
  return (
    <div className="forms-grid">
      <div className="subcard">
        <h4>Додати витрату/відшкодування</h4>
        <Se tip="Тип операції" value={own.kind} onChange={(e) => setOwn((s) => ({ ...s, kind: e.target.value }))}>
          <option value="owner_cost">Витрата власника</option>
          <option value="reimbursement">Відшкодування орендарю</option>
        </Se>
        <In tip="Категорія витрати" placeholder="Категорія" value={own.category} onChange={(e) => setOwn((s) => ({ ...s, category: e.target.value }))} />
        <In tip="Опис витрати" placeholder="Опис" value={own.description} onChange={(e) => setOwn((s) => ({ ...s, description: e.target.value }))} />
        <In tip="Сума витрати" placeholder="Сума" value={own.amount} onChange={(e) => setOwn((s) => ({ ...s, amount: e.target.value }))} />
        <Se tip="Валюта операції" value={own.currency} onChange={(e) => setOwn((s) => ({ ...s, currency: e.target.value }))}>
          <option value="UAH">UAH</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
        </Se>
        <In tip="Дата операції" type="date" value={own.event_date} onChange={(e) => setOwn((s) => ({ ...s, event_date: e.target.value }))} />
        <button onClick={addOwner}>Зберегти</button>
      </div>
      <div className="subcard">
        <h4>Додати ремонт/обслуговування</h4>
        <Se tip="Плановість робіт" value={mnt.maintenance_type} onChange={(e) => setMnt((s) => ({ ...s, maintenance_type: e.target.value }))}>
          <option value="planned">Плановий</option>
          <option value="unplanned">Неплановий</option>
        </Se>
        <In tip="Назва робіт" placeholder="Назва" value={mnt.title} onChange={(e) => setMnt((s) => ({ ...s, title: e.target.value }))} />
        <Ta tip="Опис робіт" placeholder="Опис" value={mnt.description} onChange={(e) => setMnt((s) => ({ ...s, description: e.target.value }))} />
        <In tip="Сума робіт" placeholder="Сума" value={mnt.amount} onChange={(e) => setMnt((s) => ({ ...s, amount: e.target.value }))} />
        <Se tip="Валюта робіт" value={mnt.currency} onChange={(e) => setMnt((s) => ({ ...s, currency: e.target.value }))}>
          <option value="UAH">UAH</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
        </Se>
        <In tip="Дата виконання" type="date" value={mnt.performed_at} onChange={(e) => setMnt((s) => ({ ...s, performed_at: e.target.value }))} />
        <button onClick={addMaint}>Зберегти</button>
      </div>
      <div className="subcard full-row">
        <h4>Журнал витрат</h4>
        <div className="table-wrap">
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
              {oc.map((x) => (
                <tr key={`oc_${x.id}`}>
                  <td>{x.kind === "owner_cost" ? "Витрата власника" : "Відшкодування"}</td>
                  <td>{x.category}</td>
                  <td>{x.description || ""}</td>
                  <td>
                    {money(x.amount)} {x.currency}
                  </td>
                  <td>{dt(x.event_date)}</td>
                  <td>
                    <button className="icon-btn" onClick={() => openOc(x)}>
                      ✎
                    </button>
                  </td>
                </tr>
              ))}
              {mr.map((x) => (
                <tr key={`mr_${x.id}`}>
                  <td>{x.maintenance_type === "planned" ? "Плановий" : "Неплановий"}</td>
                  <td>{x.title}</td>
                  <td>{x.description || ""}</td>
                  <td>{x.amount ? `${money(x.amount)} ${x.currency}` : ""}</td>
                  <td>{dt(x.performed_at)}</td>
                  <td>
                    <button className="icon-btn" onClick={() => openMr(x)}>
                      ✎
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
