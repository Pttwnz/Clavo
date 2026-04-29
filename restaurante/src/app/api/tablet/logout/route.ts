import { NextResponse } from "next/server";
import { TABLET_COOKIE } from "@/lib/tablet-session";

export const dynamic = "force-dynamic";

export async function POST() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(TABLET_COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}
