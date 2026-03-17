import { useLanguage } from "@/shared/i18n/provider";
import { languageLabel, type AppLanguage } from "@/shared/i18n/config";
import { ModeToggle } from "@/shared/ui/mode-toggle";
import { NavLink } from "react-router-dom";

export function TenantHeader({
  fullName,
  onLogout,
}: {
  fullName: string;
  onLogout: () => void;
}) {
  const { language, setLanguage, t } = useLanguage();

  return (
    <header className="tenant-header">
      <div>
        <h1>{t("tenant.header.title", "Кабінет орендаря")}</h1>
        <p>{fullName || "-"}</p>
      </div>
      <div className="tenant-nav">
        <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/dashboard">
          {t("tenant.header.dashboard", "Дашборд")}
        </NavLink>
        <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/history">
          {t("tenant.header.history", "Історія")}
        </NavLink>
        <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/profile">
          {t("tenant.header.profile", "Профіль")}
        </NavLink>
        <select
          className="tenant-language-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value as AppLanguage)}
          aria-label={t("settings.language", "Мова")}
        >
          {(["uk", "en"] as const).map((item) => (
            <option key={item} value={item}>
              {languageLabel(item)}
            </option>
          ))}
        </select>
        <ModeToggle />
        <button onClick={onLogout}>{t("tenant.header.logout", "Вийти")}</button>
      </div>
    </header>
  );
}
