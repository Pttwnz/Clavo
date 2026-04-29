import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";
import { notifyReservationChange } from "@/lib/reservation-events";
import { assertReservationTableNoConflict } from "@/lib/reservation-table-conflict";
import { ReservationSource, ReservationStatus } from "@/generated/prisma/enums";
import {
  detectNearDuplicateReservation,
  normalizePhone,
  validatePartySizeWithinHouseCapacity,
  validateStartsAtNotPast,
} from "@/lib/reservation-create-guards";

export const dynamic = "force-dynamic";

async function requireTabletEmployee() {
  const id = await getTabletEmployeeId();
  if (!id) {
    return { ok: false as const, response: NextResponse.json({ error: "Sin sesión tablet" }, { status: 401 }) };
  }
  const active = await prisma.employee.findFirst({ where: { id, active: true } });
  if (!active) {
    return { ok: false as const, response: NextResponse.json({ error: "Empleado inactivo" }, { status: 403 }) };
  }
  return { ok: true as const, employee: active };
}

export async function GET() {
  const gate = await requireTabletEmployee();
  if (!gate.ok) return gate.response;

  const list = await prisma.reservation.findMany({
    orderBy: { startsAt: "asc" },
    take: 200,
    include: { diningTable: true },
  });
  return NextResponse.json(list);
}

/** Alta de reserva desde recepción (llamada o cliente en el local). Requiere sesión tablet. */
export async function POST(req: Request) {
  const gate = await requireTabletEmployee();
  if (!gate.ok) return gate.response;

  const body = await req.json().catch(() => null) as {
    customerName?: string;
    phone?: string;
    customerEmail?: string | null;
    partySize?: number;
    startsAt?: string;
    endsAt?: string | null;
    notes?: string | null;
    staffNotes?: string | null;
    tableId?: string | null;
    status?: string;
    /** PHONE = llamada; WALKIN = persona en el local */
    tabletSource?: string;
  } | null;

  if (!body || typeof body.customerName !== "string" || !body.customerName.trim()) {
    return NextResponse.json({ error: "Nombre obligatorio" }, { status: 400 });
  }
  if (typeof body.phone !== "string" || !body.phone.trim()) {
    return NextResponse.json({ error: "Teléfono obligatorio" }, { status: 400 });
  }
  const phone = normalizePhone(body.phone.trim());
  if (phone.length < 7) {
    return NextResponse.json({ error: "Teléfono no válido" }, { status: 400 });
  }

  const partySize = Number(body.partySize);
  const startsAt = new Date(body.startsAt ?? "");
  if (!Number.isFinite(partySize) || partySize < 1 || Number.isNaN(startsAt.getTime())) {
    return NextResponse.json({ error: "Fecha u ocupación no válidos" }, { status: 400 });
  }
  const timeCheck = validateStartsAtNotPast(startsAt, 20);
  if (!timeCheck.ok) {
    return NextResponse.json({ error: timeCheck.message }, { status: 400 });
  }
  const house = await validatePartySizeWithinHouseCapacity(prisma, partySize);
  if (!house.ok) {
    return NextResponse.json({ error: house.message }, { status: 400 });
  }

  let endsAt: Date | null = null;
  if (body.endsAt != null && String(body.endsAt).trim() !== "") {
    const e = new Date(body.endsAt as string);
    if (Number.isNaN(e.getTime())) {
      return NextResponse.json({ error: "Fin de franja no válido" }, { status: 400 });
    }
    endsAt = e;
  }

  const tableId: string | null =
    typeof body.tableId === "string" && body.tableId.length > 0 ? body.tableId : null;
  let assignedTable: string | null = null;
  if (tableId) {
    const t = await prisma.diningTable.findFirst({ where: { id: tableId, active: true } });
    if (!t) {
      return NextResponse.json({ error: "Mesa no válida" }, { status: 400 });
    }
    if (partySize > t.capacity) {
      return NextResponse.json(
        { error: `La mesa ${t.label} admite ${t.capacity} pax máximo.` },
        { status: 400 },
      );
    }
    assignedTable = t.label;
  }

  const conflict = await assertReservationTableNoConflict(prisma, {
    excludeReservationId: "__tablet_new__",
    tableId,
    startsAt,
    endsAt,
  });
  if (!conflict.ok) {
    return NextResponse.json({ error: conflict.message }, { status: 409 });
  }

  const status: ReservationStatus = body.status === "PENDING" ? "PENDING" : "CONFIRMED";
  const dup = await detectNearDuplicateReservation(prisma, {
    customerName: body.customerName,
    phone,
    startsAt,
  });
  if (!dup.ok) {
    return NextResponse.json({ error: dup.message }, { status: 409 });
  }

  const reservationSource: ReservationSource =
    body.tabletSource === "WALKIN"
      ? ReservationSource.TABLET_WALKIN
      : ReservationSource.TABLET_PHONE;

  const emailRaw = typeof body.customerEmail === "string" ? body.customerEmail.trim() : "";
  const notesClient = typeof body.notes === "string" ? body.notes.trim() || null : null;
  const staffExtra = typeof body.staffNotes === "string" ? body.staffNotes.trim() : "";
  const staffLine = `Registro tablet · ${gate.employee.name}`;
  const staffNotes = [staffExtra, staffLine].filter(Boolean).join(" · ");

  const created = await prisma.reservation.create({
    data: {
      customerName: body.customerName.trim(),
      customerEmail: emailRaw.length ? emailRaw : null,
      phone,
      partySize: Math.floor(partySize),
      startsAt,
      endsAt,
      notes: notesClient,
      staffNotes,
      tableId,
      assignedTable,
      status,
      source: reservationSource,
    },
    include: { diningTable: true },
  });

  notifyReservationChange();
  return NextResponse.json(created);
}
