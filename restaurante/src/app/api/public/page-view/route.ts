import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

const MAX_PATH = 1024;
const MAX_REF = 500;

function normalizePath(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const p = raw.trim().slice(0, MAX_PATH);
  if (!p.startsWith("/")) return null;
  if (p.startsWith("/admin")) return null;
  if (p.startsWith("/ingreso")) return null;
  if (p.startsWith("/api")) return null;
  if (p.startsWith("/_next")) return null;
  return p;
}

/** Registra una vista de página (llamado desde la web pública). Sin autenticación. */
export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { path?: unknown } | null;
  const path = normalizePath(body?.path);
  if (!path) {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
  const refHeader = req.headers.get("referer") ?? req.headers.get("referrer");
  const referrer =
    refHeader && refHeader.length > 0 ? refHeader.trim().slice(0, MAX_REF) : null;

  try {
    await prisma.pageView.create({
      data: { path, referrer },
    });
  } catch (err) {
    // No bloquear la navegación si la BD no está migrada o hay bloqueo SQLite
    console.error("[clavo] page-view:", err);
    return NextResponse.json({ ok: false }, { status: 200 });
  }
  return NextResponse.json({ ok: true }, { status: 201 });
}
