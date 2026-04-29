import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { notifyReservationChange } from "@/lib/reservation-events";

export const dynamic = "force-dynamic";

function parseTimeToMinutes(s: string): number | null {
  const m = s.trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (!Number.isFinite(h) || !Number.isFinite(min) || h > 23 || min > 59) return null;
  return h * 60 + min;
}

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const body = await req.json().catch(() => null) as Record<string, unknown> | null;
  if (!body) {
    return NextResponse.json({ error: "Cuerpo inválido" }, { status: 400 });
  }

  const existing = await prisma.bookingSlot.findUnique({ where: { id } });
  if (!existing) {
    return NextResponse.json({ error: "No encontrada" }, { status: 404 });
  }

  const data: {
    weekday?: number;
    startMinute?: number;
    endMinute?: number;
    label?: string | null;
    webPercent?: number;
    sortOrder?: number;
    active?: boolean;
  } = {};

  if (body.weekday !== undefined) {
    const w = Number(body.weekday);
    if (!Number.isFinite(w) || w < 1 || w > 7) {
      return NextResponse.json({ error: "weekday 1–7" }, { status: 400 });
    }
    data.weekday = Math.floor(w);
  }
  if (body.startTime !== undefined || body.endTime !== undefined) {
    const nextStart =
      typeof body.startTime === "string"
        ? parseTimeToMinutes(body.startTime)
        : existing.startMinute;
    const nextEnd =
      typeof body.endTime === "string" ? parseTimeToMinutes(body.endTime) : existing.endMinute;
    if (nextStart === null || nextEnd === null || nextStart >= nextEnd) {
      return NextResponse.json({ error: "Horas inválidas (HH:MM, inicio antes que fin)" }, { status: 400 });
    }
    data.startMinute = nextStart;
    data.endMinute = nextEnd;
  }
  if (body.label !== undefined) {
    data.label = typeof body.label === "string" ? body.label.trim() || null : null;
  }
  if (body.webPercent !== undefined) {
    const p = Number(body.webPercent);
    if (!Number.isFinite(p) || p < 1 || p > 100) {
      return NextResponse.json({ error: "webPercent 1–100" }, { status: 400 });
    }
    data.webPercent = Math.floor(p);
  }
  if (body.sortOrder !== undefined) {
    data.sortOrder = Math.floor(Number(body.sortOrder));
  }
  if (body.active !== undefined) {
    data.active = Boolean(body.active);
  }

  if (Object.keys(data).length === 0) {
    return NextResponse.json({ error: "Nada que actualizar" }, { status: 400 });
  }

  const updated = await prisma.bookingSlot.update({ where: { id }, data });
  notifyReservationChange();
  return NextResponse.json(updated);
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  const { id } = await ctx.params;
  await prisma.bookingSlot.delete({ where: { id } });
  notifyReservationChange();
  return NextResponse.json({ ok: true });
}
