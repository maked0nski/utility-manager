import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { QueryClient } from "@tanstack/react-query";
import type { ApartmentProfileForm } from "@/shared/api/types";
import { buildFullPropertyAddress, buildShortPropertyAddress } from "@/features/properties/utils/address";

function apartmentPayload(ap: ApartmentProfileForm) {
  return {
    country: ap.country || "Україна",
    region: ap.region || null,
    locality: ap.locality || null,
    street: ap.street || null,
    house_number: ap.house_number || null,
    apartment_number: ap.apartment_number || null,
    postal_code: ap.postal_code || null,
    address: buildFullPropertyAddress(ap) || null,
    registered_residents: ap.registered_residents.trim() !== "" ? Number(ap.registered_residents) : 1,
    area_m2: ap.area_m2 !== "" ? Number(ap.area_m2) : null,
    living_area_m2: ap.living_area_m2 !== "" ? Number(ap.living_area_m2) : null,
    entrance: ap.entrance || null,
    floor: ap.floor || null,
    room_count: ap.room_count !== "" ? Number(ap.room_count) : null,
    latitude: ap.latitude !== "" ? Number(ap.latitude) : null,
    longitude: ap.longitude !== "" ? Number(ap.longitude) : null,
    location_note: ap.location_note || null,
    object_notes: ap.object_notes || null,
  };
}

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
  sel: { apartment_id: number; address?: string; short_address?: string } | null;
  ap: ApartmentProfileForm;
  setSel: (v: { apartment_id: number; code?: string; address?: string; short_address?: string } | null) => void;
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
        body: JSON.stringify(apartmentPayload(ap)),
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
      api<{ id: number; code: string; address: string; short_address?: string; google_maps_url?: string | null }>(
        "/admin/apartments",
        tok,
        {
          method: "POST",
          body: JSON.stringify(apartmentPayload(ap)),
        },
      ),
    onSuccess: async (row) => {
      await apartmentsQuery.refetch();
      setSel({
        apartment_id: row.id,
        code: row.code,
        address: row.address,
        short_address: row.short_address || buildShortPropertyAddress(ap),
      });
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
    confirmRun("Видалити об'єкт", `Підтвердьте видалення об'єкта "${sel.short_address || sel.address}"`, async () => {
      await deleteApartmentMutation.mutateAsync(sel.apartment_id);
      setSel(null);
    });
  };

  return { saveAp, createAp, delAp, deleteApartmentMutation };
}
