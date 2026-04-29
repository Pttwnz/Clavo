import { locales, type Locale } from "./menu-types";
import { menuCartaResolvedPages } from "./menu-carta-fs";

/** URLs de carta servidas por `/api/menu-carta/file` (lectura desde `public/` en el servidor). */
export function resolveMenuCartaImagePaths(locale: Locale): { src: string; page: number }[] {
  return menuCartaResolvedPages(locale);
}

export function resolveAllMenuCartaImages(): Record<Locale, { src: string; page: number }[]> {
  const r = {} as Record<Locale, { src: string; page: number }[]>;
  for (const l of locales) {
    r[l] = resolveMenuCartaImagePaths(l);
  }
  return r;
}
