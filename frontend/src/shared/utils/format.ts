import { MONTH_LABELS, readStoredLanguage } from "@/shared/i18n/config";
import { formatUkDate, monthStartIso } from "@/shared/utils/date";

export const money = (v: unknown): string => Number(v || 0).toFixed(2);

export const asInt = (v: unknown): string =>
  v === null || v === undefined || v === "" ? "" : String(Math.trunc(Number(v)));

export const periodLabel = (year: number, month: number): string => {
  const language = readStoredLanguage();
  return `${MONTH_LABELS[language][month - 1]} ${year}`;
};

export const dt = (x: string | Date | null | undefined): string => formatUkDate(x);

export const normalizePhone = (value: unknown): string => String(value || "").replace(/[^\d+]/g, "");

export const formatPhone = (value: unknown): string => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const digits = raw.replace(/\D/g, "");
  const ua = digits.startsWith("380") ? digits : digits.startsWith("0") ? `38${digits}` : digits;
  if (ua.length !== 12) return raw;
  return `+${ua.slice(0, 3)} ${ua.slice(3, 5)} ${ua.slice(5, 8)} ${ua.slice(8, 12)}`;
};

export const unitLabel = (x: string): string =>
  x === "kWh" ? "1 кВт·год" : x === "m3" ? "1 м3" : x === "month" ? "місяць" : x;

export const monthStart = (year: number, month: number): string => monthStartIso(year, month);

export const inferUtilityType = (serviceName: string): string => {
  const s = String(serviceName || "").toLowerCase();
  if (s.includes("елект") || s.includes("квт")) return "electricity";
  if (s.includes("газ")) return "gas";
  if (s.includes("вод")) return "water";
  if (s.includes("опал")) return "heating";
  if (s.includes("інтернет") || s.includes("internet")) return "internet";
  return "other";
};
