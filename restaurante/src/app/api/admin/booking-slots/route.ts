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

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  const slots = await prisma.bookingSlot.findMany({
    orderBy: [{ weekday: "asc" }, { sortOrder: "asc" }, { startMinute: "asc" }],
  });
  return NextResponse.json(slots);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  const body = await req.json().catch(() => null) as {
    weekday?: number;
    startTime?: string;
    endTime?: string;
    label?: string | null;
    webPercent?: number;
    sortOrder?: number;
    active?: boolean;
  } | null;

  if (!body || typeof body.weekday !== "number" || body.weekday < 1 || body.weekday > 7) {
    return NextResponse.json({ error: "Día de la semana 1–7 (Lun–Dom)" }, { status: 400 });
  }
  const startMinute = typeof body.startTime === "string" ? parseTimeToMinutes(body.startTime) : null;
  const endMinute = typeof body.endTime === "string" ? parseTimeToMinutes(body.endTime) : null;
  if (startMinute === null || endMinute === null || startMinute >= endMinute) {
    return NextResponse.json({ error: "Horas HH:MM válidas (inicio antes que fin)" }, { status: 400 });
  }
  const webPercent = Number(body.webPercent);
  if (!Number.isFinite(webPercent) || webPercent < 1 || webPercent > 100) {
    return NextResponse.json({ error: "Porcentaje web entre 1 y 100" }, { status: 400 });
  }

  const created = await prisma.bookingSlot.create({
    data: {
      weekday: body.weekday,
      startMinute,
      endMinute,
      label: typeof body.label === "string" ? body.label.trim() || null : null,
      webPercent: Math.floor(webPercent),
      sortOrder: body.sortOrder !== undefined ? Math.floor(Number(body.sortOrder)) : 0,
      active: body.active !== false,
    },
  });
  notifyReservationChange();
  return NextResponse.json(created);
}
