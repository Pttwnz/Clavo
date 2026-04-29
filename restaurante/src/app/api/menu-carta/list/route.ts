import { NextResponse } from "next/server";
import { resolveAllMenuCartaImages } from "@/lib/menu-carta-images.server";

export const runtime = "nodejs";

export async function GET() {
  const byLang = resolveAllMenuCartaImages();
  return NextResponse.json({ byLang }, { headers: { "Cache-Control": "no-store" } });
}
