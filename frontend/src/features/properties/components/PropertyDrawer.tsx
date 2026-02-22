import { In } from "@/shared/ui/form-controls";
import type { Dispatch, SetStateAction } from "react";

type ApartmentItem = {
  apartment_id: number;
  code?: string;
  address?: string;
  total_balance?: string | number;
};

export function PropertyDrawer({
  drawer,
  setDrawer,
  addProp,
  setAddProp,
  apartmentsQuery,
  ap,
  setAp,
  createAp,
  totals,
  money,
  props,
  sel,
  setSel,
}: {
  drawer: boolean;
  setDrawer: (v: boolean) => void;
  addProp: boolean;
  setAddProp: Dispatch<SetStateAction<boolean>>;
  apartmentsQuery: { refetch: () => Promise<unknown> };
  ap: { address: string };
  setAp: Dispatch<SetStateAction<{ address: string }>>;
  createAp: () => Promise<void>;
  totals: { utility: number; rent: number; total: number };
  money: (v: unknown) => string;
  props: ApartmentItem[];
  sel: ApartmentItem | null;
  setSel: (v: ApartmentItem) => void;
}) {
  return (
    <>
      {drawer && (
        <div
          className="drawer-backdrop"
          onClick={() => {
            setDrawer(false);
            setAddProp(false);
          }}
        />
      )}
      <div className={`property-drawer ${drawer ? "open" : ""}`}>
        <div className="drawer-card">
          <div className="title-row">
            <h3>Нерухомість</h3>
            <div className="row-actions">
              <button className="secondary" onClick={() => apartmentsQuery.refetch()}>
                Оновити
              </button>
              <button onClick={() => setAddProp((s) => !s)}>Додати</button>
            </div>
          </div>
          {addProp && (
            <div className="subcard">
              <In
                tip="Адреса нерухомості"
                placeholder="Адреса"
                value={ap.address}
                onChange={(e) => setAp((s) => ({ ...s, address: e.target.value }))}
              />
              <div className="row-actions">
                <button onClick={createAp}>Створити</button>
                <button className="secondary" onClick={() => setAddProp(false)}>
                  Скасувати
                </button>
              </div>
            </div>
          )}
          <p className="helper">
            Комуналка: {money(totals.utility)} | Оренда: {money(totals.rent)} | Разом:{" "}
            {money(totals.total)}
          </p>
          <div className="property-list">
            {props.map((x) => (
              <button
                key={x.apartment_id}
                className={`property-item ${sel?.apartment_id === x.apartment_id ? "active" : ""}`}
                onClick={() => {
                  setSel(x);
                  setDrawer(false);
                  setAddProp(false);
                }}
              >
                <div className="title-row">
                  <strong>{x.code}</strong>
                  <span className="badge">{money(x.total_balance)}</span>
                </div>
                <div className="addr">{x.address}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
