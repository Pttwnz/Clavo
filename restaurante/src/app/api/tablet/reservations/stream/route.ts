import { reservationEvents } from "@/lib/reservation-events";
import { getTabletEmployeeId } from "@/lib/tablet-session";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const sessionEmployee = await getTabletEmployeeId();
  if (!sessionEmployee) {
    return new Response(JSON.stringify({ error: "Sin sesión tablet" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const active = await prisma.employee.findFirst({ where: { id: sessionEmployee, active: true } });
  if (!active) {
    return new Response(JSON.stringify({ error: "Empleado inactivo" }), {
      status: 403,
      headers: { "Content-Type": "application/json" },
    });
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      const send = (payload: unknown) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
      };

      const onUpdate = () => send({ type: "reservations_updated" });
      reservationEvents.on("update", onUpdate);
      send({ type: "connected" });

      request.signal.addEventListener("abort", () => {
        reservationEvents.off("update", onUpdate);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      /** Evita que nginx (y similares) buffericen el SSE; sin esto el tablet parece “desconectado”. */
      "X-Accel-Buffering": "no",
    },
  });
}
