import { NextResponse } from "next/server";
import { getMenuItemsResolved } from "@/lib/menu-items-resolved";
import { getStoppedKitchenItemIds, setStoppedKitchenItemIds } from "@/lib/kitchen-stops-db";
import { requireTabletKitchenManager } from "@/lib/tablet-kitchen-access";

export const dynamic = "force-dynamic";

/** Lista de platos (metadatos) + ids parados. Solo sesión tablet cocina/encargado. */
export async function GET() {
  const gate = await requireTabletKitchenManager();
  if (!gate.ok) return gate.response;

  const items = await getMenuItemsResolved();
  const stopped = await getStoppedKitchenItemIds();
  const minimal = items.map((m) => ({
    id: m.id,
    nameEs: m.name.es,
    categoryEs: m.category.es,
    hiddenFromPublic: Boolean(m.hiddenFromPublic),
  }));

  return NextResponse.json({
    items: minimal,
    stoppedItemIds: [...stopped],
  });
}

/** Sustituye el conjunto de paros (ids de `MenuItem`). */
export async function PUT(req: Request) {
  const gate = await requireTabletKitchenManager();
  if (!gate.ok) return gate.response;

  const body = (await req.json().catch(() => null)) as { stoppedItemIds?: unknown } | null;
  const raw = body?.stoppedItemIds;
  if (!Array.isArray(raw)) {
    return NextResponse.json({ error: "stoppedItemIds debe ser un array de strings" }, { status: 400 });
  }
  const ids = raw.filter((x): x is string => typeof x === "string" && x.trim().length > 0);

  const menu = await getMenuItemsResolved();
  const valid = new Set(menu.map((m) => m.id));
  const invalid = ids.filter((id) => !valid.has(id));
  if (invalid.length > 0) {
    return NextResponse.json(
      { error: `IDs no reconocidos en la carta: ${invalid.slice(0, 8).join(", ")}` },
      { status: 400 },
    );
  }

  await setStoppedKitchenItemIds(ids);
  return NextResponse.json({ ok: true, stoppedItemIds: ids });
}
