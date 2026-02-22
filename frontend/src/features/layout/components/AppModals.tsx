import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { In, Se, Ta } from "@/shared/ui/form-controls";
import { Modal } from "@/shared/ui/modal";
import { Toasts } from "@/shared/ui/toast";
import { ConfirmModal } from "@/shared/ui/confirm-modal";
import { AdminUsersModal } from "@/features/auth/components/AdminUsersModal";
import { TariffEditModal } from "@/features/tariffs/components/TariffEditModal";
import type { ConfirmState, ToastItem } from "@/features/layout/hooks/use-modal-state";
import type { Dispatch, SetStateAction } from "react";

const positiveAmount = z.coerce.number().positive("Сума має бути більшою за 0");

const paySchema = z.object({
  amount: positiveAmount,
  paid_at: z.string().min(1, "Вкажіть дату оплати"),
  note: z.string().optional(),
});

const passwordSchema = z.object({
  current_password: z.string().min(1, "Вкажіть поточний пароль"),
  new_password: z.string().min(8, "Новий пароль має містити мінімум 8 символів"),
});

const ownerChargeSchema = z.object({
  year: z.coerce.number().int().min(2000).max(2100),
  month: z.coerce.number().int().min(1).max(12),
  kind: z.enum(["owner_cost", "reimbursement"]),
  category: z.string().min(1, "Вкажіть категорію"),
  description: z.string().optional(),
  amount: positiveAmount,
  currency: z.enum(["UAH", "USD", "EUR"]),
  event_date: z.string().min(1, "Вкажіть дату"),
});

const maintenanceSchema = z.object({
  maintenance_type: z.enum(["planned", "unplanned"]),
  title: z.string().min(1, "Вкажіть назву"),
  description: z.string().optional(),
  amount: z.union([z.literal(""), positiveAmount]),
  currency: z.enum(["UAH", "USD", "EUR"]),
  performed_at: z.string().min(1, "Вкажіть дату виконання"),
});

type PayFormData = { amount: number; paid_at: string; note?: string };
type PasswordFormData = { current_password: string; new_password: string };
type PayFormInput = { amount: string; paid_at: string; note: string };
type OwnerChargeFormInput = {
  year: string;
  month: string;
  kind: "owner_cost" | "reimbursement";
  category: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  event_date: string;
};
type MaintenanceFormInput = {
  maintenance_type: "planned" | "unplanned";
  title: string;
  description: string;
  amount: string;
  currency: "UAH" | "USD" | "EUR";
  performed_at: string;
};
export function AppModals({
  payModal,
  setPayModal,
  pay,
  savePay,
  pwdModal,
  setPwdModal,
  pwd,
  changePassword,
  adminsModal,
  setAdminsModal,
  adminUsersQuery,
  createAdminUserMutation,
  updateAdminUserMutation,
  tModal,
  tForm,
  saveT,
  delT,
  meters,
  tariffServiceNames,
  setTModal,
  setTFormModal,
  ocModal,
  ocForm,
  setOcModal,
  setOcForm,
  saveOc,
  delOc,
  mrModal,
  mrForm,
  setMrModal,
  setMrForm,
  saveMr,
  delMr,
  confirm,
  setConfirm,
  confirmActionRef,
  toasts,
  setToasts,
}: {
  payModal: boolean;
  setPayModal: (v: boolean) => void;
  pay: { amount?: string | number; paid_at?: string; note?: string };
  savePay: (data: PayFormData) => Promise<void>;
  pwdModal: boolean;
  setPwdModal: (v: boolean) => void;
  pwd: PasswordFormData;
  changePassword: (data: PasswordFormData) => Promise<void>;
  adminsModal: boolean;
  setAdminsModal: (v: boolean) => void;
  adminUsersQuery: { data?: any[] };
  createAdminUserMutation: { mutate: (payload: any) => void };
  updateAdminUserMutation: { mutate: (payload: any) => void };
  tModal: any;
  tForm: any;
  saveT: (payload: any) => Promise<void>;
  delT: () => Promise<void>;
  meters: Array<{ id: number; service_name: string; serial_number?: string | null }>;
  tariffServiceNames: string[];
  setTModal: (v: any) => void;
  setTFormModal: (v: any) => void;
  ocModal: any;
  ocForm: any;
  setOcModal: (v: any) => void;
  setOcForm: (v: any) => void;
  saveOc: (payload: any) => Promise<void>;
  delOc: () => Promise<void>;
  mrModal: any;
  mrForm: any;
  setMrModal: (v: any) => void;
  setMrForm: (v: any) => void;
  saveMr: (payload: any) => Promise<void>;
  delMr: () => Promise<void>;
  confirm: ConfirmState;
  setConfirm: (v: ConfirmState) => void;
  confirmActionRef: { current: null | (() => void | Promise<void>) };
  toasts: ToastItem[];
  setToasts: Dispatch<SetStateAction<ToastItem[]>>;
}) {
  const payForm = useForm<PayFormInput>({
    resolver: zodResolver(paySchema),
    defaultValues: { amount: "", paid_at: "", note: "" },
  });
  const pwdForm = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "" },
  });
  const ocEditForm = useForm<OwnerChargeFormInput>({
    resolver: zodResolver(ownerChargeSchema),
    defaultValues: {
      year: "",
      month: "",
      kind: "owner_cost",
      category: "",
      description: "",
      amount: "",
      currency: "UAH",
      event_date: "",
    },
  });
  const mrEditForm = useForm<MaintenanceFormInput>({
    resolver: zodResolver(maintenanceSchema),
    defaultValues: {
      maintenance_type: "planned",
      title: "",
      description: "",
      amount: "",
      currency: "UAH",
      performed_at: "",
    },
  });

  useEffect(() => {
    if (!payModal) return;
    payForm.reset({
      amount: String(pay.amount || ""),
      paid_at: pay.paid_at || "",
      note: pay.note || "",
    });
  }, [payModal, pay, payForm]);

  useEffect(() => {
    if (!pwdModal) return;
    pwdForm.reset({
      current_password: pwd.current_password || "",
      new_password: pwd.new_password || "",
    });
  }, [pwdModal, pwd, pwdForm]);

  useEffect(() => {
    if (!ocModal || !ocForm) return;
    ocEditForm.reset({
      year: ocForm.year || "",
      month: ocForm.month || "",
      kind: ocForm.kind || "owner_cost",
      category: ocForm.category || "",
      description: ocForm.description || "",
      amount: ocForm.amount || "",
      currency: ocForm.currency || "UAH",
      event_date: ocForm.event_date || "",
    });
  }, [ocModal, ocForm, ocEditForm]);

  useEffect(() => {
    if (!mrModal || !mrForm) return;
    mrEditForm.reset({
      maintenance_type: mrForm.maintenance_type || "planned",
      title: mrForm.title || "",
      description: mrForm.description || "",
      amount: mrForm.amount ?? "",
      currency: mrForm.currency || "UAH",
      performed_at: mrForm.performed_at || "",
    });
  }, [mrModal, mrForm, mrEditForm]);

  return (
    <>
      {payModal && (
        <Modal title="Оплата комуналки" onClose={() => setPayModal(false)}>
          <form
            onSubmit={payForm.handleSubmit(async (data) => {
              await savePay({
                amount: Number(data.amount || 0),
                paid_at: data.paid_at,
                note: data.note || "",
              });
            })}
          >
            <div className="forms-grid">
              <Controller
                control={payForm.control}
                name="amount"
                render={({ field }) => (
                  <In
                    tip="Сума оплати комуналки"
                    placeholder="Сума"
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <Controller
                control={payForm.control}
                name="paid_at"
                render={({ field }) => (
                  <In tip="Дата оплати комуналки" type="date" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={payForm.control}
                name="note"
                render={({ field }) => (
                  <In
                    tip="Примітка до оплати"
                    placeholder="Примітка"
                    value={field.value || ""}
                    onChange={field.onChange}
                  />
                )}
              />
            </div>
            {payForm.formState.errors.amount && (
              <p className="error">{payForm.formState.errors.amount.message}</p>
            )}
            {payForm.formState.errors.paid_at && (
              <p className="error">{payForm.formState.errors.paid_at.message}</p>
            )}
            <button type="submit">Зберегти</button>
          </form>
        </Modal>
      )}
      {pwdModal && (
        <Modal title="Зміна пароля адміністратора" onClose={() => setPwdModal(false)}>
          <form
            onSubmit={pwdForm.handleSubmit(async (data) => {
              await changePassword(data);
            })}
          >
            <div className="forms-grid">
              <Controller
                control={pwdForm.control}
                name="current_password"
                render={({ field }) => (
                  <In tip="Поточний пароль" type="password" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={pwdForm.control}
                name="new_password"
                render={({ field }) => (
                  <In
                    tip="Новий пароль (мінімум 8 символів)"
                    type="password"
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            </div>
            {pwdForm.formState.errors.current_password && (
              <p className="error">{pwdForm.formState.errors.current_password.message}</p>
            )}
            {pwdForm.formState.errors.new_password && (
              <p className="error">{pwdForm.formState.errors.new_password.message}</p>
            )}
            <div className="row-actions top-gap">
              <button type="submit">Зберегти</button>
              <button className="secondary" type="button" onClick={() => setPwdModal(false)}>
                Скасувати
              </button>
            </div>
          </form>
        </Modal>
      )}
      <AdminUsersModal
        open={adminsModal}
        onClose={() => setAdminsModal(false)}
        users={adminUsersQuery.data || []}
        onCreate={(payload) => createAdminUserMutation.mutate(payload)}
        onUpdate={(payload) => updateAdminUserMutation.mutate(payload)}
      />
      <TariffEditModal
        tModal={tModal}
        tForm={tForm}
        saveT={saveT}
        delT={delT}
        meters={meters}
        serviceNames={tariffServiceNames}
        close={() => {
          setTModal(null);
          setTFormModal(null);
        }}
      />
      {ocModal && ocForm && (
        <Modal
          title="Редагувати витрату/відшкодування"
          onClose={() => {
            setOcModal(null);
            setOcForm(null);
          }}
        >
          <form
            onSubmit={ocEditForm.handleSubmit(async (data) => {
              await saveOc(data);
            })}
          >
            <div className="forms-grid">
              <Controller
                control={ocEditForm.control}
                name="year"
                render={({ field }) => (
                  <In tip="Рік" type="number" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="month"
                render={({ field }) => (
                  <In
                    tip="Місяць"
                    type="number"
                    min="1"
                    max="12"
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="kind"
                render={({ field }) => (
                  <Se tip="Тип операції" value={field.value} onChange={field.onChange}>
                    <option value="owner_cost">Витрата власника</option>
                    <option value="reimbursement">Відшкодування орендарю</option>
                  </Se>
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="category"
                render={({ field }) => (
                  <In tip="Категорія" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="description"
                render={({ field }) => (
                  <In tip="Опис" value={field.value || ""} onChange={field.onChange} />
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="amount"
                render={({ field }) => (
                  <In tip="Сума" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="currency"
                render={({ field }) => (
                  <Se tip="Валюта" value={field.value} onChange={field.onChange}>
                    <option value="UAH">UAH</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </Se>
                )}
              />
              <Controller
                control={ocEditForm.control}
                name="event_date"
                render={({ field }) => (
                  <In tip="Дата" type="date" value={field.value} onChange={field.onChange} />
                )}
              />
            </div>
            {ocEditForm.formState.errors.amount && (
              <p className="error">{ocEditForm.formState.errors.amount.message}</p>
            )}
            <div className="row-actions top-gap">
              <button type="submit">Зберегти</button>
              <button className="danger" type="button" onClick={delOc}>
                Видалити
              </button>
            </div>
          </form>
        </Modal>
      )}
      {mrModal && mrForm && (
        <Modal
          title="Редагувати ремонт/обслуговування"
          onClose={() => {
            setMrModal(null);
            setMrForm(null);
          }}
        >
          <form
            onSubmit={mrEditForm.handleSubmit(async (data) => {
              await saveMr(data);
            })}
          >
            <div className="forms-grid">
              <Controller
                control={mrEditForm.control}
                name="maintenance_type"
                render={({ field }) => (
                  <Se tip="Плановість" value={field.value} onChange={field.onChange}>
                    <option value="planned">Плановий</option>
                    <option value="unplanned">Неплановий</option>
                  </Se>
                )}
              />
              <Controller
                control={mrEditForm.control}
                name="title"
                render={({ field }) => (
                  <In tip="Назва" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={mrEditForm.control}
                name="description"
                render={({ field }) => (
                  <Ta tip="Опис" value={field.value || ""} onChange={field.onChange} />
                )}
              />
              <Controller
                control={mrEditForm.control}
                name="amount"
                render={({ field }) => (
                  <In tip="Сума" value={field.value} onChange={field.onChange} />
                )}
              />
              <Controller
                control={mrEditForm.control}
                name="currency"
                render={({ field }) => (
                  <Se tip="Валюта" value={field.value} onChange={field.onChange}>
                    <option value="UAH">UAH</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </Se>
                )}
              />
              <Controller
                control={mrEditForm.control}
                name="performed_at"
                render={({ field }) => (
                  <In
                    tip="Дата виконання"
                    type="date"
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            </div>
            {mrEditForm.formState.errors.title && (
              <p className="error">{mrEditForm.formState.errors.title.message}</p>
            )}
            <div className="row-actions top-gap">
              <button type="submit">Зберегти</button>
              <button className="danger" type="button" onClick={delMr}>
                Видалити
              </button>
            </div>
          </form>
        </Modal>
      )}
      <ConfirmModal
        open={confirm.open}
        title={confirm.title}
        message={confirm.message}
        onCancel={() => {
          setConfirm({ open: false, title: "", message: "" });
          confirmActionRef.current = null;
        }}
        onConfirm={async () => {
          const action = confirmActionRef.current;
          setConfirm({ open: false, title: "", message: "" });
          confirmActionRef.current = null;
          if (action) await action();
        }}
      />
      <Toasts
        items={toasts}
        onClose={(id) => setToasts((items) => items.filter((x) => x.id !== id))}
      />
    </>
  );
}
