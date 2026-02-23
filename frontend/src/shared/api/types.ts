export type ApiPrimitive = string | number | boolean | null;
export type ApiValue = ApiPrimitive | ApiValue[] | { [key: string]: ApiValue };

export interface ApiErrorPayload {
  detail?: string;
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | Record<string, unknown> | null;
}

export interface UtilityBalance {
  previous_month_debt: string;
  month_charges: string;
  month_payments: string;
  month_payment_date?: string | null;
  month_payment_note?: string | null;
  current_balance: string;
}

export interface CalculationRow {
  meter_id: number | null;
  service_name: string;
  meter_register?: string;
  previous_reading: string | null;
  current_reading: string | null;
  difference: string | null;
  unit_name: string;
  unit_price: string;
  amount: string;
  can_edit_previous?: boolean;
}

export interface BillingHistoryItem {
  id: number;
  apartment_id: number;
  year: number;
  month: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  service_name: string | null;
  actor_username: string;
  details: Record<string, ApiValue>;
  created_at: string;
}

export type UtilityType =
  | "electricity"
  | "water"
  | "gas"
  | "heating"
  | "sewage"
  | "internet"
  | "other";

export interface MeterItem {
  id: number;
  apartment_id?: number;
  service_name: string;
  utility_type: UtilityType;
  serial_number?: string | null;
  initial_reading?: string | number;
  installed_at?: string;
}

export interface MeterUpsertForm {
  service_name: string;
  utility_type: UtilityType;
  serial_number: string;
  initial_reading: string;
  installed_at: string;
}

export interface ServiceLedgerRow {
  id: number;
  apartment_id: number;
  service_name: string;
  year: number;
  month: number;
  accrued: string;
  paid: string;
  adjustment: string;
  benefit: string;
  subsidy: string;
  opening_balance: string;
  closing_balance: string;
  updated_at: string;
}

export interface ServiceLedgerForm {
  year: number;
  month: number;
  accrued: string;
  paid: string;
  adjustment: string;
  benefit: string;
  subsidy: string;
}
