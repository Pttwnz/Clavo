import type { Prisma } from "@/generated/prisma/client";
import { prisma } from "@/lib/db";
import { assertReservationTableNoConflict } from "@/lib/reservation-table-conflict";
import { parseReservationPatch } from "@/lib/reservation-update";

export async function prepareReservationPatch(
  id: string,
  body: unknown,
): Promise<
  | { ok: true; data: Prisma.ReservationUncheckedUpdateInput }
  | { ok: false; status: number; error: string }
> {
  const existing = await prisma.reservation.findUnique({ where: { id } });
  if (!existing) {
    return { ok: false, status: 404, error: "Reserva no encontrada" };
  }

  const parsed = parseReservationPatch(body);
  if (!parsed.ok) {
    return { ok: false, status: 400, error: parsed.error };
  }

  const patch = parsed.data;

  const touchedSlot = patch.tableId !== undefined || patch.endsAt !== undefined;

  if (touchedSlot) {
    const effectiveTableId =
      patch.tableId !== undefined ? (patch.tableId as string | null) : existing.tableId;
    const effectiveEndsAt =
      patch.endsAt !== undefined ? (patch.endsAt as Date | null) : existing.endsAt;

    const conflict = await assertReservationTableNoConflict(prisma, {
      excludeReservationId: id,
      tableId: effectiveTableId,
      startsAt: existing.startsAt,
      endsAt: effectiveEndsAt,
    });
    if (!conflict.ok) {
      return { ok: false, status: 409, error: conflict.message };
    }
  }

  const out: Prisma.ReservationUncheckedUpdateInput = { ...patch };

  if (patch.tableId !== undefined) {
    if (patch.tableId === null) {
      out.assignedTable = null;
    } else {
      const t = await prisma.diningTable.findFirst({
        where: { id: patch.tableId as string, active: true },
      });
      if (!t) {
        return { ok: false, status: 400, error: "Mesa no válida o inactiva" };
      }
      out.assignedTable = t.label;
    }
  }

  return { ok: true, data: out };
}
