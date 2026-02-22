export const DEFAULT_SERVICE_SEQUENCE = [
  "Квартплата",
  "Газопостачання",
  "За розподіл (доставку) газу",
  "Вивіз сміття",
  "Електроенергія День",
  "Електроенергія Ніч",
  "Абонентська плата (водоканал)",
  "Водовідведення",
  "Водопостачання",
  "За автоматику на воротах",
  "За домофон",
  "Інтернет",
];

const SERVICE_ORDER_INDEX: Record<string, number> = Object.fromEntries(
  DEFAULT_SERVICE_SEQUENCE.map((name, idx) => [name, idx]),
);

export const canonicalServiceName = (serviceName: string | null | undefined): string => {
  const s = String(serviceName || "").trim().toLowerCase();
  if (s === "квартплата") return "Квартплата";
  if (s.includes("газопостач")) return "Газопостачання";
  if (s.includes("розпод") && s.includes("газ")) return "За розподіл (доставку) газу";
  if (s.includes("сміт")) return "Вивіз сміття";
  if (s.includes("електро") && (s.includes("день") || s.includes("денн"))) return "Електроенергія День";
  if (s.includes("електро") && (s.includes("ніч") || s.includes("нічн"))) return "Електроенергія Ніч";
  if (s.includes("абонент") && s.includes("вод")) return "Абонентська плата (водоканал)";
  if (s.includes("водовідвед")) return "Водовідведення";
  if (s.includes("водопостач")) return "Водопостачання";
  if (s.includes("автоматик") && s.includes("ворот")) return "За автоматику на воротах";
  if (s.includes("домоф")) return "За домофон";
  if (s.includes("інтернет") || s.includes("internet")) return "Інтернет";
  return String(serviceName || "").trim();
};

export const defaultServiceOrderScore = (row: { service_name?: string | null }): number => {
  if (String(row.service_name || "").startsWith("Відшкодування:")) return 9000;
  const normalized = canonicalServiceName(row.service_name);
  const idx = SERVICE_ORDER_INDEX[normalized];
  if (idx !== undefined) return idx;
  return 5000;
};
