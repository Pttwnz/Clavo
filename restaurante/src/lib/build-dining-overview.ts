import type { DiningTable, Reservation } from "@/generated/prisma/client";
import { ReservationSource, ReservationStatus } from "@/generated/prisma/enums";
import type { DiningOverviewRow } from "@/lib/dining-overview-types";
import { physicalFootprintForTableRow } from "@/lib/reservation-table-footprint";
import { reservationSlotEnd } from "@/lib/reservation-slot";

export type { DiningOverviewRow, DiningOverviewState } from "@/lib/dining-overview-types";

const inactive: ReservationStatus[] = ["CANCELLED", "COMPLETED"];

function overviewSource(src: ReservationSource): DiningOverviewRow["reservationSource"] {
  switch (src) {
    case ReservationSource.WEB:
      return "WEB";
    case ReservationSource.TABLET_PHONE:
      return "TABLET_PHONE";
    case ReservationSource.TABLET_WALKIN:
      return "TABLET_WALKIN";
    default: {
      const _x: never = src;
      return _x;
    }
  }
}

export function buildDiningOverview(
  tables: DiningTable[],
  reservations: Reservation[],
  now: Date,
): DiningOverviewRow[] {
  const active = reservations.filter((r) => !inactive.includes(r.status));
  const tableById = new Map(tables.map((t) => [t.id, t]));
  const labelToId = new Map<string, string>();
  for (const t of tables) {
    labelToId.set(t.label.trim().toLowerCase(), t.id);
  }

  function physicalFpForReservation(r: Reservation): Set<string> {
    if (r.tableId) {
      const t = tableById.get(r.tableId);
      if (!t) return new Set();
      return physicalFootprintForTableRow(t);
    }
    const lab = r.assignedTable?.trim();
    if (!lab) return new Set();
    const id = labelToId.get(lab.toLowerCase());
    if (!id) return new Set();
    const t = tableById.get(id);
    return t ? physicalFootprintForTableRow(t) : new Set();
  }

  function belongsToTable(r: Reservation, dt: DiningTable): boolean {
    return physicalFpForReservation(r).has(dt.id);
  }

  return tables
    .filter((t) => t.active && !(t.unionMemberIds && t.unionMemberIds.trim()))
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
          reservationSource: overviewSource(r.source),
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
          reservationSource: overviewSource(r.source),
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
          reservationSource: overviewSource(r.source),
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
          reservationSource: null,
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
        reservationSource: null,
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
