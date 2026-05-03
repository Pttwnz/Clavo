import { NextResponse } from "next/server";
import { TABLET_COOKIE, tabletCookieOptions } from "@/lib/tablet-session";

export const dynamic = "force-dynamic";

export async function POST() {
  const res = NextResponse.json({ ok: true });
  const opts = tabletCookieOptions();
  res.cookies.set(TABLET_COOKIE, "", { ...opts, maxAge: 0 });
  return res;
}
