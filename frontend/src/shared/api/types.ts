export type ApiPrimitive = string | number | boolean | null;
export type ApiValue = ApiPrimitive | ApiValue[] | { [key: string]: ApiValue };

export interface ApiValidationErrorItem {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
}

export interface ApiErrorPayload {
  detail?: string | ApiValidationErrorItem[] | Record<string, unknown> | null;
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
  actual_current_balance?: string | null;
  report_generated_at?: string | null;
  report_payments_to_date?: string | null;
  report_payment_date?: string | null;
  report_payment_note?: string | null;
  report_balance?: string | null;
}

export interface LiveBalanceSummary {
  current_balance: string;
  latest_payment_amount?: string | null;
  latest_payment_date?: string | null;
  latest_payment_note?: string | null;
}

export type BillingStatementStatus = "draft" | "prepared" | "sent" | "cancelled";

export interface UtilityPaymentItem {
  id: number;
  apartment_id: number;
  tenant_id: number | null;
  tenant_name?: string | null;
  year: number;
  month: number;
  amount: string;
  paid_at: string;
  note?: string | null;
  payer_type: "tenant" | "owner";
}

export interface CalculationRow {
  line_id?: number | null;
  meter_id: number | null;
  source_line_id?: number | null;
  service_name: string;
  service_group_key?: string | null;
  service_group_label?: string | null;
  service_line_label?: string | null;
  meter_register?: string;
  meter_register_label?: string | null;
  meter_plan_mode?: string | null;
  meter_expected_registers?: string[];
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

export interface BillingMonthSnapshotItem {
  id: number;
  apartment_id: number;
  year: number;
  month: number;
  status: string;
  opening_balance: string;
  utility_accrual: string;
  compensation_total: string;
  month_total: string;
  payments_in_month: string;
  closing_balance: string;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  reopened_at?: string | null;
  reopened_by?: string | null;
  reopen_reason?: string | null;
  rows: CalculationRow[];
}

export interface BillingAffectedPeriod {
  year: number;
  month: number;
  label: string;
  reason: string;
}

export interface BillingMonthReopenResult {
  status: string;
  reopened_count: number;
  reopened_periods: BillingAffectedPeriod[];
}

export interface BillingPeriodActionResult {
  status: string;
  recalculated_count: number;
  recalculated_periods: BillingAffectedPeriod[];
}

export interface BillingStatementItem {
  id: number;
  apartment_id: number;
  snapshot_id: number;
  year: number;
  month: number;
  version: number;
  status: BillingStatementStatus;
  generated_at: string;
  generated_by?: string | null;
  sent_at?: string | null;
  sent_channel?: string | null;
  sent_to?: string | null;
  month_closing_balance_snapshot: string;
  payments_after_month_to_generated_at: string;
  balance_due_on_generated_at: string;
  note?: string | null;
  rows: CalculationRow[];
}

export interface BillingPeriodSummaryItem {
  month_snapshot?: BillingMonthSnapshotItem | null;
  current_statement?: BillingStatementItem | null;
  statements: BillingStatementItem[];
}

export type UtilityType =
  | "electricity"
  | "water"
  | "gas"
  | "heating"
  | "sewage"
  | "internet"
  | "other";

export type ProviderKind =
  | "utility"
  | "management_company"
  | "telecom"
  | "security"
  | "other";

export type ServiceCalculationKind = "fixed" | "metered" | "derived";

export type ChargeLineKind = "fixed" | "meter_register" | "derived";

export type QuantitySource =
  | "fixed_1"
  | "registered_residents"
  | "area_m2"
  | "derived_consumption";

export interface ProviderItem {
  id: number;
  name_full: string;
  utility_type: UtilityType | null;
  provider_kind: ProviderKind;
  adapter_code: string;
  is_active: boolean;
  note?: string | null;
  created_at: string;
}

export interface ServiceCatalogItem {
  id: number;
  code: string;
  name: string;
  calculation_kind: ServiceCalculationKind;
  unit_name: string;
  requires_meter: boolean;
  allowed_meter_utility_type?: UtilityType | null;
  default_provider_utility_type?: UtilityType | null;
  derived_from_service_id?: number | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface ConnectionChargeLineItem {
  id: number;
  connection_id: number;
  line_kind: ChargeLineKind;
  label: string;
  meter_id?: number | null;
  meter_register: string;
  derived_from_line_id?: number | null;
  initial_reading?: string | null;
  unit_name: string;
  price_per_unit: string;
  quantity_source: QuantitySource;
  quantity_multiplier: string;
  effective_from: string;
  effective_to?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ApartmentServiceConnectionItem {
  id: number;
  apartment_id: number;
  service_catalog_id: number;
  provider_id?: number | null;
  personal_account?: string | null;
  started_at: string;
  ended_at?: string | null;
  status: string;
  note?: string | null;
  automation_id?: number | null;
  created_at: string;
  charge_lines: ConnectionChargeLineItem[];
}

export interface MeterItem {
  id: number;
  apartment_id?: number;
  meter_type_id?: number | null;
  meter_type_name?: string | null;
  display_name?: string | null;
  service_name?: string | null;
  utility_type: UtilityType;
  serial_number?: string | null;
  initial_reading?: string | number;
  installed_at?: string;
  retired_at?: string | null;
  replaced_by_meter_id?: number | null;
  is_active?: boolean;
}

export type ElectricityPlanMode = "single" | "day_night" | "tri_zone";

export interface ElectricityPlanHistoryItem {
  id: number;
  apartment_id: number;
  meter_id: number;
  meter_service_name: string;
  meter_serial_number?: string | null;
  plan_mode: ElectricityPlanMode | string;
  effective_from: string;
  single_service_name?: string | null;
  day_service_name?: string | null;
  night_service_name?: string | null;
  peak_service_name?: string | null;
  semi_peak_service_name?: string | null;
  off_peak_service_name?: string | null;
  single_price_per_unit?: string | null;
  day_price_per_unit?: string | null;
  night_price_per_unit?: string | null;
  peak_price_per_unit?: string | null;
  semi_peak_price_per_unit?: string | null;
  off_peak_price_per_unit?: string | null;
  single_initial_reading?: string | null;
  day_initial_reading?: string | null;
  night_initial_reading?: string | null;
  peak_initial_reading?: string | null;
  semi_peak_initial_reading?: string | null;
  off_peak_initial_reading?: string | null;
  note?: string | null;
  created_at: string;
  can_delete?: boolean;
  delete_block_reason?: string | null;
}

export interface MeterExpectedRegisterItem {
  register_name: string;
  label: string;
  service_name?: string | null;
  previous_reading?: string | null;
  current_reading?: string | null;
}

export interface MeterExpectedRegistersResult {
  meter_id: number;
  meter_service_name: string;
  plan_mode: string;
  effective_from?: string | null;
  registers: MeterExpectedRegisterItem[];
}

export interface MeterUpsertForm {
  meter_type_id: string;
  serial_number: string;
  installed_at: string;
}

export interface MeterTypeItem {
  id: number;
  code: string;
  name: string;
  utility_type: UtilityType;
  sort_order: number;
  is_active: boolean;
}

export interface MeterReplacementForm {
  serial_number: string;
  initial_reading: string;
  installed_at: string;
}

export interface ApartmentProfileForm {
  country: string;
  region: string;
  locality: string;
  street: string;
  house_number: string;
  apartment_number: string;
  postal_code: string;
  address: string;
  short_address: string;
  registered_residents: string;
  area_m2: string;
  living_area_m2: string;
  entrance: string;
  floor: string;
  room_count: string;
  latitude: string;
  longitude: string;
  google_maps_url: string;
  location_note: string;
  object_notes: string;
}

export interface ApartmentEquipmentItem {
  id: number;
  apartment_id: number;
  name: string;
  category: string;
  model_name?: string | null;
  serial_number?: string | null;
  installed_at?: string | null;
  manual_url?: string | null;
  service_interval_days?: number | null;
  last_service_at?: string | null;
  next_service_at?: string | null;
  note?: string | null;
  is_active: boolean;
}

export interface ApartmentEquipmentForm {
  name: string;
  category: string;
  model_name: string;
  serial_number: string;
  installed_at: string;
  manual_url: string;
  service_interval_days: string;
  last_service_at: string;
  next_service_at: string;
  note: string;
  is_active: boolean;
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

export interface TenantMe {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  phones: string[];
  portal_enabled: boolean;
  can_submit_meter_readings: boolean;
}

export interface TenantInvoiceItem {
  service_name: string;
  consumption: string;
  unit_name: string;
  unit_price: string;
  amount: string;
}

export interface TenantInvoice {
  id: number;
  year: number;
  month: number;
  total_amount: string;
  carry_over_debt: string;
  utility_payment_received: string;
  closing_balance: string;
  status: string;
  items: TenantInvoiceItem[];
}

export interface TenantDashboard {
  tenant_id: number;
  tenant_name: string;
  apartment_code: string;
  apartment_address: string;
  current_debt: string;
  current_invoice: TenantInvoice | null;
  latest_payment_amount: string | null;
  latest_payment_date: string | null;
}

export interface TenantHistory {
  invoices: TenantInvoice[];
}

export interface TenantSession {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export interface TenantPasswordResetResult {
  status: string;
  session_revoked: boolean;
}

export interface TenancyHistoryItem {
  id: number;
  start_date: string;
  end_date: string | null;
  tenant: {
    id: number;
    full_name: string;
  } | null;
}

export interface AutomationItem {
  automation_id?: number | null;
  template_id?: number | null;
  template_name?: string | null;
  template_code?: string | null;
  apartment_id: number;
  apartment_code: string;
  apartment_address: string;
  service_name: string;
  provider_id?: number | null;
  provider_name?: string | null;
  provider_company?: string | null;
  personal_account?: string | null;
  cabinet_url?: string | null;
  cabinet_login?: string | null;
  cabinet_password?: string | null;
  auto_check_enabled: boolean;
  auto_check_time: string;
  auto_check_timezone: string;
  auto_check_window_day_from: number;
  auto_check_window_day_to: number;
  auto_check_target_year?: number | null;
  auto_check_target_month?: number | null;
  auto_check_completed_for_period: boolean;
  auto_check_status?: string | null;
  auto_check_message?: string | null;
  auto_check_last_value_raw?: string | null;
  auto_check_last_value_rounded?: string | null;
  auto_check_last_checked_at?: string | null;
  auto_check_last_updated_at?: string | null;
  auto_check_next_at?: string | null;
  submit_enabled?: boolean;
  submit_time?: string;
  submit_window_day_from?: number;
  submit_window_day_to?: number;
  submit_target_year?: number | null;
  submit_target_month?: number | null;
  submit_completed_for_period?: boolean;
  submit_next_at?: string | null;
  submit_state_reason?: string | null;
}

export interface AutomationTemplateItem {
  id: number;
  code: string;
  name: string;
  provider_id?: number | null;
  provider_name?: string | null;
  utility_type?: UtilityType | null;
  cabinet_url?: string | null;
  description?: string | null;
  supports_accrual: boolean;
  supports_meter_submit: boolean;
  is_active: boolean;
  created_at: string;
}

export interface MeterSubmitEvaluateResult {
  can_submit: boolean;
  reason: string;
  automation_id?: number | null;
  template_name?: string | null;
  target_year?: number | null;
  target_month?: number | null;
}

export interface MeterSubmitDispatchResult {
  dispatched: boolean;
  message: string;
}

export interface AutomationCycleRunResult {
  id?: number | null;
  trigger_mode?: string;
  processed_accrual_automations: number;
  processed_submit_automations: number;
  processed_legacy_settings: number;
  submitted_readings: number;
  message: string;
  started_at?: string | null;
  finished_at?: string | null;
  phases?: AutomationCyclePhaseRunResult[];
}

export interface AutomationCyclePhaseRunResult {
  id?: number | null;
  phase: string;
  status: string;
  processed_count: number;
  skipped_count: number;
  submitted_readings: number;
  duration_ms?: number | null;
  message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AutomationCyclePreviewItem {
  automation_id?: number | null;
  apartment_id: number;
  apartment_address: string;
  service_name: string;
  phase: string;
  action: string;
  reason_code: string;
  reason: string;
}

export interface AutomationCyclePreviewResult {
  items: AutomationCyclePreviewItem[];
  message: string;
}

export interface AutomationCycleRunLogDetailResult {
  id: number;
  apartment_id: number;
  apartment_address: string;
  service_name: string;
  phase: string;
  mode: string;
  status: string;
  register_name?: string | null;
  target_year?: number | null;
  target_month?: number | null;
  message?: string | null;
  started_at: string;
  finished_at?: string | null;
}

export interface AutomationCycleRunDetailResult {
  id: number;
  trigger_mode: string;
  message: string;
  started_at?: string | null;
  finished_at?: string | null;
  phases: AutomationCyclePhaseRunResult[];
  logs: AutomationCycleRunLogDetailResult[];
}

export interface AutomationRunLogItem {
  id: number;
  automation_id?: number | null;
  apartment_id: number;
  service_name: string;
  register_name?: string | null;
  target_year?: number | null;
  target_month?: number | null;
  mode: string;
  status: string;
  message?: string | null;
  started_at: string;
  finished_at?: string | null;
}
