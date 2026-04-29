/**
 * Si existe GASTRO_RESERVAS_BASE_URL, las rutas /api/reservations* delegan en gastro-app (Flask).
 */
export function gastroReservasBaseUrl(): string | null {
  const raw =
    (process.env.GASTRO_RESERVAS_BASE_URL || process.env.NEXT_PUBLIC_GASTRO_BASE_URL || "").trim();
  if (!raw) return null;
  return raw.replace(/\/$/, "");
}

export async function proxyJsonToGastro(
  gastroPath: string,
  init?: RequestInit,
): Promise<Response> {
  const base = gastroReservasBaseUrl();
  if (!base) {
    return new Response(JSON.stringify({ error: "GASTRO_RESERVAS_BASE_URL no configurada" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
  const url = `${base}${gastroPath.startsWith("/") ? "" : "/"}${gastroPath}`;
  return fetch(url, {
    ...init,
    headers: {
      ...(init?.headers as Record<string, string>),
    },
    cache: "no-store",
  });
}
