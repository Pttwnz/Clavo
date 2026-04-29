import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const list = await prisma.employee.findMany({
    orderBy: { name: "asc" },
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      active: true,
      createdAt: true,
    },
  });
  return NextResponse.json(list);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const body = await req.json().catch(() => null) as {
    name?: string;
    email?: string | null;
    role?: string;
    pin?: string;
  } | null;

  if (!body?.name?.trim() || typeof body.pin !== "string" || body.pin.length < 4) {
    return NextResponse.json({ error: "Nombre y PIN (mín. 4 caracteres) obligatorios" }, { status: 400 });
  }

  const role = body.role === "MANAGER" ? "MANAGER" : "STAFF";
  const email = body.email?.trim() || null;
  if (email) {
    const exists = await prisma.employee.findUnique({ where: { email } });
    if (exists) {
      return NextResponse.json({ error: "Ese email ya está en uso" }, { status: 409 });
    }
  }

  const pinHash = await bcrypt.hash(body.pin, 10);
  const created = await prisma.employee.create({
    data: {
      name: body.name.trim(),
      email,
      role,
      pinHash,
    },
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      active: true,
      createdAt: true,
    },
  });

  return NextResponse.json(created);
}
