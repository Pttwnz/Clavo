import type { Locale, MenuItem } from "@/lib/menu-types";

/** Orden de bloques como en la carta impresa (pág. 1 + 2). */
export const FOLLETO_CATEGORY_ORDER = [
  "Promociones",
  "Tapas",
  "Tostas",
  "Carnes",
  "Pan y extras",
  "Postres",
  "Cervezas",
  "Refrescos",
  "Copas",
  "Cafés",
  "Blancos",
  "Tintos",
  "Rosados",
  "Vermú",
  "Cavas",
] as const;

const ALLERGEN_KEYS: [string, number][] = [
  ["soja", 1],
  ["moluscos", 2],
  ["pescado", 3],
  ["crustáceos", 4],
  ["lácteos", 5],
  ["huevo", 6],
  ["gluten", 7],
  ["altramuces", 8],
  ["apio", 9],
  ["sésamo", 10],
  ["mostaza", 11],
  ["cacahuetes", 12],
  ["sulfitos", 13],
  ["frutos secos", 14],
];

export function allergenCodesFromSpanish(s: string | undefined): number[] {
  if (!s) return [];
  const low = s.toLowerCase();
  const out: number[] = [];
  for (const [key, code] of ALLERGEN_KEYS) {
    if (low.includes(key)) out.push(code);
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

export function itemsByCategoryEs(items: MenuItem[], catEs: string): MenuItem[] {
  return items.filter((m) => m.category.es === catEs);
}

export function splitTapasColumns(items: MenuItem[]): { left: MenuItem[]; right: MenuItem[] } {
  const tapas = itemsByCategoryEs(items, "Tapas");
  const mid = Math.ceil(tapas.length / 2);
  return { left: tapas.slice(0, mid), right: tapas.slice(mid) };
}

export function priceLine(m: MenuItem, lang: Locale): string {
  const pt = m.priceText?.[lang];
  if (pt) return pt.replace(/\s/g, "\u00a0").replace(/€/g, "€");
  if (m.price > 0) {
    const n = Number.isInteger(m.price) ? String(m.price) : m.price.toFixed(2).replace(".", ",");
    return `${n}\u00a0€`;
  }
  return "";
}

export function dishName(m: MenuItem, lang: Locale): string {
  return m.name[lang];
}

export function dishDesc(m: MenuItem, lang: Locale): string {
  return m.description[lang];
}

export type LegendRow = { id: number } & Record<Locale, string>;

function lr(
  id: number,
  es: string,
  en: string,
  fr: string,
  de: string,
  ca?: string,
  it?: string,
  pt?: string,
): LegendRow {
  return { id, es, en, fr, de, ca: ca ?? es, it: it ?? en, pt: pt ?? en };
}

export function legendLabel(lang: Locale, row: LegendRow): string {
  return row[lang];
}

export const LEGEND: LegendRow[] = [
  lr(1, "Soja", "Soy", "Soja", "Soja", "Soja", "Soia", "Soja"),
  lr(2, "Moluscos", "Molluscs", "Mollusques", "Weichtiere", "Moluscos", "Molluschi", "Moluscos"),
  lr(3, "Pescado", "Fish", "Poisson", "Fisch", "Peix", "Pesce", "Peixe"),
  lr(4, "Crustáceos", "Crustaceans", "Crustacés", "Krebstiere", "Crustacis", "Crostacei", "Crustáceos"),
  lr(5, "Lácteos", "Dairy", "Produits laitiers", "Milch", "Làctics", "Latticini", "Laticínios"),
  lr(6, "Huevo", "Egg", "Œuf", "Ei", "Ou", "Uovo", "Ovo"),
  lr(7, "Gluten", "Gluten", "Gluten", "Gluten", "Gluten", "Glutine", "Glúten"),
  lr(8, "Altramuces", "Lupins", "Lupin", "Lupinen", "Tramussos", "Lupini", "Tremoço"),
  lr(9, "Apio", "Celery", "Céleri", "Sellerie", "Api", "Sedano", "Aipo"),
  lr(10, "Sésamo", "Sesame", "Sésame", "Sesam", "Sèsam", "Sesamo", "Sésamo"),
  lr(11, "Mostaza", "Mustard", "Moutarde", "Senf", "Mostassa", "Senape", "Mostarda"),
  lr(12, "Cacahuetes", "Peanuts", "Arachides", "Erdnüsse", "Cacauets", "Arachidi", "Amendoins"),
  lr(13, "Sulfitos", "Sulphites", "Sulfites", "Sulfite", "Sulfits", "Solfiti", "Sulfitos"),
  lr(14, "Frutos secos", "Tree nuts", "Fruits à coque", "Schalenfrüchte", "Fruits secs", "Frutta a guscio", "Frutos de casca rija"),
];
