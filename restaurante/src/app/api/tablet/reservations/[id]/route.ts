import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";
import { notifyReservationChange } from "@/lib/reservation-events";
import { prepareReservationPatch } from "@/lib/reservation-patch-server";

export const dynamic = "force-dynamic";

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const sessionEmployee = await getTabletEmployeeId();
  if (!sessionEmployee) {
    return NextResponse.json({ error: "Sin sesión tablet" }, { status: 401 });
  }

  const active = await prisma.employee.findFirst({ where: { id: sessionEmployee, active: true } });
  if (!active) {
    return NextResponse.json({ error: "Empleado inactivo" }, { status: 403 });
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
