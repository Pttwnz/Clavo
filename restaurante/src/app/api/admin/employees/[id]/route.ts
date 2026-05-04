import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const { id } = await ctx.params;
  const body = await req.json().catch(() => null) as {
    active?: boolean;
    role?: string;
    newPin?: string;
  } | null;

  if (!body) {
    return NextResponse.json({ error: "Cuerpo inválido" }, { status: 400 });
  }

  const data: { active?: boolean; role?: string; pinHash?: string } = {};
  if (typeof body.active === "boolean") data.active = body.active;
  if (body.role === "MANAGER" || body.role === "STAFF" || body.role === "KITCHEN") data.role = body.role;
  if (typeof body.newPin === "string" && body.newPin.length >= 4) {
    data.pinHash = await bcrypt.hash(body.newPin, 10);
  }

  if (Object.keys(data).length === 0) {
    return NextResponse.json({ error: "Nada que actualizar" }, { status: 400 });
  }

  const updated = await prisma.employee.update({
    where: { id },
    data,
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      active: true,
    },
  });

  return NextResponse.json(updated);
}
