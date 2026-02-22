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

export const In = ({ onChange, onKeyDown, tip, placeholder, ...props }) => (
  <label className="field">
    {(props.label || placeholder || tip) && <span className="field-label">{props.label || placeholder || tip}</span>}
    <input
      title={tip || placeholder || ""}
      {...props}
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
  </label>
);

export const Se = ({ tip, children, onKeyDown, ...props }) => (
  <label className="field">
    {(props.label || props.placeholder || tip) && <span className="field-label">{props.label || props.placeholder || tip}</span>}
    <select
      title={tip || ""}
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
  </label>
);

export const Ta = ({ onKeyDown, tip, placeholder, ...props }) => (
  <label className="field">
    {(props.label || placeholder || tip) && <span className="field-label">{props.label || placeholder || tip}</span>}
    <textarea
      title={tip || placeholder || ""}
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
  </label>
);
