import { prisma } from "@/lib/db";

const SINGLETON_ID = "singleton";

function parseIds(raw: string | null | undefined): Set<string> {
  const s = raw?.trim();
  if (!s || s === "[]") return new Set();
  try {
    const v = JSON.parse(s) as unknown;
    if (!Array.isArray(v)) return new Set();
    return new Set(v.filter((x): x is string => typeof x === "string" && x.length > 0));
  } catch {
    return new Set();
  }
}

export async function getStoppedKitchenItemIds(): Promise<Set<string>> {
  try {
    const row = await prisma.kitchenStopsState.findUnique({
      where: { id: SINGLETON_ID },
    });
    return parseIds(row?.stoppedItemIdsJson);
  } catch {
    return new Set();
  }
}

export async function setStoppedKitchenItemIds(ids: string[]): Promise<void> {
  const uniq = [...new Set(ids.filter((x) => typeof x === "string" && x.trim()))];
  const json = JSON.stringify(uniq);
  await prisma.kitchenStopsState.upsert({
    where: { id: SINGLETON_ID },
    create: { id: SINGLETON_ID, stoppedItemIdsJson: json },
    update: { stoppedItemIdsJson: json },
  });
}
