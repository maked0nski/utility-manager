import { Modal } from "@/shared/ui/modal";
import { useLanguage } from "@/shared/i18n/provider";
import { languageLabel, type AppLanguage } from "@/shared/i18n/config";

export function ProfileSettingsModal({
  username,
  themeMode,
  onClose,
  onCycleTheme,
  onOpenPassword,
}: {
  username?: string | null;
  themeMode: "light" | "dark" | "auto";
  onClose: () => void;
  onCycleTheme: () => void;
  onOpenPassword: () => void;
}) {
  const { language, setLanguage, t } = useLanguage();
  const themeLabel =
    themeMode === "auto"
      ? t("settings.theme.auto", "Авто")
      : themeMode === "dark"
        ? t("settings.theme.dark", "Темна")
        : t("settings.theme.light", "Світла");

  return (
    <Modal title={t("settings.title", "Налаштування профілю")} onClose={onClose}>
      <div className="settings-grid">
        <section className="subcard">
          <h4>{username || t("admin.header.settings", "Профіль")}</h4>
          <p className="helper">{t("settings.subtitle", "Керуйте мовою інтерфейсу, темою та безпекою входу.")}</p>
        </section>
        <section className="subcard">
          <h4>{t("settings.interface", "Інтерфейс")}</h4>
          <label className="field">
            <span className="field-label">{t("settings.language", "Мова")}</span>
            <select
              title={t("settings.languageHelp", "Застосовується до адмінки та кабінету орендаря на цьому пристрої.")}
              value={language}
              onChange={(e) => setLanguage(e.target.value as AppLanguage)}
            >
              {(["uk", "en"] as const).map((item) => (
                <option key={item} value={item}>
                  {languageLabel(item)}
                </option>
              ))}
            </select>
            <span className="field-help">
              {t("settings.languageHelp", "Застосовується до адмінки та кабінету орендаря на цьому пристрої.")}
            </span>
          </label>
          <div className="field">
            <span className="field-label">{t("settings.theme", "Тема")}</span>
            <button
              type="button"
              className="secondary"
              title={t("settings.themeHelp", "Натискання перемикає: світла, темна, авто.")}
              onClick={onCycleTheme}
            >
              {themeLabel}
            </button>
            <span className="field-help">{t("settings.themeHelp", "Натискання перемикає: світла, темна, авто.")}</span>
          </div>
        </section>
        <section className="subcard">
          <h4>{t("settings.security", "Безпека")}</h4>
          <p className="helper">{t("settings.securityHelp", "Зміну пароля адміністратора відкриваємо в окремому вікні.")}</p>
          <div className="row-actions">
            <button type="button" onClick={onOpenPassword}>
              {t("settings.changePassword", "Змінити пароль")}
            </button>
            <button type="button" className="secondary" onClick={onClose}>
              {t("settings.close", "Закрити")}
            </button>
          </div>
        </section>
      </div>
    </Modal>
  );
}
