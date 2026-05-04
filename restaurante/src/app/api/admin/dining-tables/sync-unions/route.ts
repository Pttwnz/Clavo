import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { syncDiningUnionsFromGastro } from "@/lib/sync-dining-unions-from-gastro";
import { notifyReservationChange } from "@/lib/reservation-events";

export const dynamic = "force-dynamic";

/**
 * Sincroniza uniones definidas en el editor de salón (Gastro) hacia filas `DiningTable` con
 * `unionMemberIds` en Clavo, para sugerencias de mesa y conflictos por mesa física.
 */
export async function POST() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const result = await syncDiningUnionsFromGastro(prisma);
  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: 400 });
  }

  notifyReservationChange();
  return NextResponse.json({
    ok: true,
    synced: result.synced,
    skipped: result.skipped,
    deactivated: result.deactivated,
    warnings: result.warnings,
  });
}
