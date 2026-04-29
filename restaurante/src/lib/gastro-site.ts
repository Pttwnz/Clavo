/** Base pública de gastro-app (Flask). Requiere `NEXT_PUBLIC_*` para usarse en el cliente. */
export function publicGastroBaseUrl(): string {
  const raw = (process.env.NEXT_PUBLIC_GASTRO_BASE_URL || "http://127.0.0.1:5050").trim();
  return raw.replace(/\/$/, "") || "http://127.0.0.1:5050";
}

/** Panel de gestión Gastro Manager (misma base que `publicGastroBaseUrl`). */
export function gastroPanelUrl(): string {
  return `${publicGastroBaseUrl()}/panel`;
}
