import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { notifyReservationChange } from "@/lib/reservation-events";
import { prepareReservationPatch } from "@/lib/reservation-patch-server";

export const dynamic = "force-dynamic";

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const { id } = await ctx.params;
  const body = await req.json().catch(() => null);
  const prepared = await prepareReservationPatch(id, body);
  if (!prepared.ok) {
    return NextResponse.json({ error: prepared.error }, { status: prepared.status });
  }

  const updated = await prisma.reservation.update({
    where: { id },
    data: prepared.data,
    include: { diningTable: true },
  });
  notifyReservationChange();
  return NextResponse.json(updated);
}
