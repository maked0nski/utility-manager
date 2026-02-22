export function AdminHeader({
  boot,
  onOpenDrawer,
  onOpenAdmins,
  onOpenChangePassword,
  onLogout,
}: {
  boot: { must_change_password: boolean; password_rotation_recommended?: boolean };
  onOpenDrawer: () => void;
  onOpenAdmins: () => void;
  onOpenChangePassword: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="hero">
      <div className="title-row">
        <div>
          <h1>UtilityManager Admin</h1>
          <p>Нерухомість, оренда, комуналка, витрати.</p>
        </div>
        <div className="row-actions">
          <button className="secondary" onClick={onOpenDrawer}>
            Список нерухомості
          </button>
          <button className="secondary" onClick={onOpenAdmins}>
            Користувачі
          </button>
          <button className="secondary" onClick={onOpenChangePassword}>
            Змінити пароль
          </button>
          <button className="secondary" onClick={onLogout}>
            Вийти
          </button>
        </div>
      </div>
      {boot.must_change_password && (
        <p className="warning">
          Нагадування: використовується стандартний пароль адміністратора.
          Рекомендується змінити його в меню "Змінити пароль".
        </p>
      )}
      {!boot.must_change_password && boot.password_rotation_recommended && (
        <p className="warning">
          Нагадування: пароль адміністратора не змінювався понад 90 днів. Рекомендується ротація.
        </p>
      )}
    </header>
  );
}
