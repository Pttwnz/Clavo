import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { buildDiningOverview } from "@/lib/build-dining-overview";
import { requireAdminOrTabletSession } from "@/lib/auth-dining";

export const dynamic = "force-dynamic";

export async function GET() {
  const denied = await requireAdminOrTabletSession();
  if (denied) return denied;

  const [tables, reservations] = await Promise.all([
    prisma.diningTable.findMany({ orderBy: [{ sortOrder: "asc" }, { label: "asc" }] }),
    prisma.reservation.findMany({
      where: { status: { notIn: ["CANCELLED", "COMPLETED"] } },
      take: 500,
      orderBy: { startsAt: "asc" },
    }),
  ]);

  const overview = buildDiningOverview(tables, reservations, new Date());
  return NextResponse.json(
    { overview, generatedAt: new Date().toISOString() },
    {
      headers: {
        "Cache-Control": "private, no-store, must-revalidate",
      },
    },
  );
}
