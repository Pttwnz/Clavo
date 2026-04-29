import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { notifyReservationChange } from "@/lib/reservation-events";

export const dynamic = "force-dynamic";

function parsePositiveInt(value: unknown, fallback: number): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n < 1) return fallback;
  return Math.floor(n);
}

function parseSortOrder(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.floor(n);
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const list = await prisma.diningTable.findMany({
    orderBy: [{ sortOrder: "asc" }, { label: "asc" }],
  });
  return NextResponse.json(list);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const body = await req.json().catch(() => null) as {
    label?: string;
    zone?: string | null;
    capacity?: number;
    sortOrder?: number;
  } | null;

  if (!body || typeof body.label !== "string" || !body.label.trim()) {
    return NextResponse.json({ error: "Etiqueta de mesa obligatoria" }, { status: 400 });
  }

  const capacity = parsePositiveInt(body.capacity, 4);
  const sortOrder = parseSortOrder(body.sortOrder);

  try {
    const created = await prisma.diningTable.create({
      data: {
        label: body.label.trim(),
        zone: typeof body.zone === "string" ? body.zone.trim() || null : body.zone ?? null,
        capacity,
        sortOrder,
        active: true,
      },
    });
    notifyReservationChange();
    return NextResponse.json(created);
  } catch (e) {
    console.error("[admin dining-tables POST]", e);
    const msg = e instanceof Error ? e.message : String(e);
    const code = typeof e === "object" && e !== null && "code" in e ? String((e as { code: unknown }).code) : "";
    if (code === "P2021" || msg.includes("does not exist") || msg.includes("no such table")) {
      return NextResponse.json(
        {
          error:
            "La base de datos no tiene la tabla de mesas. En la carpeta del proyecto ejecuta: npx prisma db push",
        },
        { status: 500 },
      );
    }
    return NextResponse.json({ error: msg || "No se pudo crear la mesa" }, { status: 500 });
  }
}
