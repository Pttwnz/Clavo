import type { PrismaClient } from "@/generated/prisma/client";
import { ReservationStatus } from "@/generated/prisma/enums";
import { reservationSlotEnd, rangesOverlap } from "@/lib/reservation-slot";

const inactive: ReservationStatus[] = ["CANCELLED", "COMPLETED"];

export async function assertReservationTableNoConflict(
  prisma: PrismaClient,
  args: {
    excludeReservationId: string;
    tableId: string | null;
    startsAt: Date;
    endsAt: Date | null;
  },
): Promise<{ ok: true } | { ok: false; message: string }> {
  if (!args.tableId) return { ok: true };

  const table = await prisma.diningTable.findFirst({
    where: { id: args.tableId, active: true },
  });
  if (!table) return { ok: false, message: "Mesa no encontrada o inactiva" };

  const myStart = args.startsAt;
  const myEnd = reservationSlotEnd(args.startsAt, args.endsAt);

  const others = await prisma.reservation.findMany({
    where: {
      id: { not: args.excludeReservationId },
      status: { notIn: inactive },
      OR: [{ tableId: args.tableId }, { AND: [{ tableId: null }, { assignedTable: table.label }] }],
    },
    select: { id: true, startsAt: true, endsAt: true },
  });

  for (const o of others) {
    const oEnd = reservationSlotEnd(o.startsAt, o.endsAt);
    if (rangesOverlap(myStart, myEnd, o.startsAt, oEnd)) {
      return {
        ok: false,
        message: "Esa mesa ya tiene otra reserva activa en esa franja horaria.",
      };
    }
  }

  return { ok: true };
}
