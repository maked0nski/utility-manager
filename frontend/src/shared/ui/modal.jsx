export const Modal = ({ title, onClose, children }) => (
  <div className="modal-backdrop" onClick={onClose}>
    <div className="modal" onClick={(e) => e.stopPropagation()}>
      <div className="title-row">
        <h3>{title}</h3>
        <button className="secondary" onClick={onClose}>
          Закрити
        </button>
      </div>
      {children}
    </div>
  </div>
);

