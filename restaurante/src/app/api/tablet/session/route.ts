import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";

export const dynamic = "force-dynamic";

export async function GET() {
  const id = await getTabletEmployeeId();
  if (!id) {
    return NextResponse.json({ error: "Sin sesión" }, { status: 401 });
  }
  const employee = await prisma.employee.findFirst({
    where: { id, active: true },
    select: { id: true, name: true, role: true },
  });
  if (!employee) {
    return NextResponse.json({ error: "Sesión inválida" }, { status: 401 });
  }
  return NextResponse.json({ employee });
}
