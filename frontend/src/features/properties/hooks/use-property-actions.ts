import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { QueryClient } from "@tanstack/react-query";

export function usePropertyActions({
  tok,
  sel,
  ap,
  setSel,
  setDrawer,
  setAddProp,
  apartmentsQuery,
  pushToast,
  confirmRun,
  queryClient,
  reload,
}: {
  tok: string | null;
  sel: { apartment_id: number; address?: string } | null;
  ap: { address: string };
  setSel: (v: { apartment_id: number; code?: string; address?: string } | null) => void;
  setDrawer: (v: boolean) => void;
  setAddProp: (v: boolean) => void;
  apartmentsQuery: { refetch: () => Promise<unknown> };
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
  confirmRun: (title: string, message: string, action: () => Promise<void>) => void;
  queryClient: QueryClient;
  reload: () => Promise<unknown>;
}) {
  const deleteApartmentMutation = useMutation({
    mutationFn: async (apartmentId: number) =>
      api(`/admin/apartments/${apartmentId}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      pushToast("Об'єкт видалено", "success");
      await queryClient.invalidateQueries({ queryKey: ["dashboard-apartments", tok] });
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити об'єкт", "error"),
  });

  const updateApartmentMutation = useMutation({
    mutationFn: async () => {
      if (!sel?.apartment_id) throw new Error("Нерухомість не обрана.");
      return api(`/admin/apartments/${sel.apartment_id}`, tok, {
        method: "PUT",
        body: JSON.stringify(ap),
      });
    },
    onSuccess: async () => {
      pushToast("Об'єкт оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити об'єкт", "error"),
  });

  const createApartmentMutation = useMutation({
    mutationFn: async () =>
      api<{ id: number; code: string; address: string }>("/admin/apartments", tok, {
        method: "POST",
        body: JSON.stringify({ address: ap.address }),
      }),
    onSuccess: async (row) => {
      await apartmentsQuery.refetch();
      setSel({ apartment_id: row.id, code: row.code, address: row.address });
      setDrawer(false);
      setAddProp(false);
      pushToast("Об'єкт створено", "success");
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося створити об'єкт", "error"),
  });

  const saveAp = async () => {
    await updateApartmentMutation.mutateAsync();
  };

  const createAp = async () => {
    await createApartmentMutation.mutateAsync();
  };

  const delAp = async () => {
    if (!sel?.apartment_id) return;
    confirmRun("Видалити об'єкт", `Підтвердьте видалення об'єкта "${sel.address}"`, async () => {
      await deleteApartmentMutation.mutateAsync(sel.apartment_id);
      setSel(null);
    });
  };

  return { saveAp, createAp, delAp, deleteApartmentMutation };
}
