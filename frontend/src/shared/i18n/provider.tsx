import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AppLanguage, LANGUAGE_KEY, readStoredLanguage } from "@/shared/i18n/config";

type Dictionary = Record<string, string>;

const messages: Record<AppLanguage, Dictionary> = {
  uk: {
    "common.loading": "Завантаження...",
    "settings.title": "Налаштування профілю",
    "settings.subtitle": "Керуйте мовою інтерфейсу, темою та безпекою входу.",
    "settings.interface": "Інтерфейс",
    "settings.language": "Мова",
    "settings.languageHelp": "Застосовується до адмінки та кабінету орендаря на цьому пристрої.",
    "settings.theme": "Тема",
    "settings.theme.light": "Світла",
    "settings.theme.dark": "Темна",
    "settings.theme.auto": "Авто",
    "settings.theme.next": "Наступна",
    "settings.themeHelp": "Натискання перемикає: світла, темна, авто.",
    "settings.security": "Безпека",
    "settings.securityHelp": "Зміну пароля адміністратора відкриваємо в окремому вікні.",
    "settings.changePassword": "Змінити пароль",
    "settings.close": "Закрити",
    "admin.header.title": "UtilityManager Admin",
    "admin.header.subtitle": "Нерухомість, оренда, комуналка, витрати.",
    "admin.header.theme.light": "Світла тема",
    "admin.header.theme.dark": "Темна тема",
    "admin.header.properties": "Нерухомість/орендарі",
    "admin.header.users": "Користувачі",
    "admin.header.settings": "Профіль",
    "admin.header.logout": "Вийти",
    "admin.warning.defaultPassword":
      "Нагадування: використовується стандартний пароль адміністратора. Рекомендується змінити його в меню \"Користувачі\".",
    "admin.warning.rotation":
      "Нагадування: пароль адміністратора не змінювався понад 90 днів. Рекомендується ротація.",
    "tenant.header.title": "Кабінет орендаря",
    "tenant.header.dashboard": "Дашборд",
    "tenant.header.history": "Історія",
    "tenant.header.profile": "Профіль",
    "tenant.header.theme.light": "Світла тема",
    "tenant.header.theme.dark": "Темна тема",
    "tenant.header.logout": "Вийти",
    "tenant.profile.title": "Профіль",
    "tenant.profile.loading": "Завантаження профілю...",
    "tenant.profile.edit": "Редагувати",
    "tenant.profile.cancelEdit": "Скасувати редагування",
    "tenant.profile.email": "Email (логін)",
    "tenant.profile.emailPlaceholder": "name@example.com",
    "tenant.profile.primaryPhone": "Основний телефон",
    "tenant.profile.primaryPhonePlaceholder": "+380...",
    "tenant.profile.extraPhones": "Додаткові телефони",
    "tenant.profile.extraPhonesPlaceholder": "+380..., +380...",
    "tenant.profile.extraPhonesHelp": "Вкажіть додаткові номери через кому.",
    "tenant.profile.save": "Зберегти профіль",
    "tenant.profile.saving": "Зберігаю...",
    "tenant.profile.passwordTitle": "Безпека",
    "tenant.profile.newPassword": "Новий пароль",
    "tenant.profile.confirmPassword": "Підтвердіть новий пароль",
    "tenant.profile.changePassword": "Змінити пароль",
    "tenant.profile.updatingPassword": "Оновлюю...",
    "tenant.profile.logoutAll": "Завершити всі сесії",
    "tenant.profile.loggingOutAll": "Завершую...",
    "tenant.profile.interfaceTitle": "Інтерфейс",
    "tenant.profile.interfaceHelp": "Мову можна змінити в будь-який момент. Нові екрани легко додати через словник перекладів.",
  },
  en: {
    "common.loading": "Loading...",
    "settings.title": "Profile settings",
    "settings.subtitle": "Manage interface language, theme, and sign-in security.",
    "settings.interface": "Interface",
    "settings.language": "Language",
    "settings.languageHelp": "Applies to the admin and tenant interfaces on this device.",
    "settings.theme": "Theme",
    "settings.theme.light": "Light",
    "settings.theme.dark": "Dark",
    "settings.theme.auto": "Auto",
    "settings.theme.next": "Next",
    "settings.themeHelp": "Each click cycles through light, dark, and auto.",
    "settings.security": "Security",
    "settings.securityHelp": "Administrator password changes open in a separate dialog.",
    "settings.changePassword": "Change password",
    "settings.close": "Close",
    "admin.header.title": "UtilityManager Admin",
    "admin.header.subtitle": "Property, rent, utilities, expenses.",
    "admin.header.theme.light": "Light theme",
    "admin.header.theme.dark": "Dark theme",
    "admin.header.properties": "Properties/Tenants",
    "admin.header.users": "Users",
    "admin.header.settings": "Profile",
    "admin.header.logout": "Log out",
    "admin.warning.defaultPassword":
      "Reminder: the default administrator password is still in use. Change it from the \"Users\" section.",
    "admin.warning.rotation":
      "Reminder: the administrator password has not been changed for more than 90 days. Rotation is recommended.",
    "tenant.header.title": "Tenant portal",
    "tenant.header.dashboard": "Dashboard",
    "tenant.header.history": "History",
    "tenant.header.profile": "Profile",
    "tenant.header.theme.light": "Light theme",
    "tenant.header.theme.dark": "Dark theme",
    "tenant.header.logout": "Log out",
    "tenant.profile.title": "Profile",
    "tenant.profile.loading": "Loading profile...",
    "tenant.profile.edit": "Edit",
    "tenant.profile.cancelEdit": "Cancel editing",
    "tenant.profile.email": "Email (login)",
    "tenant.profile.emailPlaceholder": "name@example.com",
    "tenant.profile.primaryPhone": "Primary phone",
    "tenant.profile.primaryPhonePlaceholder": "+380...",
    "tenant.profile.extraPhones": "Additional phones",
    "tenant.profile.extraPhonesPlaceholder": "+380..., +380...",
    "tenant.profile.extraPhonesHelp": "Enter extra phone numbers separated by commas.",
    "tenant.profile.save": "Save profile",
    "tenant.profile.saving": "Saving...",
    "tenant.profile.passwordTitle": "Security",
    "tenant.profile.newPassword": "New password",
    "tenant.profile.confirmPassword": "Confirm new password",
    "tenant.profile.changePassword": "Change password",
    "tenant.profile.updatingPassword": "Updating...",
    "tenant.profile.logoutAll": "End all sessions",
    "tenant.profile.loggingOutAll": "Ending...",
    "tenant.profile.interfaceTitle": "Interface",
    "tenant.profile.interfaceHelp": "You can switch language at any time. New screens can be added through the translation dictionary.",
  },
};

type LanguageContextValue = {
  language: AppLanguage;
  setLanguage: (language: AppLanguage) => void;
  t: (key: string, fallback?: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<AppLanguage>(readStoredLanguage);

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_KEY, language);
    document.documentElement.setAttribute("lang", language);
  }, [language]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== LANGUAGE_KEY) return;
      setLanguageState(readStoredLanguage());
    };
    const onLanguageChanged = (event: Event) => {
      const next = (event as CustomEvent<AppLanguage>).detail;
      if ((next === "uk" || next === "en") && next !== language) setLanguageState(next);
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("um-language-changed", onLanguageChanged as EventListener);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("um-language-changed", onLanguageChanged as EventListener);
    };
  }, [language]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage: setLanguageState,
      t: (key, fallback) => messages[language][key] || fallback || key,
    }),
    [language],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used inside LanguageProvider");
  return ctx;
}
