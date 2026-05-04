import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { requireAdminOrTabletSession } from "@/lib/auth-dining";
import { rankTableSuggestions } from "@/lib/table-assignment-suggest";

export const dynamic = "force-dynamic";

const NEW_ID = "__suggest_new__";

/**
 * POST { reservationId } o { partySize, startsAt, endsAt? }.
 * Devuelve mesas candidatas ordenadas (mejor aprovechamiento de aforo sin solapes).
 */
export async function POST(req: Request) {
  const denied = await requireAdminOrTabletSession();
  if (denied) return denied;

  const body = (await req.json().catch(() => null)) as {
    reservationId?: string;
    partySize?: number;
    startsAt?: string;
    endsAt?: string | null;
  } | null;

  if (!body) {
    return NextResponse.json({ error: "Cuerpo JSON inválido" }, { status: 400 });
  }

  let partySize: number;
  let startsAt: Date;
  let endsAt: Date | null;
  let excludeReservationId: string;

  if (body.reservationId) {
    const r = await prisma.reservation.findUnique({ where: { id: body.reservationId } });
    if (!r) {
      return NextResponse.json({ error: "Reserva no encontrada" }, { status: 404 });
    }
    partySize = r.partySize;
    startsAt = r.startsAt;
    endsAt = r.endsAt;
    excludeReservationId = r.id;
  } else {
    partySize = Number(body.partySize);
    startsAt = new Date(body.startsAt ?? "");
    endsAt =
      body.endsAt != null && String(body.endsAt).trim() !== ""
        ? new Date(body.endsAt as string)
        : null;
    excludeReservationId = NEW_ID;

    if (!Number.isFinite(partySize) || partySize < 1 || Number.isNaN(startsAt.getTime())) {
      return NextResponse.json({ error: "partySize o startsAt inválidos" }, { status: 400 });
    }
    if (endsAt && Number.isNaN(endsAt.getTime())) {
      return NextResponse.json({ error: "endsAt no válido" }, { status: 400 });
    }
  }

  const suggestions = await rankTableSuggestions(prisma, {
    partySize,
    startsAt,
    endsAt,
    excludeReservationId,
  });

  return NextResponse.json({
    suggestions,
    meta: {
      partySize,
      startsAt: startsAt.toISOString(),
      endsAt: endsAt?.toISOString() ?? null,
    },
  });
}
