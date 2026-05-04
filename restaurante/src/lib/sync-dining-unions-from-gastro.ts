import type { PrismaClient } from "@/generated/prisma/client";
import { gastroReservasBaseUrl } from "@/lib/gastro-reservas-proxy";

type GastroUnion = {
  id?: number;
  nombre?: string;
  capacidad_total?: number;
  mesa_nombres?: string[];
};

type SyncResult =
  | {
      ok: true;
      synced: number;
      skipped: number;
      deactivated: number;
      warnings: string[];
    }
  | { ok: false; error: string };

export async function syncDiningUnionsFromGastro(prisma: PrismaClient): Promise<SyncResult> {
  const base = gastroReservasBaseUrl();
  if (!base) {
    return { ok: false, error: "GASTRO_RESERVAS_BASE_URL no configurada" };
  }
  const secret = (process.env.CLAVO_INTERNAL_API_SECRET || "").trim();
  if (!secret) {
    return { ok: false, error: "CLAVO_INTERNAL_API_SECRET no configurada" };
  }

  const url = `${base.replace(/\/$/, "")}/api/internal/clavo/dining-table-unions`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "X-Clavo-Internal": secret },
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: `No se pudo conectar con Gastro: ${msg}` };
  }

  if (!res.ok) {
    const t = await res.text();
    return { ok: false, error: `Gastro respondió ${res.status}: ${t.slice(0, 400)}` };
  }

  let data: { uniones?: GastroUnion[] };
  try {
    data = (await res.json()) as { uniones?: GastroUnion[] };
  } catch {
    return { ok: false, error: "Respuesta JSON inválida desde Gastro" };
  }

  const uniones = Array.isArray(data.uniones) ? data.uniones : [];
  const warnings: string[] = [];
  let synced = 0;
  let skipped = 0;

  const allTables = await prisma.diningTable.findMany();
  const physical = allTables.filter((t) => !t.unionMemberIds?.trim());
  const physicalLabelToId = new Map(physical.map((t) => [t.label.trim().toLowerCase(), t.id]));

  const syncedNamesLower = new Set<string>();

  for (const u of uniones) {
    const nombre = (u.nombre || "").trim();
    if (!nombre) {
      skipped += 1;
      continue;
    }
    const names = (u.mesa_nombres || []).map((n) => n.trim()).filter(Boolean);
    if (names.length < 2) {
      warnings.push(`Unión «${nombre}»: hace falta al menos 2 mesas en Gastro.`);
      skipped += 1;
      continue;
    }

    const memberIds: string[] = [];
    let missing: string | null = null;
    for (const n of names) {
      const id = physicalLabelToId.get(n.toLowerCase());
      if (!id) {
        missing = n;
        break;
      }
      memberIds.push(id);
    }
    if (missing) {
      warnings.push(
        `Unión «${nombre}»: en Clavo no hay mesa física con etiqueta «${missing}» (revisa nombres o sincroniza mesas).`,
      );
      skipped += 1;
      continue;
    }

    const capRaw = u.capacidad_total;
    const cap =
      typeof capRaw === "number" && Number.isFinite(capRaw) && capRaw >= 1
        ? Math.floor(capRaw)
        : memberIds.length * 4;

    const labelKey = nombre.toLowerCase();
    syncedNamesLower.add(labelKey);

    const existing = allTables.find(
      (t) => t.unionMemberIds?.trim() && t.label.trim().toLowerCase() === labelKey,
    );
    const jsonMembers = JSON.stringify(memberIds);

    if (existing) {
      await prisma.diningTable.update({
        where: { id: existing.id },
        data: {
          capacity: cap,
          unionMemberIds: jsonMembers,
          active: true,
        },
      });
    } else {
      const maxSort = allTables.length ? Math.max(...allTables.map((t) => t.sortOrder)) : 0;
      const created = await prisma.diningTable.create({
        data: {
          label: nombre,
          capacity: cap,
          sortOrder: maxSort + 1,
          active: true,
          unionMemberIds: jsonMembers,
        },
      });
      allTables.push(created);
    }
    synced += 1;
  }

  const unionRows = allTables.filter((t) => t.unionMemberIds?.trim());
  let deactivated = 0;
  for (const row of unionRows) {
    if (syncedNamesLower.has(row.label.trim().toLowerCase())) continue;
    await prisma.diningTable.update({
      where: { id: row.id },
      data: { active: false },
    });
    deactivated += 1;
  }

  return { ok: true, synced, skipped, deactivated, warnings };
}
