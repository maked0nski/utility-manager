const focusNextFieldOrSubmit = (current) => {
  if (!current) return;
  const root = current.closest(".card, .modal, .subcard, .auth-card") || document.body;
  const nodes = Array.from(root.querySelectorAll("input, select, textarea, button")).filter((el) => {
    if (!el) return false;
    if (el.disabled) return false;
    const hidden = el.type === "hidden" || el.getAttribute("aria-hidden") === "true";
    return !hidden;
  });
  const idx = nodes.indexOf(current);
  for (let i = idx + 1; i < nodes.length; i += 1) {
    const el = nodes[i];
    if (el && typeof el.focus === "function") {
      el.focus();
      return;
    }
  }
  const btn = nodes.find((el) => el.tagName === "BUTTON" && typeof el.click === "function");
  if (btn) btn.click();
};

const normalizeNumericLike = (value) => {
  const raw = String(value ?? "");
  if (!raw.includes(",")) return raw;
  if (/^[\d\s,.\-+]*$/.test(raw)) return raw.replaceAll(",", ".");
  return raw;
};

export const In = ({ onChange, onKeyDown, tip, placeholder, help, ...props }) => (
  <label className="field">
    {(props.label || tip) && <span className="field-label">{props.label || tip}</span>}
    <input
      title={help || tip || placeholder || ""}
      {...props}
      type={props.type === "number" ? "text" : props.type}
      inputMode={props.type === "number" ? "decimal" : props.inputMode}
      onChange={(e) => {
        const nextValue = normalizeNumericLike(e.target.value);
        if (nextValue !== e.target.value) e.target.value = nextValue;
        onChange?.(e);
      }}
      onKeyDown={(e) => {
        onKeyDown?.(e);
        if (e.defaultPrevented) return;
        if (e.key === "Enter") {
          e.preventDefault();
          focusNextFieldOrSubmit(e.currentTarget);
        }
      }}
    />
    {help ? <span className="field-help">{help}</span> : null}
  </label>
);

export const Se = ({ tip, children, onKeyDown, help, ...props }) => (
  <label className="field">
    {(props.label || tip) && <span className="field-label">{props.label || tip}</span>}
    <select
      title={help || tip || ""}
      {...props}
      onKeyDown={(e) => {
        onKeyDown?.(e);
        if (e.defaultPrevented) return;
        if (e.key === "Enter") {
          e.preventDefault();
          focusNextFieldOrSubmit(e.currentTarget);
        }
      }}
    >
      {children}
    </select>
    {help ? <span className="field-help">{help}</span> : null}
  </label>
);

export const Ta = ({ onKeyDown, tip, placeholder, help, ...props }) => (
  <label className="field">
    {(props.label || tip) && <span className="field-label">{props.label || tip}</span>}
    <textarea
      title={help || tip || placeholder || ""}
      {...props}
      onKeyDown={(e) => {
        onKeyDown?.(e);
        if (e.defaultPrevented) return;
        if (e.key === "Enter" && e.ctrlKey) {
          e.preventDefault();
          focusNextFieldOrSubmit(e.currentTarget);
        }
      }}
    />
    {help ? <span className="field-help">{help}</span> : null}
  </label>
);
