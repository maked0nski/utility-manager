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
