import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { QueryClient } from "@tanstack/react-query";

type AdminRole = "admin" | "operator" | "read_only";
type CreateAdminPayload = { username: string; password: string; role: AdminRole };
type UpdateAdminPayload = { id: number; role: AdminRole; is_active: boolean };

export function useAdminUserActions({
  tok,
  queryClient,
  pushToast,
}: {
  tok: string | null;
  queryClient: QueryClient;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
}) {
  const createAdminUserMutation = useMutation({
    mutationFn: async (payload: CreateAdminPayload) =>
      api("/auth/admin/users", tok, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      pushToast("Користувача створено", "success");
      queryClient.invalidateQueries({ queryKey: ["admin-users", tok] });
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося створити користувача", "error"),
  });

  const updateAdminUserMutation = useMutation({
    mutationFn: async (payload: UpdateAdminPayload) =>
      api(`/auth/admin/users/${payload.id}`, tok, {
        method: "PUT",
        body: JSON.stringify({ role: payload.role, is_active: payload.is_active }),
      }),
    onSuccess: () => {
      pushToast("Користувача оновлено", "success");
      queryClient.invalidateQueries({ queryKey: ["admin-users", tok] });
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити користувача", "error"),
  });

  return { createAdminUserMutation, updateAdminUserMutation };
}
