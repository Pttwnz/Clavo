import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";

export const dynamic = "force-dynamic";

type Body = {
  employeeId?: string;
  pin?: string;
  action?: "in" | "out";
  note?: string;
};

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as Body | null;
  if (!body?.employeeId || (body.action !== "in" && body.action !== "out")) {
    return NextResponse.json({ error: "Faltan datos" }, { status: 400 });
  }

  const employee = await prisma.employee.findFirst({
    where: { id: body.employeeId, active: true },
  });
  if (!employee) {
    return NextResponse.json({ error: "Empleado no encontrado" }, { status: 404 });
  }

  const tabletId = await getTabletEmployeeId();
  const pinOk =
    tabletId === employee.id ||
    (typeof body.pin === "string" && (await bcrypt.compare(body.pin, employee.pinHash)));
  if (!pinOk) {
    return NextResponse.json({ error: "PIN incorrecto" }, { status: 401 });
  }

  if (body.action === "in") {
    const open = await prisma.timeEntry.findFirst({
      where: { employeeId: employee.id, clockOut: null },
      orderBy: { clockIn: "desc" },
    });
    if (open) {
      return NextResponse.json(
        { error: "Ya hay un fichaje abierto. Ficha la salida primero.", entry: open },
        { status: 409 },
      );
    }
    const entry = await prisma.timeEntry.create({
      data: {
        employeeId: employee.id,
        clockIn: new Date(),
        note: typeof body.note === "string" ? body.note || null : null,
      },
    });
    return NextResponse.json({ ok: true, entry });
  }

  const open = await prisma.timeEntry.findFirst({
    where: { employeeId: employee.id, clockOut: null },
    orderBy: { clockIn: "desc" },
  });
  if (!open) {
    return NextResponse.json({ error: "No hay entrada abierta para cerrar" }, { status: 409 });
  }

  const entry = await prisma.timeEntry.update({
    where: { id: open.id },
    data: { clockOut: new Date() },
  });
  return NextResponse.json({ ok: true, entry });
}
