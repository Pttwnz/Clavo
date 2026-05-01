function mergedHostRoot(): boolean {
  const v = (process.env.NEXT_PUBLIC_MERGED_HOST_ROOT || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

/**
 * Base pública de gastro-app (Flask) para enlaces en el navegador.
 * Con `NEXT_PUBLIC_MERGED_HOST_ROOT=1` (Nginx: Next + Gastro en el mismo host) devuelve cadena
 * vacía para usar rutas relativas (`/panel`, `/login`) y no forzar IP ni otro origen.
 */
export function publicGastroBaseUrl(): string {
  if (mergedHostRoot()) {
    return "";
  }
  const raw = (process.env.NEXT_PUBLIC_GASTRO_BASE_URL || "http://127.0.0.1:5050").trim();
  return raw.replace(/\/$/, "") || "http://127.0.0.1:5050";
}

/** Panel de gestión Gastro Manager (misma base que `publicGastroBaseUrl`). */
export function gastroPanelUrl(): string {
  const base = publicGastroBaseUrl();
  return base ? `${base}/panel` : "/panel";
}
