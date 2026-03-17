import { useMutation } from "@tanstack/react-query";
import { api } from "@/shared/api/client";

type PaymentPayload = {
  apartment_id: number;
  amount: number;
  paid_at: string;
  note: string | null;
  payer_type: "tenant" | "owner";
  tenant_id: number | null;
};

export function usePaymentActions({
  tok,
  apartmentId,
  period,
  reload,
  pushToast,
}: {
  tok: string | null;
  apartmentId?: number;
  period: { year: number; month: number };
  reload: () => Promise<unknown>;
  pushToast: (message: string, kind?: "success" | "error") => void;
}) {
  const createPaymentMutation = useMutation({
    mutationFn: async (payload: PaymentPayload) =>
      api("/admin/payments/utilities", tok, { method: "POST", body: payload }),
    onSuccess: async () => {
      pushToast("Оплату додано", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося додати оплату", "error"),
  });

  const updatePaymentMutation = useMutation({
    mutationFn: async ({ paymentId, payload }: { paymentId: number; payload: Omit<PaymentPayload, "apartment_id"> }) =>
      api(`/admin/payments/utilities/${paymentId}`, tok, { method: "PUT", body: payload }),
    onSuccess: async () => {
      pushToast("Оплату оновлено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося оновити оплату", "error"),
  });

  const deletePaymentMutation = useMutation({
    mutationFn: async (paymentId: number) => api(`/admin/payments/utilities/${paymentId}`, tok, { method: "DELETE" }),
    onSuccess: async () => {
      pushToast("Оплату видалено", "success");
      await reload();
    },
    onError: (e: Error) => pushToast(e.message || "Не вдалося видалити оплату", "error"),
  });

  const createPayment = async (payload: Omit<PaymentPayload, "apartment_id">) => {
    if (!apartmentId) throw new Error("Apartment is not selected");
    await createPaymentMutation.mutateAsync({
      apartment_id: apartmentId,
      ...payload,
    });
  };

  const updatePayment = async (
    paymentId: number,
    payload: Omit<PaymentPayload, "apartment_id">,
  ) => {
    await updatePaymentMutation.mutateAsync({
      paymentId,
      payload: {
        amount: payload.amount,
        paid_at: payload.paid_at,
        note: payload.note,
        payer_type: payload.payer_type,
        tenant_id: payload.tenant_id,
      },
    });
  };

  const deletePayment = async (paymentId: number) => {
    await deletePaymentMutation.mutateAsync(paymentId);
  };

  return {
    createPayment,
    updatePayment,
    deletePayment,
  };
}
