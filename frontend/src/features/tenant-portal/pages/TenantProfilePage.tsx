import { useEffect, useState } from "react";
import { useMutation, type UseQueryResult } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { localizeApiError } from "@/features/tenant-portal/utils";
import type { TenantMe } from "@/shared/api/types";
import { useLanguage } from "@/shared/i18n/provider";
import { languageLabel, type AppLanguage } from "@/shared/i18n/config";

export function TenantProfilePage({
  token,
  me,
  setError,
  setNotice,
  onSessionRevoked,
}: {
  token: string;
  me: UseQueryResult<TenantMe, Error>;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
  onSessionRevoked: (reason: string) => void;
}) {
  const { language, setLanguage, t } = useLanguage();
  const [profileEmail, setProfileEmail] = useState("");
  const [primaryPhone, setPrimaryPhone] = useState("");
  const [extraPhones, setExtraPhones] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isEditMode, setIsEditMode] = useState(false);
  const profileEmailId = "tenant-profile-email";
  const primaryPhoneId = "tenant-profile-primary-phone";
  const phonesId = "tenant-profile-phones";
  const newPasswordId = "tenant-profile-new-password";
  const confirmPasswordId = "tenant-profile-confirm-password";

  useEffect(() => {
    if (!me.data) return;
    setProfileEmail(me.data.email || "");
    setPrimaryPhone(me.data.phone || "");
    setExtraPhones((me.data.phones || []).join(", "));
  }, [me.data]);

  const updateProfileMutation = useMutation({
    mutationFn: () =>
      api<TenantMe>("/tenant/me/profile", token, {
        method: "PUT",
        body: {
          email: profileEmail.trim().toLowerCase() || null,
          primary_phone: primaryPhone.trim() || null,
          phones: extraPhones
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
        },
      }),
    onSuccess: () => {
      setError("");
      setNotice("Профіль оновлено. Увійдіть повторно.");
      onSessionRevoked("Профіль змінено. Потрібен повторний вхід.");
    },
    onError: (err) => setError(localizeApiError(err, "Не вдалося зберегти профіль.")),
  });

  const changePasswordMutation = useMutation({
    mutationFn: () =>
      api("/tenant/me/password", token, {
        method: "PUT",
        body: { new_password: newPassword, confirm_password: confirmPassword },
      }),
    onSuccess: () => {
      setNewPassword("");
      setConfirmPassword("");
      setError("");
      setNotice("Пароль змінено. Увійдіть повторно.");
      onSessionRevoked("Пароль змінено. Потрібен повторний вхід.");
    },
    onError: (err) => setError(localizeApiError(err, "Не вдалося змінити пароль.")),
  });

  const logoutAllMutation = useMutation({
    mutationFn: () => api("/tenant/me/logout-all", token, { method: "POST" }),
    onSuccess: () => {
      setError("");
      setNotice("Усі сесії завершено. Увійдіть повторно.");
      onSessionRevoked("Усі сесії завершено.");
    },
    onError: (err) => setError(localizeApiError(err, "Не вдалося завершити всі сесії.")),
  });

  return (
    <section className="tenant-card">
      <h2>{t("tenant.profile.title", "Профіль")}</h2>
      {me.isLoading ? <p className="tenant-muted">{t("tenant.profile.loading", "Завантаження профілю...")}</p> : null}
      <div className="tenant-form-grid">
        {!isEditMode ? (
          <button className="btn-primary" type="button" onClick={() => setIsEditMode(true)}>
            {t("tenant.profile.edit", "Редагувати")}
          </button>
        ) : (
          <button className="secondary" type="button" onClick={() => setIsEditMode(false)}>
            {t("tenant.profile.cancelEdit", "Скасувати редагування")}
          </button>
        )}
        <label htmlFor={profileEmailId}>{t("tenant.profile.email", "Email (логін)")}</label>
        <input
          id={profileEmailId}
          value={profileEmail}
          onChange={(e) => setProfileEmail(e.target.value)}
          type="email"
          placeholder={t("tenant.profile.emailPlaceholder", "name@example.com")}
          readOnly={!isEditMode}
        />
        <label htmlFor={primaryPhoneId}>{t("tenant.profile.primaryPhone", "Основний телефон")}</label>
        <input
          id={primaryPhoneId}
          value={primaryPhone}
          onChange={(e) => setPrimaryPhone(e.target.value)}
          type="text"
          placeholder={t("tenant.profile.primaryPhonePlaceholder", "+380...")}
          readOnly={!isEditMode}
        />
        <label htmlFor={phonesId}>{t("tenant.profile.extraPhones", "Додаткові телефони")}</label>
        <input
          id={phonesId}
          value={extraPhones}
          onChange={(e) => setExtraPhones(e.target.value)}
          type="text"
          placeholder={t("tenant.profile.extraPhonesPlaceholder", "+380..., +380...")}
          readOnly={!isEditMode}
        />
        <p className="tenant-muted">{t("tenant.profile.extraPhonesHelp", "Вкажіть додаткові номери через кому.")}</p>
        <button
          className="btn-primary"
          onClick={() => updateProfileMutation.mutate()}
          disabled={updateProfileMutation.isPending || me.isLoading || !isEditMode}
        >
          {updateProfileMutation.isPending ? t("tenant.profile.saving", "Зберігаю...") : t("tenant.profile.save", "Зберегти профіль")}
        </button>

        <h3>{t("tenant.profile.interfaceTitle", "Інтерфейс")}</h3>
        <label htmlFor="tenant-language">{t("settings.language", "Мова")}</label>
        <select id="tenant-language" value={language} onChange={(e) => setLanguage(e.target.value as AppLanguage)}>
          {(["uk", "en"] as const).map((item) => (
            <option key={item} value={item}>
              {languageLabel(item)}
            </option>
          ))}
        </select>
        <p className="tenant-muted">{t("tenant.profile.interfaceHelp", "Мову можна змінити в будь-який момент. Нові екрани легко додати через словник перекладів.")}</p>

        <h3>{t("tenant.profile.passwordTitle", "Безпека")}</h3>
        <label htmlFor={newPasswordId}>{t("tenant.profile.newPassword", "Новий пароль")}</label>
        <input
          id={newPasswordId}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          type="password"
        />
        <label htmlFor={confirmPasswordId}>{t("tenant.profile.confirmPassword", "Підтвердіть новий пароль")}</label>
        <input
          id={confirmPasswordId}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          type="password"
        />
        <button
          className="btn-primary"
          onClick={() => changePasswordMutation.mutate()}
          disabled={changePasswordMutation.isPending || !newPassword || !confirmPassword}
        >
          {changePasswordMutation.isPending ? t("tenant.profile.updatingPassword", "Оновлюю...") : t("tenant.profile.changePassword", "Змінити пароль")}
        </button>
        <button
          className="tenant-link-btn"
          onClick={() => logoutAllMutation.mutate()}
          disabled={logoutAllMutation.isPending}
        >
          {logoutAllMutation.isPending ? t("tenant.profile.loggingOutAll", "Завершую...") : t("tenant.profile.logoutAll", "Завершити всі сесії")}
        </button>
      </div>
    </section>
  );
}
