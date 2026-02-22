import { In } from "@/shared/ui/form-controls";
import type { Dispatch, SetStateAction } from "react";

type LoginCreds = { username: string; password: string };
type BootstrapInfo = {
  username: string | null;
  password: string | null;
  must_change_password: boolean;
  password_rotation_recommended?: boolean;
};

export function LoginScreen({
  cred,
  setCred,
  login,
  boot,
  err,
}: {
  cred: LoginCreds;
  setCred: Dispatch<SetStateAction<LoginCreds>>;
  login: () => void | Promise<void>;
  boot: BootstrapInfo;
  err: string;
}) {
  return (
    <div className="app-shell">
      <header className="hero">
        <h1>UtilityManager Admin</h1>
        <p>Вхід адміністратора</p>
      </header>
      <section className="card auth-card tenant-grid">
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
        {boot.must_change_password && (
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
