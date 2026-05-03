export type Locale = "es" | "en" | "fr" | "de" | "ca" | "it" | "pt";

export const locales: Locale[] = ["es", "en", "fr", "de", "ca", "it", "pt"];

export const localeLabels: Record<Locale, string> = {
  es: "Español",
  en: "English",
  fr: "Français",
  de: "Deutsch",
  ca: "Català",
  it: "Italiano",
  pt: "Português",
};

export type MenuItem = {
  id: string;
  name: Record<Locale, string>;
  description: Record<Locale, string>;
  /** Precio simple; si hay `priceText`, la UI prioriza la cadena. */
  price: number;
  category: Record<Locale, string>;
  /** Alérgenos u otras notas (leyenda carta física). */
  allergens?: Record<Locale, string>;
  /** Sustituye el precio numérico (p. ej. vinos copa/botella, promos). */
  priceText?: Record<Locale, string>;
  /** Si es true, el plato no se muestra en la carta web pública (/menu, /carta); en el panel sigue apareciendo para reactivarlo. */
  hiddenFromPublic?: boolean;
};

/** Orden de secciones en español (clave de `category.es`). */
export const menuCategoryOrderEs: string[] = [
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
];
