import { NextResponse } from "next/server";
import { gastroReservasBaseUrl } from "@/lib/gastro-reservas-proxy";

export const dynamic = "force-dynamic";

/** Opciones de mesa para reserva web (delega en Gastro). */
export async function GET(req: Request) {
  const base = gastroReservasBaseUrl();
  if (!base) {
    return NextResponse.json(
      { ok: false, error: "GASTRO_RESERVAS_BASE_URL no configurada" },
      { status: 500 },
    );
  }
  const u = new URL(req.url);
  const gastroUrl = `${base}/api/web/reservas/opciones-mesa?${u.searchParams.toString()}`;
  try {
    const r = await fetch(gastroUrl, { cache: "no-store", signal: AbortSignal.timeout(15_000) });
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": r.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error:
          "No se pudo conectar con Gastro (opciones de mesa). Revisa GASTRO_RESERVAS_BASE_URL y que gastro-app esté en marcha.",
      },
      { status: 503 },
    );
  }
}
