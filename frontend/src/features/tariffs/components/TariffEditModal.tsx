import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { In, Se } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";

const tariffSchema = z
  .object({
    price_per_unit: z.coerce.number().positive("Тариф має бути більшим за 0"),
    unit_name: z.enum(["kWh", "m3", "month"]),
    service_status: z.enum(["active", "inactive"]),
    disable_from_month: z.string().optional(),
    provider_company: z.string().optional(),
    personal_account: z.string().optional(),
    cabinet_url: z.string().optional(),
    cabinet_login: z.string().optional(),
    cabinet_password: z.string().optional(),
    meter_id: z.string().optional(),
    meter_register: z.string().optional(),
    source_service_name: z.string().optional(),
  })
  .superRefine((v, ctx) => {
    if (v.service_status === "inactive" && !v.disable_from_month) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["disable_from_month"],
        message: "Вкажіть місяць відключення послуги",
      });
    }
  });

type TariffEditFormInput = {
  price_per_unit: string;
  unit_name: "kWh" | "m3" | "month";
  service_status: "active" | "inactive";
  disable_from_month?: string;
  provider_company?: string;
  personal_account?: string;
  cabinet_url?: string;
  cabinet_login?: string;
  cabinet_password?: string;
  meter_id?: string;
  meter_register?: string;
  source_service_name?: string;
};

export function TariffEditModal({
  tModal,
  tForm,
  saveT,
  delT,
  close,
  meters,
  serviceNames,
}: {
  tModal: any;
  tForm: any;
  saveT: (data: TariffEditFormInput) => Promise<void>;
  delT: () => Promise<void>;
  close: () => void;
  meters: Array<{ id: number; service_name: string; serial_number?: string | null }>;
  serviceNames: string[];
}) {
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<TariffEditFormInput>({
    resolver: zodResolver(tariffSchema),
    defaultValues: {
      price_per_unit: "",
      unit_name: "month",
      service_status: "active",
      disable_from_month: "",
      provider_company: "",
      personal_account: "",
      cabinet_url: "",
      cabinet_login: "",
      cabinet_password: "",
      meter_id: "",
      meter_register: "total",
      source_service_name: "",
    },
  });

  useEffect(() => {
    if (!tModal || !tForm) return;
    form.reset({
      price_per_unit: tForm.price_per_unit || "",
      unit_name: tForm.unit_name || "month",
      service_status: tForm.service_status || "active",
      disable_from_month: tForm.disable_from_month || "",
      provider_company: tForm.provider_company || "",
      personal_account: tForm.personal_account || "",
      cabinet_url: tForm.cabinet_url || "",
      cabinet_login: tForm.cabinet_login || "",
      cabinet_password: tForm.cabinet_password || "",
      meter_id: tForm.meter_id || "",
      meter_register: tForm.meter_register || "total",
      source_service_name: tForm.source_service_name || "",
    });
  }, [tModal, tForm, form]);

  if (!tModal || !tForm) return null;
  const serviceStatus = form.watch("service_status");
  const sourceServiceName = form.watch("source_service_name");
  const isMetered = tModal.charge_mode === "metered";

  return (
    <Modal title={`Тариф: ${tModal.service_name}`} onClose={close}>
      <form onSubmit={form.handleSubmit(async (data) => saveT(data))}>
        <div className="forms-grid">
          <Controller
            control={form.control}
            name="price_per_unit"
            render={({ field }) => (
              <In tip="Тариф послуги" value={field.value} onChange={field.onChange} />
            )}
          />
          <Controller
            control={form.control}
            name="unit_name"
            render={({ field }) => (
              <Se tip="Одиниця тарифу" value={field.value} onChange={field.onChange}>
                <option value="kWh">1 кВт·год</option>
                <option value="m3">1 м3</option>
                <option value="month">місяць</option>
              </Se>
            )}
          />
          <Controller
            control={form.control}
            name="service_status"
            render={({ field }) => (
              <Se tip="Стан послуги у розрахунку" value={field.value} onChange={field.onChange}>
                <option value="active">Активна</option>
                <option value="inactive">Неактивна</option>
              </Se>
            )}
          />
          {isMetered && (
            <>
              <Controller
                control={form.control}
                name="meter_id"
                render={({ field }) => (
                  <Se
                    tip="Лічильник для послуги"
                    value={field.value || ""}
                    onChange={field.onChange}
                    disabled={!!sourceServiceName}
                  >
                    <option value="">Оберіть лічильник</option>
                    {meters.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.service_name}{m.serial_number ? ` (${m.serial_number})` : ""}
                      </option>
                    ))}
                  </Se>
                )}
              />
              <Controller
                control={form.control}
                name="meter_register"
                render={({ field }) => (
                  <In
                    tip="Реєстр показника лічильника (total/day/night)"
                    placeholder="register_name"
                    value={field.value || "total"}
                    onChange={field.onChange}
                  />
                )}
              />
              <Controller
                control={form.control}
                name="source_service_name"
                render={({ field }) => (
                  <Se tip="Розрахунок від послуги" value={field.value || ""} onChange={field.onChange}>
                    <option value="">Власний лічильник</option>
                    {serviceNames
                      .filter((name) => name !== tModal.service_name)
                      .map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                  </Se>
                )}
              />
            </>
          )}
          {serviceStatus === "inactive" && (
            <Controller
              control={form.control}
              name="disable_from_month"
              render={({ field }) => (
                <In
                  tip="Місяць, з якого послуга вимикається"
                  type="month"
                  value={field.value || ""}
                  onChange={field.onChange}
                />
              )}
            />
          )}
          <Controller
            control={form.control}
            name="provider_company"
            render={({ field }) => (
              <In
                tip="Компанія постачальник"
                placeholder="Компанія"
                value={field.value || ""}
                onChange={field.onChange}
              />
            )}
          />
          <Controller
            control={form.control}
            name="personal_account"
            render={({ field }) => (
              <In
                tip="Особовий рахунок"
                placeholder="Особовий рахунок"
                value={field.value || ""}
                onChange={field.onChange}
              />
            )}
          />
          <Controller
            control={form.control}
            name="cabinet_url"
            render={({ field }) => (
              <In tip="URL кабінету" placeholder="URL" value={field.value || ""} onChange={field.onChange} />
            )}
          />
          <Controller
            control={form.control}
            name="cabinet_login"
            render={({ field }) => (
              <In
                tip="Логін кабінету"
                placeholder="Логін"
                value={field.value || ""}
                onChange={field.onChange}
              />
            )}
          />
          <Controller
            control={form.control}
            name="cabinet_password"
            render={({ field }) => (
              <In
                tip="Пароль кабінету"
                placeholder="Пароль"
                type={showPassword ? "text" : "password"}
                value={field.value || ""}
                onChange={field.onChange}
              />
            )}
          />
          <label className="check">
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(e) => setShowPassword(e.target.checked)}
            />
            Показати пароль
          </label>
        </div>
        {(form.formState.errors.price_per_unit || form.formState.errors.disable_from_month) && (
          <p className="error">
            {form.formState.errors.price_per_unit?.message ||
              form.formState.errors.disable_from_month?.message}
          </p>
        )}
        <div className="row-actions top-gap">
          <button type="submit" disabled={!form.formState.isDirty}>
            Зберегти
          </button>
          <button className="danger" type="button" onClick={delT}>
            Видалити
          </button>
        </div>
      </form>
    </Modal>
  );
}
