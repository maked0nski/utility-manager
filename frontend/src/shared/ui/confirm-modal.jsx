import { Modal } from "@/shared/ui/modal";

export function ConfirmModal({ open, title, message, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <Modal title={title || "Підтвердження"} onClose={onCancel}>
      <p>{message || "Підтвердити дію?"}</p>
      <div className="row-actions top-gap">
        <button className="danger" onClick={onConfirm}>
          Підтвердити
        </button>
        <button className="secondary" onClick={onCancel}>
          Скасувати
        </button>
      </div>
    </Modal>
  );
}
