import type { Prisma } from "@/generated/prisma/client";
import { prisma } from "@/lib/db";
import { assertReservationTableNoConflict } from "@/lib/reservation-table-conflict";
import { parseReservationPatch } from "@/lib/reservation-update";

async function diningTableIdForLabel(label: string): Promise<string | null> {
  const trimmed = label.trim();
  if (!trimmed) return null;
  const lower = trimmed.toLowerCase();
  const rows = await prisma.diningTable.findMany({ where: { active: true } });
  const hit = rows.find((t) => t.label.trim().toLowerCase() === lower);
  return hit?.id ?? null;
}

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

  const touchedSlot =
    patch.tableId !== undefined ||
    patch.endsAt !== undefined ||
    patch.assignedTable !== undefined;

  if (touchedSlot) {
    let effectiveTableId: string | null = existing.tableId;
    if (patch.tableId !== undefined) {
      effectiveTableId = patch.tableId as string | null;
    } else if (patch.assignedTable !== undefined) {
      const raw = patch.assignedTable;
      if (raw === null || (typeof raw === "string" && !raw.trim())) {
        effectiveTableId = null;
      } else if (typeof raw === "string") {
        effectiveTableId = await diningTableIdForLabel(raw);
      }
    }

    const effectiveEndsAt =
      patch.endsAt !== undefined ? (patch.endsAt as Date | null) : existing.endsAt;
    if (
      effectiveEndsAt !== null &&
      !Number.isNaN(effectiveEndsAt.getTime()) &&
      effectiveEndsAt.getTime() < existing.startsAt.getTime()
    ) {
      return { ok: false, status: 400, error: "La hora de fin debe ser posterior al inicio de la reserva." };
    }

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
  } else if (patch.assignedTable !== undefined) {
    const raw = patch.assignedTable;
    if (raw === null || (typeof raw === "string" && !raw.trim())) {
      out.tableId = null;
    } else if (typeof raw === "string") {
      out.tableId = await diningTableIdForLabel(raw);
    }
  }

  return { ok: true, data: out };
}
