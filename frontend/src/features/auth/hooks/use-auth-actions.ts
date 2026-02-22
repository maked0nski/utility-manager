import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";

type LoginCreds = { username: string; password: string };
type PasswordPayload = { current_password: string; new_password: string };
type BootstrapInfo = {
  username: string | null;
  password: string | null;
  must_change_password: boolean;
  password_rotation_recommended: boolean;
};

export function useAuthActions({
  tok,
  cred,
  pwd,
  setErr,
  setBoot,
  saveToken,
  clearToken,
  setSel,
  setSessionError,
  setPwdModal,
  setPwd,
  pushToast,
}: {
  tok: string | null;
  cred: LoginCreds;
  pwd: PasswordPayload;
  setErr: (message: string) => void;
  setBoot: (value: BootstrapInfo) => void;
  saveToken: (token: string) => void;
  clearToken: () => void;
  setSel: (value: null) => void;
  setSessionError: (value: string) => void;
  setPwdModal: (value: boolean) => void;
  setPwd: (value: PasswordPayload) => void;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
}) {
  const loginMutation = useMutation({
    mutationFn: async () =>
      api<{ access_token: string }>("/auth/admin/login", null, {
        method: "POST",
        body: JSON.stringify(cred),
      }),
    onSuccess: async (response) => {
      saveToken(response.access_token);
      setErr("");
      const info = await api<BootstrapInfo>("/auth/admin/bootstrap-info", null);
      setBoot(info);
    },
    onError: (e: Error) => setErr(e.message || "Не вдалося виконати вхід"),
  });

  const changePasswordMutation = useMutation({
    mutationFn: async (data: PasswordPayload) =>
      api("/auth/admin/change-password", tok, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: async () => {
      setPwdModal(false);
      setPwd({ current_password: "", new_password: "" });
      const info = await api<BootstrapInfo>("/auth/admin/bootstrap-info", null);
      setBoot(info);
      pushToast("Пароль адміністратора змінено", "success");
    },
    onError: (e: Error) => setErr(e.message || "Не вдалося змінити пароль"),
  });

  useEffect(() => {
    if (tok) return;
    api<BootstrapInfo>("/auth/admin/bootstrap-info", null)
      .then(setBoot)
      .catch(() =>
        setBoot({
          username: null,
          password: null,
          must_change_password: false,
          password_rotation_recommended: false,
        }),
      );
  }, [tok, setBoot]);

  const login = async () => {
    await loginMutation.mutateAsync();
  };

  const out = () => {
    clearToken();
    setSel(null);
    setSessionError("");
  };

  const changePassword = async (payload: PasswordPayload | null = null) => {
    const data = payload || pwd;
    await changePasswordMutation.mutateAsync(data);
  };

  return { login, out, changePassword };
}
