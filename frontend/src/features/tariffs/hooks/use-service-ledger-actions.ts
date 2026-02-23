import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import type { ServiceLedgerForm, ServiceLedgerRow } from "@/shared/api/types";

const ZERO_FORM: Omit<ServiceLedgerForm, "year" | "month"> = {
  accrued: "0",
  paid: "0",
  adjustment: "0",
  benefit: "0",
  subsidy: "0",
};

export function useServiceLedgerActions({
  tok,
  apartmentId,
  period,
  tariffs,
  pushToast,
}: {
  tok: string | null;
  apartmentId: number | null | undefined;
  period: { year: number; month: number };
  tariffs: Array<{ service_name?: string; charge_mode?: string }>;
  pushToast: (message: string, type?: "success" | "error" | "info") => void;
}) {
  const queryClient = useQueryClient();
  const fixedServiceNames = useMemo(() => {
    const set = new Set<string>();
    tariffs.forEach((t) => {
      const name = String(t.service_name || "").trim();
      if (!name) return;
      if (t.charge_mode !== "fixed") return;
      set.add(name);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, "uk-UA"));
  }, [tariffs]);

  const [selectedService, setSelectedService] = useState("");
  const [ledgerForm, setLedgerForm] = useState<ServiceLedgerForm>({
    year: period.year,
    month: period.month,
    ...ZERO_FORM,
  });

  useEffect(() => {
    if (!fixedServiceNames.length) {
      setSelectedService("");
      return;
    }
    if (!selectedService || !fixedServiceNames.includes(selectedService)) {
      setSelectedService(fixedServiceNames[0]);
    }
  }, [fixedServiceNames, selectedService]);

  useEffect(() => {
    setLedgerForm((s) => ({ ...s, year: period.year, month: period.month }));
  }, [period.year, period.month]);

  const ledgerHistoryQuery = useQuery<ServiceLedgerRow[], Error>({
    queryKey: ["service-ledger-history", tok, apartmentId, selectedService],
    enabled: !!tok && !!apartmentId && !!selectedService,
    queryFn: async () =>
      api<ServiceLedgerRow[]>(
        `/admin/apartments/${apartmentId}/service-ledger/${encodeURIComponent(selectedService)}/history?limit=24`,
        tok,
      ),
  });

  const saveLedgerMutation = useMutation({
    mutationFn: async () => {
      if (!apartmentId) throw new Error("Нерухомість не обрана.");
      if (!selectedService) throw new Error("Оберіть послугу.");
      const body = {
        year: Number(ledgerForm.year),
        month: Number(ledgerForm.month),
        accrued: Number(ledgerForm.accrued || 0),
        paid: Number(ledgerForm.paid || 0),
        adjustment: Number(ledgerForm.adjustment || 0),
        benefit: Number(ledgerForm.benefit || 0),
        subsidy: Number(ledgerForm.subsidy || 0),
      };
      await api(
        `/admin/apartments/${apartmentId}/service-ledger/${encodeURIComponent(selectedService)}`,
        tok,
        {
          method: "PUT",
          body: JSON.stringify(body),
        },
      );
    },
    onSuccess: async () => {
      pushToast("Дані по послузі збережено", "success");
      await queryClient.invalidateQueries({
        queryKey: ["service-ledger-history", tok, apartmentId, selectedService],
      });
    },
    onError: (e: Error) =>
      pushToast(e.message || "Не вдалося зберегти помісячні дані по послузі", "error"),
  });

  const saveServiceLedgerMonth = async () => {
    await saveLedgerMutation.mutateAsync();
  };

  return {
    fixedServiceNames,
    selectedService,
    setSelectedService,
    ledgerForm,
    setLedgerForm,
    ledgerHistory: ledgerHistoryQuery.data || [],
    ledgerHistoryLoading: ledgerHistoryQuery.isFetching,
    saveServiceLedgerMonth,
  };
}
