import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";

export async function requireAdminOrTabletSession(): Promise<
  NextResponse | null
> {
  const session = await auth();
  if (session?.user) return null;

  const tid = await getTabletEmployeeId();
  if (tid) {
    const emp = await prisma.employee.findFirst({ where: { id: tid, active: true } });
    if (emp) return null;
  }

  return NextResponse.json({ error: "No autorizado" }, { status: 401 });
}
