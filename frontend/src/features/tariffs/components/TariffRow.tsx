import { dt, money, unitLabel } from "@/shared/utils/format";

type TariffRowData = {
  service_name: string;
  price_per_unit: string | number;
  unit_name: string;
  personal_account?: string | null;
  is_active_for_period?: boolean;
  last_tariff_check_at?: string | null;
};

export const TariffRow = ({ row, open }: { row: TariffRowData; open: (row: TariffRowData) => void }) => (
  <tr>
    <td>{row.service_name}</td>
    <td>{money(row.price_per_unit)}</td>
    <td>{unitLabel(row.unit_name)}</td>
    <td>{row.personal_account || ""}</td>
    <td>{row.is_active_for_period ? "Активна" : "Неактивна"}</td>
    <td>{dt(row.last_tariff_check_at)}</td>
    <td>
      <button className="icon-btn" onClick={() => open(row)}>
        ✎
      </button>
    </td>
  </tr>
);
