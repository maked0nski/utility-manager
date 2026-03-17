import { useLanguage } from "@/shared/i18n/provider";
import { ModeToggle } from "@/shared/ui/mode-toggle";

export function AdminHeader({
  boot,
  onOpenDrawer,
  onOpenAdmins,
  onOpenSettings,
  onLogout,
}: {
  boot: { must_change_password: boolean; password_rotation_recommended?: boolean };
  onOpenDrawer: () => void;
  onOpenAdmins: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
}) {
  const { t } = useLanguage();

  return (
    <header className="hero">
      <div className="title-row">
        <div>
          <h1>{t("admin.header.title", "UtilityManager Admin")}</h1>
          <p>{t("admin.header.subtitle", "Нерухомість, оренда, комуналка, витрати.")}</p>
        </div>
        <div className="hero-actions">
          <ModeToggle />
          <button className="hero-btn" onClick={onOpenDrawer}>
            {t("admin.header.properties", "Нерухомість/орендарі")}
          </button>
          <button className="hero-btn" onClick={onOpenAdmins}>
            {t("admin.header.users", "Користувачі")}
          </button>
          <button className="hero-btn" onClick={onOpenSettings}>
            {t("admin.header.settings", "Профіль")}
          </button>
          <button className="hero-btn ghost" onClick={onLogout}>
            {t("admin.header.logout", "Вийти")}
          </button>
        </div>
      </div>
      {boot.must_change_password && (
        <p className="warning">
          {t(
            "admin.warning.defaultPassword",
            "Нагадування: використовується стандартний пароль адміністратора. Рекомендується змінити його в меню \"Користувачі\".",
          )}
        </p>
      )}
      {!boot.must_change_password && boot.password_rotation_recommended && (
        <p className="warning">{t("admin.warning.rotation", "Нагадування: пароль адміністратора не змінювався понад 90 днів. Рекомендується ротація.")}</p>
      )}
    </header>
  );
}
