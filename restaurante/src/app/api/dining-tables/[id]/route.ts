import { NextResponse } from "next/server";
import { Prisma } from "@/generated/prisma/client";
import { prisma } from "@/lib/db";
import { notifyReservationChange } from "@/lib/reservation-events";
import { requireAdminOrTabletSession } from "@/lib/auth-dining";

export const dynamic = "force-dynamic";

/** Ocupación manual walk-in (panel / tablet). Requiere sesión admin o tablet. */
export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const denied = await requireAdminOrTabletSession();
  if (denied) return denied;

  const { id } = await ctx.params;
  const body = await req.json().catch(() => null) as {
    walkInOccupied?: boolean;
    walkInPartySize?: number | null;
  } | null;

  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "Cuerpo inválido" }, { status: 400 });
  }

  const existing = await prisma.diningTable.findFirst({ where: { id, active: true } });
  if (!existing) {
    return NextResponse.json({ error: "Mesa no encontrada" }, { status: 404 });
  }

  const data: Prisma.DiningTableUpdateInput = {};

  if (body.walkInOccupied !== undefined) {
    const occupied = Boolean(body.walkInOccupied);
    data.walkInOccupied = occupied;
    if (occupied) {
      if (!existing.walkInOccupied) {
        data.walkInStartedAt = new Date();
      }
    } else {
      data.walkInPartySize = null;
      data.walkInStartedAt = null;
    }
  }

  if (body.walkInPartySize !== undefined) {
    if (body.walkInPartySize === null) {
      data.walkInPartySize = null;
    } else {
      const p = Number(body.walkInPartySize);
      if (!Number.isFinite(p) || p < 1 || p > 99) {
        return NextResponse.json({ error: "Comensales entre 1 y 99" }, { status: 400 });
      }
      data.walkInPartySize = Math.floor(p);
    }
  }

  if (Object.keys(data).length === 0) {
    return NextResponse.json({ error: "Nada que actualizar" }, { status: 400 });
  }

  try {
    const updated = await prisma.diningTable.update({
      where: { id },
      data,
    });
    notifyReservationChange();
    return NextResponse.json(updated);
  } catch (e) {
    console.error("[PATCH /api/dining-tables/[id]]", e);
    if (e instanceof Prisma.PrismaClientValidationError) {
      return NextResponse.json(
        {
          error:
            "Cliente de base de datos desactualizado. Para el servidor (`next dev` o el proceso de producción), ejecuta `npx prisma generate` y vuelve a arrancar.",
        },
        { status: 503 },
      );
    }
    return NextResponse.json({ error: "No se pudo actualizar la mesa" }, { status: 500 });
  }
}
