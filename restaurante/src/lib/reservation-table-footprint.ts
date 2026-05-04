import type { DiningTable, PrismaClient, Reservation } from "@/generated/prisma/client";

/** IDs de mesas físicas ocupadas por esta fila de catálogo (mesa suelta o miembros de unión). */
export function physicalFootprintForTableRow(t: DiningTable): Set<string> {
  const raw = t.unionMemberIds?.trim();
  if (raw) {
    try {
      const ids = JSON.parse(raw) as unknown;
      if (Array.isArray(ids)) {
        const out = ids.filter((x): x is string => typeof x === "string" && x.length > 0);
        if (out.length > 0) return new Set(out);
      }
    } catch {
      /* fallthrough */
    }
  }
  return new Set([t.id]);
}

export function setsIntersect(a: Set<string>, b: Set<string>): boolean {
  for (const x of a) {
    if (b.has(x)) return true;
  }
  return false;
}

/** Índice por id y por etiqueta (mesas activas) para resolver huellas sin N consultas. */
export type DiningTableLookup = {
  byId: Map<string, DiningTable>;
  byLabelLower: Map<string, DiningTable>;
};

export function buildDiningTableLookup(tables: DiningTable[]): DiningTableLookup {
  const byId = new Map(tables.map((t) => [t.id, t]));
  const byLabelLower = new Map<string, DiningTable>();
  for (const t of tables) {
    if (t.active) {
      byLabelLower.set(t.label.trim().toLowerCase(), t);
    }
  }
  return { byId, byLabelLower };
}

/** Huella física de una reserva (mesas que deben estar libres). */
export async function physicalFootprintForReservation(
  prisma: PrismaClient,
  r: Pick<Reservation, "tableId" | "assignedTable">,
  cache?: Map<string, DiningTable>,
  lookup?: DiningTableLookup,
): Promise<Set<string>> {
  const getTable = async (id: string): Promise<DiningTable | null> => {
    if (lookup?.byId.has(id)) return lookup.byId.get(id)!;
    if (cache?.has(id)) return cache.get(id)!;
    const t = await prisma.diningTable.findFirst({ where: { id } });
    if (t && cache) cache.set(id, t);
    return t;
  };

  if (r.tableId) {
    const t = await getTable(r.tableId);
    if (!t) return new Set();
    return physicalFootprintForTableRow(t);
  }

  const lab = r.assignedTable?.trim();
  if (!lab) return new Set();

  const lower = lab.toLowerCase();
  const fromLookup = lookup?.byLabelLower.get(lower);
  if (fromLookup) return physicalFootprintForTableRow(fromLookup);

  const rows = await prisma.diningTable.findMany({
    where: { active: true },
  });
  const match = rows.find((t) => t.label.trim().toLowerCase() === lower);
  if (!match) return new Set();
  return physicalFootprintForTableRow(match);
}
