import { NextResponse } from "next/server";
import {
  clearMenuCartaDb,
  getDefaultMenuItems,
  getMenuItemsResolved,
  isMenuCartaPersisted,
  saveMenuItemsToDb,
} from "@/lib/menu-items-resolved";
import { parseMenuItemsJson } from "@/lib/menu-items-validate";
import type { Locale, MenuItem } from "@/lib/menu-types";
import { internalApiUnauthorized, verifyInternalClavoRequest } from "@/lib/internal-api-auth";

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

export async function GET(req: Request) {
  if (!(await verifyInternalClavoRequest(req))) {
    return internalApiUnauthorized();
  }
  const items = await getMenuItemsResolved();
  const persisted = await isMenuCartaPersisted();
  const categoryPresets = categoryPresetsFromDefaults();
  return NextResponse.json({ items, persisted, categoryPresets } satisfies {
    items: MenuItem[];
    persisted: boolean;
    categoryPresets: Record<string, Record<Locale, string>>;
  });
}

export async function PUT(req: Request) {
  if (!(await verifyInternalClavoRequest(req))) {
    return internalApiUnauthorized();
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

export async function DELETE(req: Request) {
  if (!(await verifyInternalClavoRequest(req))) {
    return internalApiUnauthorized();
  }
  await clearMenuCartaDb();
  const items = getDefaultMenuItems();
  return NextResponse.json({ ok: true, items });
}
