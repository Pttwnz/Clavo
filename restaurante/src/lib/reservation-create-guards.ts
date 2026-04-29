import type { PrismaClient } from "@/generated/prisma/client";
import { ReservationStatus } from "@/generated/prisma/enums";

const inactive: ReservationStatus[] = ["CANCELLED", "COMPLETED"];

export function normalizePhone(raw: string): string {
  return raw.replace(/[^\d+]/g, "");
}

export async function validatePartySizeWithinHouseCapacity(
  prisma: PrismaClient,
  partySize: number,
): Promise<{ ok: true } | { ok: false; message: string }> {
  const agg = await prisma.diningTable.aggregate({
    where: { active: true },
    _sum: { capacity: true },
  });
  const total = agg._sum.capacity ?? 0;
  if (total < 1) return { ok: false, message: "No hay mesas activas configuradas" };
  if (partySize > total) {
    return {
      ok: false,
      message: `La reserva supera el aforo total del local (${total} pax).`,
    };
  }
  return { ok: true };
}

export function validateStartsAtNotPast(
  startsAt: Date,
  maxPastMinutes = 5,
): { ok: true } | { ok: false; message: string } {
  const now = Date.now();
  if (startsAt.getTime() < now - maxPastMinutes * 60 * 1000) {
    return { ok: false, message: "La hora de reserva no puede estar en el pasado." };
  }
  return { ok: true };
}

export function validateWebLeadTime(
  startsAt: Date,
  minLeadMinutes = 30,
): { ok: true } | { ok: false; message: string } {
  const now = Date.now();
  const min = now + minLeadMinutes * 60 * 1000;
  if (startsAt.getTime() < min) {
    return {
      ok: false,
      message: `Para reservar online se requieren al menos ${minLeadMinutes} minutos de antelación.`,
    };
  }
  return { ok: true };
}

export async function detectNearDuplicateReservation(
  prisma: PrismaClient,
  args: {
    customerName: string;
    phone: string;
    startsAt: Date;
    windowMinutes?: number;
  },
): Promise<{ ok: true } | { ok: false; message: string }> {
  const windowMinutes = args.windowMinutes ?? 15;
  const start = new Date(args.startsAt.getTime() - windowMinutes * 60 * 1000);
  const end = new Date(args.startsAt.getTime() + windowMinutes * 60 * 1000);
  const phoneNorm = normalizePhone(args.phone);
  const nameNorm = args.customerName.trim().toLowerCase();

  const candidates = await prisma.reservation.findMany({
    where: {
      status: { notIn: inactive },
      startsAt: { gte: start, lte: end },
    },
    select: { customerName: true, phone: true, startsAt: true },
    take: 50,
  });

  const found = candidates.find((r) => {
    const samePhone = normalizePhone(r.phone) === phoneNorm;
    const sameName = r.customerName.trim().toLowerCase() === nameNorm;
    return samePhone || sameName;
  });

  if (!found) return { ok: true };
  return {
    ok: false,
    message:
      "Parece una reserva duplicada (mismo cliente/teléfono en horario cercano). Revisa antes de crearla.",
  };
}
