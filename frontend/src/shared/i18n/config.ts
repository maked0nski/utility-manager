export type AppLanguage = "uk" | "en";

export const LANGUAGE_KEY = "um-ui-language";

export const MONTH_LABELS: Record<AppLanguage, readonly string[]> = {
  uk: [
    "Січень",
    "Лютий",
    "Березень",
    "Квітень",
    "Травень",
    "Червень",
    "Липень",
    "Серпень",
    "Вересень",
    "Жовтень",
    "Листопад",
    "Грудень",
  ],
  en: [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ],
};

export const readStoredLanguage = (): AppLanguage => {
  if (typeof window === "undefined") return "uk";
  const stored = window.localStorage.getItem(LANGUAGE_KEY);
  return stored === "en" ? "en" : "uk";
};

export const languageLabel = (language: AppLanguage) => (language === "uk" ? "Українська" : "English");
