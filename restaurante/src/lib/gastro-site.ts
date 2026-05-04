function mergedHostRoot(): boolean {
  const v = (process.env.NEXT_PUBLIC_MERGED_HOST_ROOT || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

/**
 * Base pública de gastro-app (Flask) para enlaces en el navegador.
 * Con `NEXT_PUBLIC_MERGED_HOST_ROOT=1` (Nginx: Next + Gastro en el mismo host) devuelve cadena
 * vacía para usar rutas relativas (`/panel`, `/acceso-interno`, etc.) y no forzar IP ni otro origen.
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

/**
 * Hub donde el usuario elige acceso administrador, personal o tablet (Flask: `login_selector`).
 * Con host fusionado Nginx envía `/login` a Gastro (solo formulario admin); hay que usar `/acceso-interno`.
 * Sin fusionar, la entrada es la raíz del servidor Gastro (`/?next=`).
 */
export function gastroAccessHubUrl(nextPath: string = "/panel"): string {
  const next = nextPath.trim() || "/panel";
  const q = `?next=${encodeURIComponent(next)}`;
  if (mergedHostRoot()) {
    return `/acceso-interno${q}`;
  }
  const base = (process.env.NEXT_PUBLIC_GASTRO_BASE_URL || "http://127.0.0.1:5050").trim().replace(/\/$/, "");
  const origin = base || "http://127.0.0.1:5050";
  return `${origin}/${q}`;
}

/**
 * Entrada modo tablet del local (Flask: PIN en `/tablet/acceso`).
 * Recepción Next: usa `/recepcion?reauth=1` para obligar de nuevo empleado + PIN (cierra cookie `clavo_tablet`).
 */
export function gastroTabletAccesoUrl(): string {
  const base = publicGastroBaseUrl();
  return base ? `${base}/tablet/acceso` : "/tablet/acceso";
}
