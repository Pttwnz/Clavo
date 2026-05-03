import { NextResponse } from "next/server";
import { Prisma } from "@/generated/prisma/client";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { gastroReservasBaseUrl } from "@/lib/gastro-reservas-proxy";
import { notifyReservationChange } from "@/lib/reservation-events";
import { ReservationSource } from "@/generated/prisma/enums";
import { evaluateWebBookingQuota } from "@/lib/web-booking-quota";
import {
  detectNearDuplicateReservation,
  normalizePhone,
  validatePartySizeWithinHouseCapacity,
  validateWebLeadTime,
  validateStartsAtNotPast,
} from "@/lib/reservation-create-guards";
import {
  clientIpFromRequest,
  turnstileConfigured,
  verifyTurnstileToken,
} from "@/lib/turnstile-verify";

export const dynamic = "force-dynamic";

function stripTurnstileToken(data: Record<string, unknown>): void {
  delete data.turnstileToken;
}

async function assertTurnstileOk(
  req: Request,
  data: Record<string, unknown>,
): Promise<NextResponse | null> {
  if (!turnstileConfigured()) {
    return null;
  }
  const token = typeof data.turnstileToken === "string" ? data.turnstileToken.trim() : "";
  if (!token) {
    return NextResponse.json(
      { error: "Completa la verificación anti-spam antes de enviar la reserva." },
      { status: 400 },
    );
  }
  const secret = (process.env.TURNSTILE_SECRET_KEY || "").trim();
  const ok = await verifyTurnstileToken(secret, token, clientIpFromRequest(req));
  if (!ok) {
    return NextResponse.json(
      {
        error:
          "La verificación anti-spam ha fallado o ha caducado. Recarga la página, vuelve a marcar el captcha e inténtalo de nuevo.",
      },
      { status: 400 },
    );
  }
  return null;
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const list = await prisma.reservation.findMany({
    orderBy: { startsAt: "asc" },
    take: 200,
    include: { diningTable: true },
  });
  return NextResponse.json(list);
}

export async function POST(req: Request) {
  try {
    const base = gastroReservasBaseUrl();
    if (base) {
      const bodyText = await req.text();
      let bodyData: Record<string, unknown>;
      try {
        bodyData = JSON.parse(bodyText) as Record<string, unknown>;
      } catch {
        return NextResponse.json({ error: "Solicitud no válida." }, { status: 400 });
      }
      const tsErr = await assertTurnstileOk(req, bodyData);
      if (tsErr) {
        return tsErr;
      }
      stripTurnstileToken(bodyData);
      const forwarded = JSON.stringify(bodyData);
      let r: Response;
      try {
        r = await fetch(`${base}/api/web/reservas`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: forwarded,
          cache: "no-store",
          signal: AbortSignal.timeout(30_000),
        });
      } catch {
        return NextResponse.json(
          {
            error:
              "No se pudo conectar con Gastro. Arranca la app Flask (gastro-app, puerto 5050) y comprueba GASTRO_RESERVAS_BASE_URL.",
          },
          { status: 503 },
        );
      }
      const text = await r.text();
      return new NextResponse(text, {
        status: r.status,
        headers: { "Content-Type": r.headers.get("content-type") || "application/json" },
      });
    }

    const bodyRaw = await req.json().catch(() => null);
    if (!bodyRaw || typeof bodyRaw !== "object" || Array.isArray(bodyRaw)) {
      return NextResponse.json({ error: "Datos inválidos" }, { status: 400 });
    }
    const body = bodyRaw as Record<string, unknown>;
    const tsErr = await assertTurnstileOk(req, body);
    if (tsErr) {
      return tsErr;
    }
    stripTurnstileToken(body);
    if (typeof body.customerName !== "string" || typeof body.phone !== "string") {
      return NextResponse.json({ error: "Datos inválidos" }, { status: 400 });
    }
    const phone = normalizePhone(body.phone.trim());
    if (phone.length < 7) {
      return NextResponse.json({ error: "Teléfono no válido" }, { status: 400 });
    }
    const partySize = Number(body.partySize);
    const startsRaw = body.startsAt;
    const startsAt =
      typeof startsRaw === "string" || typeof startsRaw === "number" ? new Date(startsRaw) : new Date(NaN);
    if (!Number.isFinite(partySize) || partySize < 1 || Number.isNaN(startsAt.getTime())) {
      return NextResponse.json({ error: "Fecha o comensales inválidos" }, { status: 400 });
    }

    const timeCheck = validateStartsAtNotPast(startsAt, 0);
    if (!timeCheck.ok) {
      return NextResponse.json({ error: timeCheck.message }, { status: 400 });
    }
    const lead = validateWebLeadTime(startsAt, 30);
    if (!lead.ok) {
      return NextResponse.json({ error: lead.message }, { status: 400 });
    }

    const house = await validatePartySizeWithinHouseCapacity(prisma, partySize);
    if (!house.ok) {
      return NextResponse.json({ error: house.message }, { status: 400 });
    }

    const quota = await evaluateWebBookingQuota(prisma, startsAt, partySize);
    if (!quota.ok) {
      return NextResponse.json({ error: quota.message }, { status: 409 });
    }

    const dup = await detectNearDuplicateReservation(prisma, {
      customerName: body.customerName,
      phone: body.phone,
      startsAt,
    });
    if (!dup.ok) {
      return NextResponse.json({ error: dup.message }, { status: 409 });
    }

    const emailRaw = typeof body.customerEmail === "string" ? body.customerEmail.trim() : "";
    const created = await prisma.reservation.create({
      data: {
        customerName: body.customerName.trim(),
        customerEmail: emailRaw.length ? emailRaw : null,
        phone,
        partySize,
        startsAt,
        notes: typeof body.notes === "string" ? body.notes.trim() || null : null,
        source: ReservationSource.WEB,
      },
    });
    notifyReservationChange();
    return NextResponse.json(created);
  } catch (e) {
    console.error("[POST /api/reservations]", e);
    if (e instanceof Prisma.PrismaClientKnownRequestError) {
      return NextResponse.json(
        {
          error:
            "Error de base de datos. Asegúrate de haber ejecutado `npx prisma db push` (y `npx prisma generate`) con el último schema.",
        },
        { status: 500 },
      );
    }
    const dev = process.env.NODE_ENV === "development";
    const msg =
      e instanceof Error
        ? dev
          ? e.message
          : "No se pudo guardar la reserva. Revisa el servidor o la base de datos."
        : "Error inesperado al guardar.";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
