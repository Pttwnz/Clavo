import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { requireAdminOrTabletSession } from "@/lib/auth-dining";

export const dynamic = "force-dynamic";

export async function GET() {
  const denied = await requireAdminOrTabletSession();
  if (denied) return denied;

  const tables = await prisma.diningTable.findMany({
    where: { active: true },
    orderBy: [{ sortOrder: "asc" }, { label: "asc" }],
    select: { id: true, label: true, zone: true, capacity: true },
  });

  return NextResponse.json({ tables });
}
