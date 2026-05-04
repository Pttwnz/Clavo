import type { PrismaClient } from "@/generated/prisma/client";
import { ReservationStatus } from "@/generated/prisma/enums";
import {
  buildDiningTableLookup,
  physicalFootprintForReservation,
  physicalFootprintForTableRow,
  setsIntersect,
} from "@/lib/reservation-table-footprint";
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

  const proposed = physicalFootprintForTableRow(table);
  const myStart = args.startsAt;
  const myEnd = reservationSlotEnd(args.startsAt, args.endsAt);

  const candidates = await prisma.reservation.findMany({
    where: {
      id: { not: args.excludeReservationId },
      status: { notIn: inactive },
    },
    select: {
      id: true,
      tableId: true,
      assignedTable: true,
      startsAt: true,
      endsAt: true,
    },
  });

  const allTables = await prisma.diningTable.findMany();
  const lookup = buildDiningTableLookup(allTables);
  const cache = new Map<string, import("@/generated/prisma/client").DiningTable>();

  for (const o of candidates) {
    const oEnd = reservationSlotEnd(o.startsAt, o.endsAt);
    if (!rangesOverlap(myStart, myEnd, o.startsAt, oEnd)) continue;

    const fpO = await physicalFootprintForReservation(prisma, o, cache, lookup);
    if (setsIntersect(proposed, fpO)) {
      return {
        ok: false,
        message: "Esa mesa o unión choca con otra reserva activa en esa franja horaria.",
      };
    }
  }

  return { ok: true };
}
