import type { Locale, MenuItem } from "@/lib/menu-types";

const LOCALES: Locale[] = ["es", "en", "fr", "de", "ca", "it", "pt"];

function isLocaleRecord(x: unknown): x is Record<Locale, string> {
  if (!x || typeof x !== "object") return false;
  const o = x as Record<string, unknown>;
  return LOCALES.every((l) => typeof o[l] === "string");
}

function parseOptionalLocaleRecord(x: unknown): Record<Locale, string> | undefined {
  if (x === undefined || x === null) return undefined;
  if (!isLocaleRecord(x)) return undefined;
  return x;
}

/**
 * Valida y parsea un JSON de carta. Devuelve `null` si el formato no es válido.
 */
export function parseMenuItemsJson(json: string): MenuItem[] | null {
  let data: unknown;
  try {
    data = JSON.parse(json);
  } catch {
    return null;
  }
  if (!Array.isArray(data)) return null;
  const out: MenuItem[] = [];
  for (const row of data) {
    if (!row || typeof row !== "object") return null;
    const r = row as Record<string, unknown>;
    if (typeof r.id !== "string" || !r.id.trim()) return null;
    if (!isLocaleRecord(r.name)) return null;
    if (!isLocaleRecord(r.description)) return null;
    if (!isLocaleRecord(r.category)) return null;
    const priceRaw = r.price;
    const price =
      typeof priceRaw === "number" && Number.isFinite(priceRaw)
        ? priceRaw
        : typeof priceRaw === "string" && priceRaw.trim()
          ? Number(priceRaw.replace(",", "."))
          : NaN;
    if (!Number.isFinite(price)) return null;
    const m: MenuItem = {
      id: r.id.trim(),
      name: r.name,
      description: r.description,
      price,
      category: r.category,
    };
    const allergens = parseOptionalLocaleRecord(r.allergens);
    if (allergens) m.allergens = allergens;
    const priceText = parseOptionalLocaleRecord(r.priceText);
    if (priceText) m.priceText = priceText;
    out.push(m);
  }
  return out;
}
