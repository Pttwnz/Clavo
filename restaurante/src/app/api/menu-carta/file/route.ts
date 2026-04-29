import fs from "node:fs";
import { NextRequest, NextResponse } from "next/server";
import { MENU_CARTA_MAX_PAGE, menuCartaExactFile, menuCartaMime } from "@/lib/menu-carta-fs";
import { locales, type Locale } from "@/lib/menu-types";

export const runtime = "nodejs";

function isLocale(s: string): s is Locale {
  return (locales as readonly string[]).includes(s as Locale);
}

export async function GET(req: NextRequest) {
  const lang = req.nextUrl.searchParams.get("lang") ?? "";
  const pageRaw = req.nextUrl.searchParams.get("page") ?? "";
  const page = Number(pageRaw);

  if (!isLocale(lang) || !Number.isInteger(page) || page < 1 || page > MENU_CARTA_MAX_PAGE) {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }

  const hit = menuCartaExactFile(lang, page);
  if (!hit) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const buf = fs.readFileSync(hit.absPath);
  return new NextResponse(buf, {
    status: 200,
    headers: {
      "Content-Type": menuCartaMime(hit.ext),
      "Cache-Control": "public, max-age=604800, stale-while-revalidate=86400",
    },
  });
}
