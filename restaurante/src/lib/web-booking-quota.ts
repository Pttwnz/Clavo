import type { BookingSlot, PrismaClient } from "@/generated/prisma/client";
import { ReservationSource, ReservationStatus } from "@/generated/prisma/enums";
import { madridCalendar, madridYmdToUtcRange } from "@/lib/madrid-time";

const countStatuses: ReservationStatus[] = ["PENDING", "CONFIRMED", "SEATED"];

export async function findMatchingBookingSlot(
  prisma: PrismaClient,
  isoWeekday: number,
  minuteOfDay: number,
): Promise<BookingSlot | null> {
  const slots = await prisma.bookingSlot.findMany({
    where: { active: true, weekday: isoWeekday },
    orderBy: [{ sortOrder: "asc" }, { startMinute: "asc" }],
  });
  return (
    slots.find((s) => minuteOfDay >= s.startMinute && minuteOfDay <= s.endMinute) ?? null
  );
}

async function sumWebPartyInSlot(
  prisma: PrismaClient,
  ymd: string,
  slot: BookingSlot,
): Promise<number> {
  const { start, end } = madridYmdToUtcRange(ymd);
  const rows = await prisma.reservation.findMany({
    where: {
      source: ReservationSource.WEB,
      status: { in: countStatuses },
      startsAt: { gte: start, lte: end },
    },
    select: { partySize: true, startsAt: true },
  });
  let sum = 0;
  for (const r of rows) {
    const cal = madridCalendar(r.startsAt);
    if (cal.ymd !== ymd) continue;
    if (
      cal.minuteOfDay >= slot.startMinute &&
      cal.minuteOfDay <= slot.endMinute
    ) {
      sum += r.partySize;
    }
  }
  return sum;
}

export type WebQuotaResult =
  | {
      ok: true;
      slot: BookingSlot;
      totalSeats: number;
      quota: number;
      used: number;
      remaining: number;
    }
  | { ok: false; message: string };

async function computeQuotaForSlot(
  prisma: PrismaClient,
  slot: BookingSlot,
  ymd: string,
): Promise<{ totalSeats: number; quota: number; used: number; remaining: number }> {
  const agg = await prisma.diningTable.aggregate({
    where: { active: true },
    _sum: { capacity: true },
  });
  const totalSeats = agg._sum.capacity ?? 0;
  let quota = Math.floor((totalSeats * slot.webPercent) / 100);
  if (totalSeats > 0 && slot.webPercent > 0 && quota < 1) {
    quota = 1;
  }
  quota = Math.min(quota, totalSeats);
  const used = await sumWebPartyInSlot(prisma, ymd, slot);
  const remaining = quota - used;
  return { totalSeats, quota, used, remaining };
}

/** Cupo web en una fecha/hora (sin comprobar un grupo concreto). */
export async function getWebQuotaForInstant(
  prisma: PrismaClient,
  startsAt: Date,
): Promise<
  | { inSlot: true; slot: BookingSlot; totalSeats: number; quota: number; used: number; remaining: number }
  | { inSlot: false; message: string }
> {
  const cal = madridCalendar(startsAt);
  const slot = await findMatchingBookingSlot(prisma, cal.isoWeekday, cal.minuteOfDay);
  if (!slot) {
    return {
      inSlot: false,
      message:
        "Esa hora no está dentro de ninguna franja habilitada para reservas online.",
    };
  }
  const { totalSeats, quota, used, remaining } = await computeQuotaForSlot(prisma, slot, cal.ymd);
  if (totalSeats < 1) {
    return { inSlot: false, message: "No hay mesas configuradas en el sistema." };
  }
  return { inSlot: true, slot, totalSeats, quota, used, remaining };
}

export async function evaluateWebBookingQuota(
  prisma: PrismaClient,
  startsAt: Date,
  partySize: number,
): Promise<WebQuotaResult> {
  const cal = madridCalendar(startsAt);
  const slot = await findMatchingBookingSlot(prisma, cal.isoWeekday, cal.minuteOfDay);
  if (!slot) {
    return {
      ok: false,
      message:
        "Esa hora no está dentro de ninguna franja habilitada para reservas por la web. Elige otra hora o llama al restaurante.",
    };
  }

  const { totalSeats, quota, used, remaining } = await computeQuotaForSlot(prisma, slot, cal.ymd);
  if (totalSeats < 1) {
    return {
      ok: false,
      message:
        "No hay aforo de mesas configurado. Un administrador debe dar de alta mesas en el panel.",
    };
  }

  if (partySize > remaining) {
    return {
      ok: false,
      message: `Para reservas online en esta franja (${slot.label ?? "horario"}) solo quedan ${Math.max(0, remaining)} comensales (cupos web: ${quota}, ocupados: ${used}).`,
    };
  }

  return { ok: true, slot, totalSeats, quota, used, remaining };
}
