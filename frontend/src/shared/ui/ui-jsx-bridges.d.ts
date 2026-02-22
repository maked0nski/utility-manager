declare module "@/shared/ui/form-controls" {
  import type { ChangeEvent, KeyboardEvent, ReactNode } from "react";

  export interface BaseFieldProps {
    tip?: string;
    placeholder?: string;
    label?: string;
    value?: string | number;
    type?: string;
    min?: string | number;
    max?: string | number;
    disabled?: boolean;
    className?: string;
    onChange?: (e: ChangeEvent<any>) => void;
    onKeyDown?: (e: KeyboardEvent<any>) => void;
    [key: string]: any;
  }

  export function In(props: BaseFieldProps): ReactNode;
  export function Se(props: BaseFieldProps & { children?: ReactNode }): ReactNode;
  export function Ta(props: BaseFieldProps): ReactNode;
}

declare module "@/shared/ui/modal" {
  import type { ReactNode } from "react";
  export function Modal(props: {
    title?: string;
    onClose: () => void;
    children?: ReactNode;
  }): ReactNode;
}

declare module "@/shared/ui/toast" {
  import type { ReactNode } from "react";
  export function Toasts(props: {
    items: Array<{ id: string; message: string; type?: string }>;
    onClose: (id: string) => void;
  }): ReactNode;
}

declare module "@/shared/ui/confirm-modal" {
  import type { ReactNode } from "react";
  export function ConfirmModal(props: {
    open: boolean;
    title?: string;
    message?: string;
    onConfirm: () => void | Promise<void>;
    onCancel: () => void;
  }): ReactNode;
}
