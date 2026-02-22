import { useState } from "react";
import { todayIso } from "@/shared/utils/date";

type OwnerChargeDraft = {
  kind: "owner_cost" | "reimbursement";
  category: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  event_date: string;
};

type MaintenanceDraft = {
  maintenance_type: "planned" | "unplanned";
  title: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  performed_at: string;
};

export function useOwnerFormState() {
  const [oc, setOc] = useState<any[]>([]);
  const [mr, setMr] = useState<any[]>([]);
  const [own, setOwn] = useState<OwnerChargeDraft>({
    kind: "owner_cost",
    category: "",
    description: "",
    amount: "",
    currency: "UAH",
    event_date: todayIso(),
  });
  const [mnt, setMnt] = useState<MaintenanceDraft>({
    maintenance_type: "planned",
    title: "",
    description: "",
    amount: "",
    currency: "UAH",
    performed_at: todayIso(),
  });
  const [ocModal, setOcModal] = useState<any>(null);
  const [ocForm, setOcForm] = useState<any>(null);
  const [mrModal, setMrModal] = useState<any>(null);
  const [mrForm, setMrForm] = useState<any>(null);

  return {
    oc,
    setOc,
    mr,
    setMr,
    own,
    setOwn,
    mnt,
    setMnt,
    ocModal,
    setOcModal,
    ocForm,
    setOcForm,
    mrModal,
    setMrModal,
    mrForm,
    setMrForm,
  };
}
