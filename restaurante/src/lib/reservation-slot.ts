/** Duración por defecto de una reserva si no hay `endsAt` (solapes). */
export const DEFAULT_RESERVATION_SLOT_MS = 2 * 60 * 60 * 1000;

export function reservationSlotEnd(startsAt: Date, endsAt: Date | null): Date {
  if (endsAt) return endsAt;
  return new Date(startsAt.getTime() + DEFAULT_RESERVATION_SLOT_MS);
}

export function rangesOverlap(a0: Date, a1: Date, b0: Date, b1: Date): boolean {
  return a0.getTime() < b1.getTime() && b0.getTime() < a1.getTime();
}
