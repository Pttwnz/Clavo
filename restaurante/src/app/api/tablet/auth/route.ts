import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/db";
import { signTabletToken, TABLET_COOKIE, tabletCookieOptions } from "@/lib/tablet-session";

export const dynamic = "force-dynamic";

type Body = { employeeId?: string; pin?: string };

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as Body | null;
  if (!body?.employeeId || typeof body.pin !== "string" || body.pin.length < 4) {
    return NextResponse.json({ error: "Empleado y PIN obligatorios" }, { status: 400 });
  }

  const employee = await prisma.employee.findFirst({
    where: { id: body.employeeId, active: true },
  });
  if (!employee) {
    return NextResponse.json({ error: "Empleado no encontrado" }, { status: 404 });
  }

  const ok = await bcrypt.compare(body.pin, employee.pinHash);
  if (!ok) {
    return NextResponse.json({ error: "PIN incorrecto" }, { status: 401 });
  }

  const token = signTabletToken(employee.id);
  const res = NextResponse.json({
    ok: true,
    employee: { id: employee.id, name: employee.name, role: employee.role },
  });
  res.cookies.set(TABLET_COOKIE, token, tabletCookieOptions());
  return res;
}
