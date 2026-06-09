import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/shared/api/client";
import { localizeApiError } from "@/features/tenant-portal/utils";
import type { TenantPasswordResetResult, TenantSession } from "@/shared/api/types";

export function TenantLoginPage({
  onSessionCreated,
  setError,
  setNotice,
  error,
}: {
  onSessionCreated: (session: TenantSession) => void;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
  error: string;
}) {
  const navigate = useNavigate();
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [mode, setMode] = useState<"login" | "reset">("login");
  const [resetEmail, setResetEmail] = useState("");
  const [resetAccessCode, setResetAccessCode] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState("");

  const loginMutation = useMutation({
    mutationFn: async () => {
      return api<TenantSession>("/tenant/login", null, {
        method: "POST",
        body: { email: loginEmail.trim().toLowerCase(), password: loginPassword },
      });
    },
    onSuccess: (session) => {
      onSessionCreated(session);
      setError("");
      setNotice("");
      setLoginPassword("");
      navigate("/dashboard", { replace: true });
    },
    onError: (err) => setError(localizeApiError(err, "Не вдалося увійти.")),
  });

  const onLoginSubmit = (event: FormEvent) => {
    event.preventDefault();
    loginMutation.mutate();
  };
  const resetMutation = useMutation({
    mutationFn: async () =>
      api<TenantPasswordResetResult>("/tenant/forgot-password", null, {
        method: "POST",
        body: {
          email: resetEmail.trim().toLowerCase(),
          access_code: resetAccessCode.trim(),
          new_password: resetPassword,
          confirm_password: resetPasswordConfirm,
        },
      }),
    onSuccess: () => {
      setError("");
      setNotice("Пароль оновлено. Увійдіть з новим паролем.");
      setLoginEmail(resetEmail.trim().toLowerCase());
      setLoginPassword("");
      setResetAccessCode("");
      setResetPassword("");
      setResetPasswordConfirm("");
      setMode("login");
    },
    onError: (err) => setError(localizeApiError(err, "Не вдалося відновити пароль.")),
  });
  const emailId = "tenant-login-email";
  const passwordId = "tenant-login-password";
  const resetEmailId = "tenant-reset-email";
  const resetAccessCodeId = "tenant-reset-access-code";
  const resetPasswordId = "tenant-reset-password";
  const resetPasswordConfirmId = "tenant-reset-password-confirm";

  return (
    <div className="tenant-portal tenant-login-shell">
      <form className="tenant-card" onSubmit={mode === "login" ? onLoginSubmit : (event) => { event.preventDefault(); resetMutation.mutate(); }}>
        <h1>UtilityManager Tenant</h1>
        {mode === "login" ? <p>Вхід у кабінет орендаря</p> : <p>Відновлення доступу до кабінету</p>}

        {mode === "login" ? (
          <>
            <label htmlFor={emailId}>Email</label>
            <input
              id={emailId}
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
              type="email"
              required
            />
            <label htmlFor={passwordId}>Пароль</label>
            <input
              id={passwordId}
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              type="password"
              required
            />
            <button className="btn-primary" type="submit" disabled={loginMutation.isPending}>
              {loginMutation.isPending ? "Вхід..." : "Увійти"}
            </button>
          </>
        ) : (
          <>
            <label htmlFor={resetEmailId}>Email орендаря</label>
            <input
              id={resetEmailId}
              value={resetEmail}
              onChange={(e) => setResetEmail(e.target.value)}
              type="email"
              placeholder="tenant@example.com"
              required
            />
            <label htmlFor={resetAccessCodeId}>Код доступу</label>
            <input
              id={resetAccessCodeId}
              value={resetAccessCode}
              onChange={(e) => setResetAccessCode(e.target.value)}
              type="text"
              placeholder="Код, який видав адміністратор"
              required
            />
            <p className="tenant-muted">
              Для відновлення пароля введіть email, код доступу та новий пароль. Після оновлення старі сесії буде
              завершено автоматично.
            </p>
            <label htmlFor={resetPasswordId}>Новий пароль</label>
            <input
              id={resetPasswordId}
              value={resetPassword}
              onChange={(e) => setResetPassword(e.target.value)}
              type="password"
              placeholder="Мінімум 8 символів, велика літера і цифра"
              required
            />
            <label htmlFor={resetPasswordConfirmId}>Підтвердьте новий пароль</label>
            <input
              id={resetPasswordConfirmId}
              value={resetPasswordConfirm}
              onChange={(e) => setResetPasswordConfirm(e.target.value)}
              type="password"
              required
            />
            <button className="btn-primary" type="submit" disabled={resetMutation.isPending}>
              {resetMutation.isPending ? "Оновлення..." : "Оновити пароль"}
            </button>
          </>
        )}
        <button
          className="tenant-link-btn"
          type="button"
          onClick={() => {
            setMode((current) => (current === "login" ? "reset" : "login"));
            setError("");
            setNotice("");
          }}
        >
          {mode === "login" ? "Забув пароль" : "Назад до входу"}
        </button>
        {error ? <div className="tenant-error">{error}</div> : null}
      </form>
    </div>
  );
}
