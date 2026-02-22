import { useState } from "react";
import { todayIso } from "@/shared/utils/date";

type NewTariffForm = {
  service_name: string;
  charge_mode: "fixed" | "metered";
  price_per_unit: string;
  unit_name: "kWh" | "m3" | "month";
  effective_from: string;
  initial_meter_reading: string;
  meter_serial_number: string;
  service_status: "active" | "inactive";
  disable_from_month: string;
  personal_account: string;
  meter_id: string;
  meter_register: string;
  source_service_name: string;
};

export function useTariffFormState() {
  const [tar, setTar] = useState<any[]>([]);
  const [newTar, setNewTar] = useState<NewTariffForm>({
    service_name: "",
    charge_mode: "fixed",
    price_per_unit: "",
    unit_name: "month",
    effective_from: todayIso(),
    initial_meter_reading: "",
    meter_serial_number: "",
    service_status: "active",
    disable_from_month: "",
    personal_account: "",
    meter_id: "",
    meter_register: "total",
    source_service_name: "",
  });
  const [tModal, setTModal] = useState<any>(null);
  const [tForm, setTForm] = useState<any>(null);

  return {
    tar,
    setTar,
    newTar,
    setNewTar,
    tModal,
    setTModal,
    tForm,
    setTForm,
  };
}
