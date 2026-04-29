"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DiningOverviewRow } from "@/lib/dining-overview-types";
import { OccupancyTimer } from "@/components/reservations/OccupancyTimer";

function walkInDetailFromServer(p: number | null | undefined): string {
  return p != null && p >= 1 ? `Ocupación manual · ${p} pax` : "Ocupación manual";
}

type Props = {
  onTabletSessionLost?: () => void;
};

const stateUi: Record<
  DiningOverviewRow["state"],
  { badge: string; rail: string; short: string }
> = {
  free: {
    short: "Libre",
    rail: "border-l-4 border-l-stone-400",
    badge: "bg-stone-50 text-[#5c534c] ring-1 ring-stone-200/90",
  },
  reserved_future: {
    short: "Reserva",
    rail: "border-l-4 border-l-amber-500",
    badge: "bg-amber-50/90 text-amber-950/90 ring-1 ring-amber-200/70",
  },
  reserved_now: {
    short: "En franja",
    rail: "border-l-4 border-l-orange-500",
    badge: "bg-orange-50/90 text-orange-950/90 ring-1 ring-orange-200/60",
  },
  seated: {
    short: "Servicio",
    rail: "border-l-4 border-l-[#8f1d1d]",
    badge: "bg-[#fdf4f4] text-[#6b1518] ring-1 ring-[#8f1d1d]/20",
  },
  walk_in: {
    short: "Manual",
    rail: "border-l-4 border-l-stone-700",
    badge: "bg-stone-100/95 text-stone-800 ring-1 ring-stone-300/70",
  },
};

const LEGEND: { state: DiningOverviewRow["state"]; title: string }[] = [
  { state: "free", title: "Libre" },
  { state: "reserved_future", title: "Reserva próx." },
  { state: "reserved_now", title: "En franja" },
  { state: "seated", title: "Servicio" },
  { state: "walk_in", title: "Manual" },
];

const legendDot: Record<DiningOverviewRow["state"], string> = {
  free: "bg-stone-400",
  reserved_future: "bg-amber-500",
  reserved_now: "bg-orange-500",
  seated: "bg-[#8f1d1d]",
  walk_in: "bg-stone-700",
};

function formatAgoShort(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h`;
}

export function DiningFloorMap({ onTabletSessionLost }: Props) {
  const [rows, setRows] = useState<DiningOverviewRow[]>([]);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [, setClock] = useState(0);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [partyDraft, setPartyDraft] = useState<Record<string, string>>({});
  const [confirmReleaseId, setConfirmReleaseId] = useState<string | null>(null);

  const streamUrl = "/api/tablet/reservations/stream";
  const creds = "include" as RequestCredentials;

  useEffect(() => {
    const id = window.setInterval(() => setClock((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const tablesByZone = useMemo(() => {
    const m = new Map<string, DiningOverviewRow[]>();
    for (const t of rows) {
      const z = t.zone?.trim() || "Sala principal";
      if (!m.has(z)) m.set(z, []);
      m.get(z)!.push(t);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b, "es"));
  }, [rows]);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/dining-tables/overview", {
        credentials: creds,
        cache: "no-store",
      });
      if (res.status === 401) {
        onTabletSessionLost?.();
        return;
      }
      if (!res.ok) throw new Error("No se pudo cargar el mapa de mesas");
      const data = (await res.json()) as {
        overview: DiningOverviewRow[];
        generatedAt?: string;
      };
      setRows(data.overview);
      if (data.generatedAt) setGeneratedAt(data.generatedAt);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  }, [creds, onTabletSessionLost]);

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, [load]);

  const skipNextConnectedRef = useRef(true);

  useEffect(() => {
    const es = new EventSource(streamUrl, { withCredentials: true });
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.addEventListener("message", (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as { type?: string };
        if (msg.type === "connected") {
          if (skipNextConnectedRef.current) {
            skipNextConnectedRef.current = false;
            return;
          }
          void load();
          return;
        }
        if (msg.type === "reservations_updated") void load();
      } catch {
        /* ignore */
      }
    });
    return () => es.close();
  }, [load, streamUrl]);

  useEffect(() => {
    const ms = connected ? 28000 : 8000;
    const id = window.setInterval(() => {
      void load();
    }, ms);
    return () => window.clearInterval(id);
  }, [load, connected]);

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [load]);

  const patchWalkIn = useCallback(
    async (tableId: string, walkInOccupied: boolean, walkInPartySize: number | null) => {
      setSavingId(tableId);
      setError(null);
      setConfirmReleaseId(null);
      try {
        const res = await fetch(`/api/dining-tables/${tableId}`, {
          method: "PATCH",
          credentials: creds,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ walkInOccupied, walkInPartySize }),
        });
        if (res.status === 401) {
          onTabletSessionLost?.();
          return;
        }
        if (!res.ok) {
          const d = (await res.json().catch(() => ({}))) as { error?: string };
          setError(typeof d.error === "string" ? d.error : "No se pudo actualizar la mesa");
          return;
        }
        const updated = (await res.json()) as {
          walkInOccupied?: boolean;
          walkInPartySize?: number | null;
          walkInStartedAt?: string | null;
        };
        if (updated.walkInOccupied === true) {
          const since = updated.walkInStartedAt ?? new Date().toISOString();
          setRows((prev) =>
            prev.map((row) =>
              row.id === tableId
                ? {
                    ...row,
                    state: "walk_in",
                    detail: walkInDetailFromServer(updated.walkInPartySize),
                    occupiedSinceIso: since,
                  }
                : row,
            ),
          );
        }
        await load();
      } finally {
        setSavingId(null);
      }
    },
    [creds, load, onTabletSessionLost],
  );

  const isTablet = true;

  const inputWalkIn =
    "rounded-lg border border-[#2c1810]/12 bg-white text-[#2d2420] outline-none transition focus:border-[#8f1d1d]/45 focus:ring-2 focus:ring-[#8f1d1d]/10";
  const btnPrimary =
    "rounded-lg bg-[#8f1d1d] px-3 font-semibold text-[#faf6ed] shadow-sm shadow-[#6b1518]/20 transition hover:bg-[#7a1919] disabled:opacity-45";
  const btnGhost =
    "rounded-lg border border-[#2c1810]/12 bg-white font-medium text-[#3d3532] transition hover:bg-[#faf6ed] disabled:opacity-45";

  const updatedLabel =
    generatedAt != null
      ? `${new Date(generatedAt).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", second: "2-digit" })} · hace ${formatAgoShort(generatedAt)}`
      : null;

  const gridClass = isTablet
    ? "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
    : "grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6";

  const renderCard = (t: DiningOverviewRow) => {
    const u = stateUi[t.state];
    const busy = savingId === t.id;
    return (
      <article
        key={t.id}
        aria-busy={busy}
        className={`flex min-h-0 flex-col rounded-xl border-b border-r border-t border-[#2c1810]/[0.08] bg-white shadow-[0_1px_3px_rgba(26,18,16,0.05)] transition hover:shadow-[0_4px_14px_rgba(26,18,16,0.07)] ${u.rail}`}
      >
        <div className={`flex flex-1 flex-col ${isTablet ? "gap-2 p-3.5" : "gap-1.5 p-3"}`}>
          <div className="flex items-start justify-between gap-2">
            <span
              className={`min-w-0 font-semibold tabular-nums leading-none tracking-tight text-[#1a1614] ${isTablet ? "text-xl" : "text-base"}`}
            >
              {t.label}
            </span>
            <span className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-semibold ${u.badge}`}>
              {u.short}
            </span>
          </div>

          <p className={`text-[#6b5d55] ${isTablet ? "text-sm" : "text-[11px] leading-snug"}`}>
            {[t.zone, `${t.capacity} pax`].filter(Boolean).join(" · ")}
          </p>

          {t.occupiedSinceIso && (
            <div
              className={`flex items-center justify-between gap-2 border-t border-[#2c1810]/[0.06] pt-2 ${isTablet ? "pt-2.5" : ""}`}
            >
              <span className="text-[10px] font-medium uppercase tracking-wide text-[#8a7d72]">
                Duración
              </span>
              <OccupancyTimer
                sinceIso={t.occupiedSinceIso}
                warnAfterMinutes={90}
                className={isTablet ? "text-base" : "text-sm"}
              />
            </div>
          )}

          {t.detail && (
            <p
              className={`line-clamp-4 min-w-0 text-[#4a4038] ${isTablet ? "text-sm leading-relaxed" : "text-[11px] leading-relaxed"}`}
            >
              {t.detail}
            </p>
          )}
        </div>

        {(t.state === "free" || t.state === "walk_in") && (
          <div
            className={`border-t border-[#2c1810]/[0.06] bg-[#fdfaf7]/50 ${isTablet ? "p-3.5 pt-3" : "p-3 pt-2.5"}`}
          >
            {t.state === "free" && (
              <div className="flex flex-wrap items-center gap-2">
                <label className="sr-only">Comensales (walk-in)</label>
                <input
                  type="number"
                  min={1}
                  max={t.capacity}
                  inputMode="numeric"
                  aria-label="Comensales"
                  className={`${inputWalkIn} text-center font-medium tabular-nums ${isTablet ? "h-11 w-[4.5rem] text-base" : "h-9 w-14 text-sm"}`}
                  value={partyDraft[t.id] ?? String(Math.min(2, Math.max(1, t.capacity)))}
                  onChange={(e) => setPartyDraft((d) => ({ ...d, [t.id]: e.target.value }))}
                />
                <button
                  type="button"
                  disabled={busy}
                  className={`${btnPrimary} ${isTablet ? "h-11 min-w-[5.5rem] text-sm" : "h-9 min-w-[4.75rem] text-xs"}`}
                  onClick={() => {
                    const raw = partyDraft[t.id] ?? String(Math.min(2, Math.max(1, t.capacity)));
                    const n = Number(raw);
                    const p = Number.isFinite(n)
                      ? Math.min(t.capacity, Math.max(1, Math.floor(n)))
                      : Math.min(2, t.capacity);
                    void patchWalkIn(t.id, true, p);
                  }}
                >
                  {busy ? "…" : "Ocupar"}
                </button>
              </div>
            )}
            {t.state === "walk_in" &&
              (confirmReleaseId === t.id ? (
                <div className={`flex flex-col gap-2 ${isTablet ? "gap-3" : ""}`}>
                  <p className="text-center text-[11px] font-medium text-[#6b5d55]">
                    ¿Liberar esta mesa?
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      className={`${btnPrimary} flex-1 ${isTablet ? "h-11 text-sm" : "h-9 text-xs"}`}
                      onClick={() => void patchWalkIn(t.id, false, null)}
                    >
                      {busy ? "…" : "Sí, liberar"}
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      className={`${btnGhost} flex-1 ${isTablet ? "h-11 text-sm" : "h-9 text-xs"}`}
                      onClick={() => setConfirmReleaseId(null)}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  className={`${btnGhost} w-full ${isTablet ? "h-12 text-base" : "h-9 text-xs"}`}
                  onClick={() => setConfirmReleaseId(t.id)}
                >
                  Liberar mesa
                </button>
              ))}
          </div>
        )}
      </article>
    );
  };

  return (
    <div className={isTablet ? "space-y-4" : "space-y-3"}>
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[#2c1810]/[0.08] pb-3">
        <div className="min-w-0 space-y-1">
          <h3
            className={
              isTablet
                ? "font-display text-lg font-semibold tracking-tight text-[#1a1614]"
                : "text-sm font-semibold tracking-tight text-[#2d2420]"
            }
          >
            Sala · mesas
          </h3>
          <p
            className={
              isTablet
                ? "max-w-xl text-sm leading-relaxed text-[#6b5d55]"
                : "max-w-xl text-[11px] leading-snug text-[#6b5d55]"
            }
          >
            {isTablet
              ? "Walk-in solo en mesas sin reserva activa. Los datos se sincronizan al instante."
              : "Marque ocupación walk-in en mesas libres; confirme al liberar."}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 text-[11px] text-[#6b5d55]">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-amber-400"}`}
              aria-hidden
            />
            <span className="font-medium">{connected ? "Sincronizado" : "Reconectando"}</span>
          </div>
          {updatedLabel && (
            <time className="text-[10px] tabular-nums text-[#8a7d72]" dateTime={generatedAt ?? undefined}>
              Actualizado · {updatedLabel}
            </time>
          )}
        </div>
      </div>

      <div
        className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-[#2c1810]/[0.06] bg-gradient-to-r from-[#faf6ed]/80 to-[#fdfaf7]/90 px-3 py-2.5 ${isTablet ? "py-3" : ""}`}
        aria-label="Leyenda de estados de mesa"
      >
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8a7d72]">Leyenda</span>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {LEGEND.map(({ state, title }) => (
            <span
              key={state}
              className={`inline-flex items-center gap-1.5 ${isTablet ? "text-sm" : "text-[11px]"} font-medium text-[#5c4f47]`}
            >
              <span className={`h-2.5 w-2.5 shrink-0 rounded-sm shadow-sm ${legendDot[state]}`} />
              {title}
            </span>
          ))}
        </div>
      </div>

      {error && (
        <p
          className={
            isTablet
              ? "rounded-xl border border-red-200/90 bg-red-50/95 px-4 py-3 text-sm text-red-900"
              : "rounded-lg border border-red-200/90 bg-red-50/95 px-3 py-2 text-xs text-red-900"
          }
          role="alert"
          aria-live="polite"
        >
          {error}
        </p>
      )}

      {tablesByZone.map(([zone, list]) => (
        <div key={zone} className="space-y-2">
          {tablesByZone.length > 1 && (
            <h4
              className={`font-semibold uppercase tracking-[0.14em] text-[#8a7d72] ${isTablet ? "text-xs" : "text-[10px]"}`}
            >
              {zone}
            </h4>
          )}
          <div className={gridClass}>{list.map((t) => renderCard(t))}</div>
        </div>
      ))}

      {rows.length === 0 && !error && (
        <p className="text-sm text-[#6b5d55]">No hay mesas en catálogo. Configúrelas en administración.</p>
      )}
    </div>
  );
}
