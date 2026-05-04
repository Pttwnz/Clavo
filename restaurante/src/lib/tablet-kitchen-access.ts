import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";

/** Puede marcar paros de cocina (misma cookie tablet que recepción). */
export function roleCanManageKitchenStops(role: string): boolean {
  return role === "KITCHEN" || role === "MANAGER";
}

export async function requireTabletKitchenManager(): Promise<
  | { ok: true; employee: { id: string; name: string; role: string } }
  | { ok: false; response: NextResponse }
> {
  const id = await getTabletEmployeeId();
  if (!id) {
    return { ok: false, response: NextResponse.json({ error: "Sin sesión tablet" }, { status: 401 }) };
  }
  const employee = await prisma.employee.findFirst({
    where: { id, active: true },
    select: { id: true, name: true, role: true },
  });
  if (!employee) {
    return { ok: false, response: NextResponse.json({ error: "Empleado no encontrado" }, { status: 403 }) };
  }
  if (!roleCanManageKitchenStops(employee.role)) {
    return {
      ok: false,
      response: NextResponse.json(
        { error: "Solo cocina o encargado pueden gestionar paros." },
        { status: 403 },
      ),
    };
  }
  return { ok: true, employee };
}
