import { In } from "@/shared/ui/form-controls";
import type { Dispatch, SetStateAction } from "react";

type LoginCreds = { username: string; password: string };
type BootstrapInfo = {
  username: string | null;
  password: string | null;
  must_change_password: boolean;
  password_rotation_recommended?: boolean;
  needs_initial_admin_setup: boolean;
};
type InitialAdmin = { username: string; password: string; confirm_password: string };

export function LoginScreen({
  cred,
  setCred,
  initialAdmin,
  setInitialAdmin,
  login,
  registerInitialAdmin,
  boot,
  err,
}: {
  cred: LoginCreds;
  setCred: Dispatch<SetStateAction<LoginCreds>>;
  initialAdmin: InitialAdmin;
  setInitialAdmin: Dispatch<SetStateAction<InitialAdmin>>;
  login: () => void | Promise<void>;
  registerInitialAdmin: () => void | Promise<void>;
  boot: BootstrapInfo;
  err: string;
}) {
  const isInitialSetup = boot.needs_initial_admin_setup;

  return (
    <div className="app-shell">
      <header className="hero">
        <h1>UtilityManager Admin</h1>
        <p>{isInitialSetup ? "Початкове налаштування адміністратора" : "Вхід адміністратора"}</p>
      </header>
      <section className="card auth-card tenant-grid">
        {isInitialSetup ? (
          <>
            <p className="helper auth-note">
              База порожня. Створіть першого адміністратора, після чого ви одразу увійдете в систему.
            </p>
            <In
              tip="Логін першого адміністратора"
              placeholder="Логін адміністратора"
              help="Мінімум 3 символи. Цей логін буде використовуватись для входу в адмінку."
              value={initialAdmin.username}
              onChange={(e) => setInitialAdmin((s) => ({ ...s, username: e.target.value }))}
            />
            <In
              tip="Пароль першого адміністратора"
              type="password"
              placeholder="Пароль"
              help="Мінімум 8 символів, велика і мала літера та цифра."
              value={initialAdmin.password}
              onChange={(e) => setInitialAdmin((s) => ({ ...s, password: e.target.value }))}
            />
            <In
              tip="Підтвердження пароля"
              type="password"
              placeholder="Повторіть пароль"
              help="Потрібен для перевірки, що пароль введений без помилки."
              value={initialAdmin.confirm_password}
              onChange={(e) => setInitialAdmin((s) => ({ ...s, confirm_password: e.target.value }))}
            />
            <button onClick={registerInitialAdmin}>Створити адміністратора</button>
          </>
        ) : (
          <>
            <In
              tip="Логін адміністратора"
              placeholder="Логін"
              value={cred.username}
              onChange={(e) => setCred((s) => ({ ...s, username: e.target.value }))}
            />
            <In
              tip="Пароль адміністратора"
              type="password"
              placeholder="Пароль"
              value={cred.password}
              onChange={(e) => setCred((s) => ({ ...s, password: e.target.value }))}
            />
            <button onClick={login}>Увійти</button>
          </>
        )}
        {!isInitialSetup && boot.must_change_password && (
          <p className="helper">
            Перший вхід: логін <strong>{boot.username}</strong>, пароль{" "}
            <strong>{boot.password}</strong>. Після входу змініть пароль.
          </p>
        )}
        {err && <p className="error">{err}</p>}
      </section>
    </div>
  );
}
