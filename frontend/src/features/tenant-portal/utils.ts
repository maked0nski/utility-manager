export function nowYearMonth() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

export function invoiceStatusLabel(status: string): string {
  if (status === "paid") return "Оплачено";
  if (status === "unpaid") return "Не оплачено";
  return status;
}

export function localizeApiError(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  const message = (error.message || "").trim();
  if (!message) return fallback;
  if (message === "Invalid credentials.") return "Невірний email або пароль.";
  if (message === "Tenant portal is disabled.") return "Кабінет орендаря вимкнений адміністратором.";
  if (message === "Tenant not found.") return "Орендаря з таким email не знайдено.";
  if (message === "Invalid access code.") return "Невірний код доступу орендаря.";
  if (message === "Password is not set.") return "Для цього кабінету ще не налаштовано пароль.";
  if (message === "Email already exists.") return "Такий email вже використовується.";
  if (message === "Password confirmation does not match.") return "Підтвердження пароля не збігається.";
  if (message === "Password must be at least 8 characters.") return "Новий пароль має містити щонайменше 8 символів.";
  if (message.includes("uppercase")) return "Новий пароль має містити хоча б одну велику літеру.";
  if (message.includes("lowercase")) return "Новий пароль має містити хоча б одну малу літеру.";
  if (message.includes("digit")) return "Новий пароль має містити хоча б одну цифру.";
  if (message === "Tenant cannot submit meter readings.") return "Адміністратор вимкнув можливість подавати показники.";
  if (message.includes("Meter not found")) return "Вибраний лічильник не знайдено для цього об'єкта.";
  if (message === "Meter is archived.") return "Лічильник архівовано, подача показників неможлива.";
  if (message === "Tenant is not assigned to any apartment.") return "Орендар ще не прив'язаний до жодного об'єкта.";
  return message;
}
