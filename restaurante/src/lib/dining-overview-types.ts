export type DiningOverviewState = "free" | "seated" | "reserved_now" | "reserved_future" | "walk_in";

export type DiningOverviewRow = {
  id: string;
  label: string;
  zone: string | null;
  capacity: number;
  state: DiningOverviewState;
  detail: string | null;
  /** ISO 8601: inicio de uso de la mesa (reserva en franja, sentados o walk-in). null = sin cronómetro. */
  occupiedSinceIso: string | null;
};
