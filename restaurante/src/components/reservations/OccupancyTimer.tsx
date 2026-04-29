"use client";

import { useEffect, useState } from "react";

function formatElapsed(ms: number): string {
  if (ms < 0) ms = 0;
  const totalS = Math.floor(ms / 1000);
  const h = Math.floor(totalS / 3600);
  const m = Math.floor((totalS % 3600) / 60);
  const s = totalS % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

type Props = {
  sinceIso: string;
  className?: string;
  /** Si el tiempo en mesa supera estos minutos, aplica aviso visual (p. ej. servicio largo). */
  warnAfterMinutes?: number;
  classNameWhenWarn?: string;
};

/** Cronómetro en vivo desde `sinceIso` (ISO 8601). */
export function OccupancyTimer({
  sinceIso,
  className = "",
  warnAfterMinutes,
  classNameWhenWarn = "text-amber-800",
}: Props) {
  const [, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setTick((n) => n + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [sinceIso]);

  const ms = Date.now() - new Date(sinceIso).getTime();
  const warn =
    warnAfterMinutes != null && ms >= warnAfterMinutes * 60 * 1000;

  return (
    <span
      className={`font-mono font-semibold tabular-nums tracking-tight ${warn ? classNameWhenWarn : "text-[#1a1614]"} ${className || "text-sm"}`}
    >
      {formatElapsed(ms)}
    </span>
  );
}
