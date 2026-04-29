import type { Prisma } from "@/generated/prisma/client";
import { ReservationStatus } from "@/generated/prisma/enums";

const statuses = new Set(Object.values(ReservationStatus));

export function parseReservationPatch(body: unknown):
  | { ok: true; data: Prisma.ReservationUncheckedUpdateInput }
  | { ok: false; error: string } {
  if (!body || typeof body !== "object") {
    return { ok: false, error: "Cuerpo inválido" };
  }
  const b = body as Record<string, unknown>;
  const data: Prisma.ReservationUncheckedUpdateInput = {};

  if (b.status !== undefined) {
    if (typeof b.status !== "string" || !statuses.has(b.status as ReservationStatus)) {
      return { ok: false, error: "Estado no válido" };
    }
    data.status = b.status as ReservationStatus;
  }

  if ("assignedTable" in b) {
    if (b.assignedTable === null) {
      data.assignedTable = null;
    } else if (typeof b.assignedTable === "string") {
      const t = b.assignedTable.trim();
      data.assignedTable = t.length ? t : null;
    } else {
      return { ok: false, error: "Mesa no válida" };
    }
  }

  if ("staffNotes" in b) {
    if (b.staffNotes === null) {
      data.staffNotes = null;
    } else if (typeof b.staffNotes === "string") {
      const t = b.staffNotes.trim();
      data.staffNotes = t.length ? t : null;
    } else {
      return { ok: false, error: "Notas internas no válidas" };
    }
  }

  if ("arrivedAt" in b) {
    if (b.arrivedAt === null) {
      data.arrivedAt = null;
    } else if (typeof b.arrivedAt === "string") {
      const d = new Date(b.arrivedAt);
      if (Number.isNaN(d.getTime())) {
        return { ok: false, error: "Hora de llegada no válida" };
      }
      data.arrivedAt = d;
    } else {
      return { ok: false, error: "Hora de llegada no válida" };
    }
  }

  if ("tableId" in b) {
    if (b.tableId === null) {
      data.tableId = null;
    } else if (typeof b.tableId === "string" && b.tableId.length > 0) {
      data.tableId = b.tableId;
    } else {
      return { ok: false, error: "Mesa no válida" };
    }
  }

  if ("endsAt" in b) {
    if (b.endsAt === null) {
      data.endsAt = null;
    } else if (typeof b.endsAt === "string") {
      const d = new Date(b.endsAt);
      if (Number.isNaN(d.getTime())) {
        return { ok: false, error: "Fin de franja no válido" };
      }
      data.endsAt = d;
    } else {
      return { ok: false, error: "Fin de franja no válido" };
    }
  }

  if (Object.keys(data).length === 0) {
    return { ok: false, error: "Nada que actualizar" };
  }

  return { ok: true, data };
}
