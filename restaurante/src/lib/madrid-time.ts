import { format, getHours, getISODay, getMinutes } from "date-fns";
import { fromZonedTime, toZonedTime } from "date-fns-tz";

export const MADRID_TZ = "Europe/Madrid";

/** Fecha/hora en calendario Madrid: ISO weekday 1=lun…7=dom, minutos [0,1440), yyyy-MM-dd */
export function madridCalendar(d: Date) {
  const z = toZonedTime(d, MADRID_TZ);
  return {
    isoWeekday: getISODay(z),
    minuteOfDay: getHours(z) * 60 + getMinutes(z),
    ymd: format(z, "yyyy-MM-dd"),
  };
}

export function madridYmdToUtcRange(ymd: string): { start: Date; end: Date } {
  const start = fromZonedTime(`${ymd}T00:00:00`, MADRID_TZ);
  const end = fromZonedTime(`${ymd}T23:59:59.999`, MADRID_TZ);
  return { start, end };
}

/**
 * Valor de `input type="datetime-local"` (sin zona). Se interpreta siempre como hora
 * del restaurante (Europa/Madrid), no como hora local del navegador.
 */
export function parseDatetimeLocalAsMadrid(value: string): Date {
  const v = value.trim();
  if (!v) return new Date(NaN);
  return fromZonedTime(v, MADRID_TZ);
}
