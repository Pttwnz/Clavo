import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { notifyReservationChange } from "@/lib/reservation-events";

export const dynamic = "force-dynamic";

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const { id } = await ctx.params;
  const body = await req.json().catch(() => null) as {
    label?: string;
    zone?: string | null;
    capacity?: number;
    sortOrder?: number;
    active?: boolean;
  } | null;

  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "Cuerpo inválido" }, { status: 400 });
  }

  const existing = await prisma.diningTable.findUnique({ where: { id } });
  if (!existing) {
    return NextResponse.json({ error: "No encontrada" }, { status: 404 });
  }

  const data: {
    label?: string;
    zone?: string | null;
    capacity?: number;
    sortOrder?: number;
    active?: boolean;
  } = {};

  if (body.label !== undefined) {
    if (typeof body.label !== "string" || !body.label.trim()) {
      return NextResponse.json({ error: "Etiqueta inválida" }, { status: 400 });
    }
    data.label = body.label.trim();
  }
  if (body.zone !== undefined) {
    data.zone = typeof body.zone === "string" ? body.zone.trim() || null : null;
  }
  if (body.capacity !== undefined) {
    const c = Number(body.capacity);
    if (!Number.isFinite(c) || c < 1) {
      return NextResponse.json({ error: "Capacidad inválida" }, { status: 400 });
    }
    data.capacity = Math.floor(c);
  }
  if (body.sortOrder !== undefined) {
    const s = Number(body.sortOrder);
    data.sortOrder = Number.isFinite(s) ? Math.floor(s) : 0;
  }
  if (body.active !== undefined) {
    data.active = Boolean(body.active);
  }

  if (Object.keys(data).length === 0) {
    return NextResponse.json({ error: "Nada que actualizar" }, { status: 400 });
  }

  const updated = await prisma.diningTable.update({
    where: { id },
    data,
  });

  if (data.label !== undefined && data.label !== existing.label) {
    await prisma.reservation.updateMany({
      where: { tableId: id },
      data: { assignedTable: data.label },
    });
  }

  notifyReservationChange();
  return NextResponse.json(updated);
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const { id } = await ctx.params;

  const n = await prisma.reservation.count({ where: { tableId: id } });
  if (n > 0) {
    return NextResponse.json(
      { error: `Hay ${n} reserva(s) con esta mesa. Desactívala o reasigna antes de borrar.` },
      { status: 409 },
    );
  }

  await prisma.diningTable.delete({ where: { id } });
  notifyReservationChange();
  return NextResponse.json({ ok: true });
}
