import fs from "node:fs";
import path from "node:path";
import type { Locale } from "./menu-types";

export const MENU_CARTA_EXT = [".webp", ".png", ".jpg", ".jpeg", ".svg"] as const;

const MAX_PAGE = 4;

export function menuCartaMime(ext: string): string {
  const e = ext.toLowerCase();
  if (e === ".webp") return "image/webp";
  if (e === ".png") return "image/png";
  if (e === ".jpg" || e === ".jpeg") return "image/jpeg";
  if (e === ".svg") return "image/svg+xml";
  return "application/octet-stream";
}

/** Directorio `public` del proyecto (Next en Docker: `/app/public`). */
export function menuCartaPublicDirs(): string[] {
  const cwd = process.cwd();
  const candidates = [
    path.join(cwd, "public"),
    path.join(cwd, "..", "public"),
    path.join(cwd, "restaurante", "public"),
    path.join(cwd, "..", "restaurante", "public"),
  ];
  const seen = new Set<string>();
  return candidates.filter((p) => {
    const n = path.normalize(p);
    if (seen.has(n)) return false;
    seen.add(n);
    return fs.existsSync(n);
  });
}

function primaryPublicDir(): string {
  const dirs = menuCartaPublicDirs();
  return dirs[0] ?? path.join(process.cwd(), "public");
}

/** Resuelve `carta-{page}` con extensión conocida, solo en `public/taberna/menu/{lang}/` (sin fallback de idioma). */
export function menuCartaExactFile(lang: Locale, page: number): { absPath: string; ext: string } | null {
  if (page < 1 || page > MAX_PAGE) return null;
  const dirs = menuCartaPublicDirs();
  const list = dirs.length ? dirs : [primaryPublicDir()];
  for (const publicDir of list) {
    for (const ext of MENU_CARTA_EXT) {
      const rel = path.join("taberna", "menu", lang, `carta-${page}${ext}`);
      const abs = path.join(publicDir, rel);
      const normPublic = path.normalize(publicDir);
      const normAbs = path.normalize(abs);
      const relCheck = path.relative(normPublic, normAbs);
      if (relCheck.startsWith("..") || path.isAbsolute(relCheck)) continue;
      if (fs.existsSync(abs)) return { absPath: abs, ext };
    }
  }
  return null;
}

/**
 * Para un idioma de UI: busca carta-{page} probando carpetas de idioma (locale → es).
 * Devuelve URL servida por Next (`/api/menu-carta/file?...`), no ruta estática `/taberna/...`
 * (así Nginx no tiene que servir archivos bajo `/taberna` y evitamos 404 opacos).
 */
export function menuCartaPageApiUrl(viewerLocale: Locale, page: number): string | null {
  if (page < 1 || page > MAX_PAGE) return null;
  const chain: Locale[] = viewerLocale === "es" ? ["es"] : [viewerLocale, "es"];
  const seen = new Set<string>();
  for (const loc of chain) {
    if (seen.has(loc)) continue;
    seen.add(loc);
    if (menuCartaExactFile(loc, page)) {
      return `/api/menu-carta/file?lang=${encodeURIComponent(loc)}&page=${String(page)}`;
    }
  }
  return null;
}

export function menuCartaResolvedPages(viewerLocale: Locale): { src: string; page: number }[] {
  const out: { src: string; page: number }[] = [];
  for (let page = 1; page <= MAX_PAGE; page++) {
    const src = menuCartaPageApiUrl(viewerLocale, page);
    if (src) out.push({ src, page });
  }
  /** Asegura al menos páginas 1 y 2 (404 en API → placeholder en el cliente si faltan archivos). */
  for (let page = 1; page <= 2; page++) {
    if (!out.some((o) => o.page === page)) {
      out.push({ src: `/api/menu-carta/file?lang=es&page=${String(page)}`, page });
    }
  }
  out.sort((a, b) => a.page - b.page);
  return out;
}

export { MAX_PAGE as MENU_CARTA_MAX_PAGE };
