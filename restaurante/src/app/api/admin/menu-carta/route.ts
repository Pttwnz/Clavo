import { NextResponse } from "next/server";
import { auth } from "@/auth";
import {
  clearMenuCartaDb,
  getDefaultMenuItems,
  getMenuItemsResolved,
  isMenuCartaPersisted,
  saveMenuItemsToDb,
} from "@/lib/menu-items-resolved";
import { parseMenuItemsJson } from "@/lib/menu-items-validate";
import type { Locale, MenuItem } from "@/lib/menu-types";

export const dynamic = "force-dynamic";

function categoryPresetsFromDefaults(): Record<string, Record<Locale, string>> {
  const defaults = getDefaultMenuItems();
  const presets: Record<string, Record<Locale, string>> = {};
  for (const m of defaults) {
    const es = m.category.es;
    if (!presets[es]) presets[es] = { ...m.category };
  }
  return presets;
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  const items = await getMenuItemsResolved();
  const persisted = await isMenuCartaPersisted();
  const categoryPresets = categoryPresetsFromDefaults();
  return NextResponse.json({ items, persisted, categoryPresets });
}

export async function PUT(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  const body = (await req.json().catch(() => null)) as { items?: unknown } | null;
  if (!body || !Array.isArray(body.items)) {
    return NextResponse.json({ error: "Cuerpo inválido: se espera { items: MenuItem[] }" }, { status: 400 });
  }
  const json = JSON.stringify(body.items);
  const parsed = parseMenuItemsJson(json);
  if (!parsed?.length) {
    return NextResponse.json({ error: "Lista vacía o JSON de platos no válido" }, { status: 400 });
  }
  await saveMenuItemsToDb(parsed);
  return NextResponse.json({ ok: true, count: parsed.length });
}

/** Vuelve a la carta embebida en código (borra la copia en base de datos). */
export async function DELETE() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }
  await clearMenuCartaDb();
  const items = getDefaultMenuItems();
  return NextResponse.json({ ok: true, items });
}
