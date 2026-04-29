import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { gastroReservasBaseUrl } from "@/lib/gastro-reservas-proxy";
import { evaluateWebBookingQuota, getWebQuotaForInstant } from "@/lib/web-booking-quota";
import { validateWebLeadTime } from "@/lib/reservation-create-guards";

export const dynamic = "force-dynamic";

/** Cupo web para una fecha/hora (formulario público). Si viene `partySize`, valida que quepa. */
export async function GET(req: Request) {
  const base = gastroReservasBaseUrl();
  if (base) {
    const u = new URL(req.url);
    const gastroUrl = `${base}/api/web/reservas/disponibilidad?${u.searchParams.toString()}`;
    let r: Response;
    try {
      r = await fetch(gastroUrl, { cache: "no-store", signal: AbortSignal.timeout(15_000) });
    } catch {
      return NextResponse.json(
        {
          ok: false,
          message:
            "No se pudo conectar con Gastro (reservas). Arranca gastro-app (p. ej. python app.py en restaurante/gastro-app, puerto 5050) y revisa GASTRO_RESERVAS_BASE_URL en .env de la web.",
        },
        { status: 503 },
      );
    }
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": r.headers.get("content-type") || "application/json" },
    });
  }

  const { searchParams } = new URL(req.url);
  const startsRaw = searchParams.get("startsAt");
  const partyRaw = searchParams.get("partySize");
  if (!startsRaw) {
    return NextResponse.json({ error: "Falta startsAt" }, { status: 400 });
  }
  const startsAt = new Date(startsRaw);
  if (Number.isNaN(startsAt.getTime())) {
    return NextResponse.json({ error: "Fecha no válida" }, { status: 400 });
  }
  const lead = validateWebLeadTime(startsAt, 30);
  if (!lead.ok) {
    return NextResponse.json({ ok: false, message: lead.message });
  }

  if (partyRaw === null || partyRaw === "") {
    const snap = await getWebQuotaForInstant(prisma, startsAt);
    if (!snap.inSlot) {
      return NextResponse.json({ ok: false, message: snap.message });
    }
    return NextResponse.json({
      ok: true,
      slotLabel: snap.slot.label,
      webPercent: snap.slot.webPercent,
      quota: snap.quota,
      used: snap.used,
      remaining: snap.remaining,
      totalSeats: snap.totalSeats,
    });
  }

  const partySize = Number(partyRaw);
  if (!Number.isFinite(partySize) || partySize < 1) {
    return NextResponse.json({ error: "Comensales no válidos" }, { status: 400 });
  }

  const q = await evaluateWebBookingQuota(prisma, startsAt, partySize);
  if (!q.ok) {
    return NextResponse.json({
      ok: false,
      message: q.message,
    });
  }
  return NextResponse.json({
    ok: true,
    slotLabel: q.slot.label,
    webPercent: q.slot.webPercent,
    quota: q.quota,
    used: q.used,
    remaining: q.remaining,
    totalSeats: q.totalSeats,
  });
}
