import { addMonths, format, isAfter, parseISO, startOfMonth } from "date-fns";
import { readStoredLanguage } from "@/shared/i18n/config";

export const todayIso = (): string => format(new Date(), "yyyy-MM-dd");

export const monthStartIso = (year: number, month: number): string =>
  format(new Date(Number(year), Number(month) - 1, 1), "yyyy-MM-dd");

export const formatUkDate = (value: string | Date | null | undefined): string => {
  if (!value) return "";
  const dt = typeof value === "string" ? parseISO(value) : value;
  if (Number.isNaN(dt.getTime())) return "";
  return new Intl.DateTimeFormat(readStoredLanguage() === "en" ? "en-GB" : "uk-UA", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(dt);
};

export const maxAllowedPeriodDate = (): Date => startOfMonth(addMonths(new Date(), 1));

export const isPeriodAfterMaxAllowed = (year: number, month: number): boolean => {
  const nextDate = new Date(Number(year), Number(month) - 1, 1);
  return isAfter(nextDate, maxAllowedPeriodDate());
};
