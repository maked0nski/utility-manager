export function Toasts({ items, onClose }) {
  if (!items?.length) return null;
  return (
    <div className="toasts">
      {items.map((t) => (
        <div key={t.id} className={`toast ${t.type || "info"}`}>
          <div>{t.message}</div>
          <button className="secondary" onClick={() => onClose(t.id)}>
            Закрити
          </button>
        </div>
      ))}
    </div>
  );
}
