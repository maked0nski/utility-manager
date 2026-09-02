import { useEffect, useRef, useState } from "react";

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

// ISO "YYYY-MM-DD" <-> 8 raw digits <-> "DD.MM.YYYY" display, so every date field
// on the site shows the same order regardless of the browser's own UI language
// (native <input type="date"> renders its closed-state text per browser locale,
// not per page `lang`, which is what caused the site-wide DD/MM vs MM/DD drift).
const isoToDigits = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
  return m ? `${m[3]}${m[2]}${m[1]}` : "";
};

const digitsToDisplay = (digits) => {
  const dd = digits.slice(0, 2);
  const mm = digits.slice(2, 4);
  const yyyy = digits.slice(4, 8);
  return [dd, mm, yyyy].filter(Boolean).join(".");
};

const digitsToIso = (digits) => {
  if (digits.length !== 8) return null;
  const dd = digits.slice(0, 2);
  const mm = digits.slice(2, 4);
  const yyyy = digits.slice(4, 8);
  const day = Number(dd);
  const month = Number(mm);
  const year = Number(yyyy);
  if (month < 1 || month > 12) return null;
  const daysInMonth = new Date(year, month, 0).getDate();
  if (day < 1 || day > daysInMonth) return null;
  return `${yyyy}-${mm}-${dd}`;
};

const DateIn = ({ value, onChange, onKeyDown, tip, placeholder, help, label, disabled, ...rest }) => {
  const [digits, setDigits] = useState(() => isoToDigits(value));
  const lastEmittedRef = useRef(value ?? "");

  useEffect(() => {
    const incoming = value ?? "";
    if (incoming !== lastEmittedRef.current) {
      setDigits(isoToDigits(incoming));
      lastEmittedRef.current = incoming;
    }
  }, [value]);

  return (
    <label className="field">
      {(label || tip) && <span className="field-label">{label || tip}</span>}
      <input
        title={help || tip || placeholder || ""}
        {...rest}
        type="text"
        inputMode="numeric"
        placeholder={placeholder || "ДД.ММ.РРРР"}
        disabled={disabled}
        value={digitsToDisplay(digits)}
        onChange={(e) => {
          const nextDigits = e.target.value.replace(/\D/g, "").slice(0, 8);
          setDigits(nextDigits);
          const iso = digitsToIso(nextDigits);
          if (iso !== null || nextDigits.length === 0) {
            const nextValue = iso ?? "";
            lastEmittedRef.current = nextValue;
            onChange?.({ target: { value: nextValue } });
          }
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
};

export const In = ({ onChange, onKeyDown, tip, placeholder, help, ...props }) => {
  if (props.type === "date") {
    return (
      <DateIn
        value={props.value}
        disabled={props.disabled}
        label={props.label}
        tip={tip}
        placeholder={placeholder}
        help={help}
        onChange={onChange}
        onKeyDown={onKeyDown}
      />
    );
  }
  return (
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
};

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
