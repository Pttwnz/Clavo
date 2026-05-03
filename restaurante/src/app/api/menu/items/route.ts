import { NextResponse } from "next/server";
import { getMenuItemsForPublicDisplay } from "@/lib/menu-items-resolved";

export const dynamic = "force-dynamic";

/** Carta pública (lectura). Sin autenticación. */
export async function GET() {
  const items = await getMenuItemsForPublicDisplay();
  return NextResponse.json(items, {
    headers: {
      "Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
    },
  });
}
