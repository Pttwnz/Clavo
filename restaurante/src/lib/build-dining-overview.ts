import type { DiningTable, Reservation } from "@/generated/prisma/client";
import { ReservationStatus } from "@/generated/prisma/enums";
import type { DiningOverviewRow } from "@/lib/dining-overview-types";
import { reservationSlotEnd } from "@/lib/reservation-slot";

export type { DiningOverviewRow, DiningOverviewState } from "@/lib/dining-overview-types";

const inactive: ReservationStatus[] = ["CANCELLED", "COMPLETED"];

function belongsToTable(r: Reservation, dt: DiningTable): boolean {
  if (r.tableId === dt.id) return true;
  if (r.tableId) return false;
  const a = r.assignedTable?.trim();
  return !!a && a === dt.label.trim();
}

export function buildDiningOverview(
  tables: DiningTable[],
  reservations: Reservation[],
  now: Date,
): DiningOverviewRow[] {
  const active = reservations.filter((r) => !inactive.includes(r.status));

  return tables
    .filter((t) => t.active)
    .sort((a, b) => a.sortOrder - b.sortOrder || a.label.localeCompare(b.label))
    .map((dt) => {
      const mine = active.filter((r) => belongsToTable(r, dt));

      if (mine.some((r) => r.status === "SEATED")) {
        const r = mine.find((x) => x.status === "SEATED")!;
        const since = r.arrivedAt ?? r.startsAt;
        return {
          id: dt.id,
          label: dt.label,
          zone: dt.zone,
          capacity: dt.capacity,
          state: "seated",
          detail: r.customerName,
          occupiedSinceIso: since.toISOString(),
        };
      }

      const booked = mine.filter((r) => r.status === "PENDING" || r.status === "CONFIRMED");
      const inSlot = booked.filter((r) => {
        const end = reservationSlotEnd(r.startsAt, r.endsAt);
        return now.getTime() >= r.startsAt.getTime() && now.getTime() < end.getTime();
      });

      if (inSlot.length > 0) {
        const r = inSlot.sort((a, b) => a.startsAt.getTime() - b.startsAt.getTime())[0]!;
        return {
          id: dt.id,
          label: dt.label,
          zone: dt.zone,
          capacity: dt.capacity,
          state: "reserved_now",
          detail: `Reserva en curso · ${fmtClock(r.startsAt)} · ${r.customerName}`,
          occupiedSinceIso: r.startsAt.toISOString(),
        };
      }

      const future = booked.filter((r) => r.startsAt.getTime() > now.getTime());
      if (future.length > 0) {
        const r = future.sort((a, b) => a.startsAt.getTime() - b.startsAt.getTime())[0]!;
        const when = relativeUntilReservationEs(r.startsAt, now);
        const detail = sameLocalDay(r.startsAt, now)
          ? `Próxima reserva ${when} · ${fmtClock(r.startsAt)} · ${r.customerName}`
          : `Próxima reserva ${when} · ${fmtDayClock(r.startsAt)} · ${r.customerName}`;
        return {
          id: dt.id,
          label: dt.label,
          zone: dt.zone,
          capacity: dt.capacity,
          state: "reserved_future",
          detail,
          occupiedSinceIso: null,
        };
      }

      if (dt.walkInOccupied) {
        const p = dt.walkInPartySize;
        return {
          id: dt.id,
          label: dt.label,
          zone: dt.zone,
          capacity: dt.capacity,
          state: "walk_in",
          detail:
            p != null && p >= 1 ? `Ocupación manual · ${p} pax` : "Ocupación manual",
          occupiedSinceIso: dt.walkInStartedAt?.toISOString() ?? null,
        };
      }

      return {
        id: dt.id,
        label: dt.label,
        zone: dt.zone,
        capacity: dt.capacity,
        state: "free",
        detail: null,
        occupiedSinceIso: null,
      };
    });
}

function fmtClock(d: Date) {
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function fmtDayClock(d: Date) {
  return d.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sameLocalDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  );
}

/** Texto tipo "En 40 min" / "En 2 h" para la próxima reserva. */
function relativeUntilReservationEs(startsAt: Date, now: Date): string {
  const ms = startsAt.getTime() - now.getTime();
  const minsTotal = Math.max(0, Math.round(ms / 60000));
  if (minsTotal <= 0) return "Ahora";
  if (minsTotal === 1) return "En 1 min";
  if (minsTotal < 60) return `En ${minsTotal} min`;
  const h = Math.floor(minsTotal / 60);
  const m = minsTotal % 60;
  if (m === 0) return `En ${h} h`;
  return `En ${h} h ${m} min`;
}
