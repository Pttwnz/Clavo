import type { PrismaClient } from "@/generated/prisma/client";
import { assertReservationTableNoConflict } from "@/lib/reservation-table-conflict";

export type TableSuggestion = {
  tableId: string;
  label: string;
  zone: string | null;
  capacity: number;
  score: number;
  waste: number;
  reason: string;
};

/**
 * Ordena mesas válidas para una franja horaria maximizando encaje de capacidad (sin solapes).
 * No une mesas: si partySize supera la mayor mesa, devuelve lista vacía.
 */
export async function rankTableSuggestions(
  prisma: PrismaClient,
  args: {
    partySize: number;
    startsAt: Date;
    endsAt: Date | null;
    excludeReservationId: string;
  },
): Promise<TableSuggestion[]> {
  const { partySize, startsAt, endsAt, excludeReservationId } = args;
  if (!Number.isFinite(partySize) || partySize < 1) return [];

  const tables = await prisma.diningTable.findMany({
    where: { active: true },
    orderBy: [{ sortOrder: "asc" }, { label: "asc" }],
  });

  const out: TableSuggestion[] = [];
  for (const t of tables) {
    if (t.capacity < partySize) continue;
    const conflict = await assertReservationTableNoConflict(prisma, {
      excludeReservationId,
      tableId: t.id,
      startsAt,
      endsAt,
    });
    if (!conflict.ok) continue;

    const waste = t.capacity - partySize;
    const tightBonus = waste === 0 ? 80 : waste <= 2 ? 40 : 0;
    const score = 1000 - waste * 12 + tightBonus;
    const reason =
      waste === 0
        ? "Encaje exacto de capacidad"
        : waste <= 2
          ? "Buen encaje"
          : `Holgura ${waste} plazas`;

    out.push({
      tableId: t.id,
      label: t.label,
      zone: t.zone,
      capacity: t.capacity,
      score,
      waste,
      reason,
    });
  }

  out.sort((a, b) => b.score - a.score);
  return out;
}
