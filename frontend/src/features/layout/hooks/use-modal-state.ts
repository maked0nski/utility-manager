import { useState } from "react";

export type ToastKind = "info" | "success" | "error";
export type ToastItem = { id: string; message: string; type: ToastKind };
export type ConfirmState = { open: boolean; title: string; message: string };

export function useModalState() {
  const [payModal, setPayModal] = useState(false);
  const [pwdModal, setPwdModal] = useState(false);
  const [adminsModal, setAdminsModal] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirm, setConfirm] = useState<ConfirmState>({ open: false, title: "", message: "" });

  const pushToast = (message: string, type: ToastKind = "info") => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setToasts((items) => [...items, { id, message, type }]);
    setTimeout(() => setToasts((items) => items.filter((x) => x.id !== id)), 3500);
  };

  return {
    payModal,
    setPayModal,
    pwdModal,
    setPwdModal,
    adminsModal,
    setAdminsModal,
    toasts,
    setToasts,
    confirm,
    setConfirm,
    pushToast,
  };
}
