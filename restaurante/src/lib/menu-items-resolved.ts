import { menuItems as defaultMenuItems } from "@/lib/menu-carta";
import { getStoppedKitchenItemIds } from "@/lib/kitchen-stops-db";
import { prisma } from "@/lib/db";
import { parseMenuItemsJson } from "@/lib/menu-items-validate";
import type { MenuItem } from "@/lib/menu-types";

const SINGLETON_ID = "singleton";

export async function getMenuItemsResolved(): Promise<MenuItem[]> {
  try {
    const row = await prisma.menuCartaStore.findUnique({
      where: { id: SINGLETON_ID },
    });
    const raw = row?.itemsJson?.trim();
    if (!raw) return defaultMenuItems;
    const parsed = parseMenuItemsJson(raw);
    return parsed?.length ? parsed : defaultMenuItems;
  } catch (err) {
    console.error("[clavo] getMenuItemsResolved: BD no disponible o sin migrar; carta por defecto.", err);
    return defaultMenuItems;
  }
}

/** Carta tal como la ve el cliente (sin ocultos del panel ni paros de cocina). */
export async function getMenuItemsForPublicDisplay(): Promise<MenuItem[]> {
  const items = await getMenuItemsResolved();
  const stopped = await getStoppedKitchenItemIds();
  return items.filter((m) => !m.hiddenFromPublic && !stopped.has(m.id));
}

export async function isMenuCartaPersisted(): Promise<boolean> {
  try {
    const row = await prisma.menuCartaStore.findUnique({
      where: { id: SINGLETON_ID },
    });
    const raw = row?.itemsJson?.trim();
    if (!raw) return false;
    const parsed = parseMenuItemsJson(raw);
    return Boolean(parsed?.length);
  } catch {
    return false;
  }
}

export async function saveMenuItemsToDb(items: MenuItem[]): Promise<void> {
  const json = JSON.stringify(items);
  await prisma.menuCartaStore.upsert({
    where: { id: SINGLETON_ID },
    create: { id: SINGLETON_ID, itemsJson: json },
    update: { itemsJson: json },
  });
}

export async function clearMenuCartaDb(): Promise<void> {
  await prisma.menuCartaStore.deleteMany({
    where: { id: SINGLETON_ID },
  });
}

export function getDefaultMenuItems(): MenuItem[] {
  return defaultMenuItems;
}
