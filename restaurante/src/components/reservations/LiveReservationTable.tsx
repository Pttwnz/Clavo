"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ReservationSource, ReservationStatus } from "@/generated/prisma/enums";
import {
  tabletAlertError,
  tabletPanel,
  tabletTableWrap,
  tabletThead,
} from "@/components/tablet/tablet-tokens";
import { DiningFloorMap } from "@/components/reservations/DiningFloorMap";

export type ReservationRow = {
  id: string;
  customerName: string;
  customerEmail: string | null;
  phone: string;
  partySize: number;
  startsAt: string;
  endsAt: string | null;
  arrivedAt: string | null;
  assignedTable: string | null;
  tableId: string | null;
  diningTable: { id: string; label: string; zone: string | null; capacity: number } | null;
  notes: string | null;
  staffNotes: string | null;
  status: keyof typeof ReservationStatus;
  createdAt: string;
  updatedAt: string;
  source?: keyof typeof ReservationSource;
};

type DiningTableOpt = { id: string; label: string; zone: string | null; capacity: number };

function tableSelectValue(r: ReservationRow, diningTables: DiningTableOpt[]): string {
  if (r.tableId) return r.tableId;
  const lab = r.assignedTable?.trim();
  if (!lab) return "";
  return diningTables.find((t) => t.label === lab)?.id ?? "";
}

const statusLabels: Record<string, string> = {
  PENDING: "Pendiente",
  CONFIRMED: "Confirmada",
  CANCELLED: "Cancelada",
  SEATED: "En mesa",
  COMPLETED: "Completada",
};

const sourceLabels: Record<string, string> = {
  WEB: "Web",
  TABLET_PHONE: "Teléfono",
  TABLET_WALKIN: "Mostrador",
};

/** Badges alineados con la paleta del panel (sin violetas/azules genéricos). */
function sourceBadgeClass(src: string | undefined) {
  switch (src) {
    case "TABLET_PHONE":
      return "bg-[#efe8e0] text-[#4a4038] ring-1 ring-[#2c1810]/10";
    case "TABLET_WALKIN":
      return "bg-[#fff4ed] text-[#7a3410] ring-1 ring-[#e8a87c]/50";
    case "WEB":
    default:
      return "bg-[#eef2f6] text-[#2c3540] ring-1 ring-[#2c1810]/8";
  }
}

function fmtShort(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtClockShort(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** Texto compacto tipo "en 42 min" para la franja de llegadas. */
function minutesUntilShort(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  const minsTotal = Math.max(0, Math.round(ms / 60000));
  if (minsTotal <= 0) return "ahora";
  if (minsTotal < 60) return `en ${minsTotal} min`;
  const h = Math.floor(minsTotal / 60);
  const m = minsTotal % 60;
  if (m === 0) return `en ${h} h`;
  return `en ${h} h ${m} min`;
}

function reservationTableLabel(r: ReservationRow): string {
  if (r.diningTable?.label) return `Mesa ${r.diningTable.label}`;
  const t = r.assignedTable?.trim();
  if (t) return `Mesa ${t}`;
  return "Sin mesa";
}

type Props = {
  onTabletSessionLost?: () => void;
};

type ListFilter = "all" | "today" | "active";

function isSameLocalCalendarDay(iso: string, ref = new Date()): boolean {
  const d = new Date(iso);
  return (
    d.getFullYear() === ref.getFullYear() &&
    d.getMonth() === ref.getMonth() &&
    d.getDate() === ref.getDate()
  );
}

export function LiveReservationTable({ onTabletSessionLost }: Props) {
  const [rows, setRows] = useState<ReservationRow[]>([]);
  const [diningTables, setDiningTables] = useState<DiningTableOpt[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listFilter, setListFilter] = useState<ListFilter>("all");

  const listUrl = "/api/tablet/reservations";
  const streamUrl = "/api/tablet/reservations/stream";
  const creds = "include" as RequestCredentials;

  const patchUrl = useCallback((id: string) => `/api/tablet/reservations/${id}`, []);

  const load = useCallback(async () => {
    try {
      const res = await fetch(listUrl, { credentials: creds });
      if (res.status === 401) {
        onTabletSessionLost?.();
        return;
      }
      if (res.status === 403) {
        onTabletSessionLost?.();
        return;
      }
      if (!res.ok) throw new Error("No se pudieron cargar las reservas");
      const data = (await res.json()) as ReservationRow[];
      setRows(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  }, [creds, listUrl, onTabletSessionLost]);

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, [load]);

  useEffect(() => {
    void (async () => {
      const res = await fetch("/api/dining-tables", { credentials: creds });
      if (!res.ok) return;
      const data = (await res.json()) as { tables: DiningTableOpt[] };
      setDiningTables(data.tables);
    })();
  }, [creds]);

  const tablesByZone = useMemo(() => {
    const m = new Map<string, DiningTableOpt[]>();
    for (const t of diningTables) {
      const z = t.zone?.trim() || "Mesas";
      if (!m.has(z)) m.set(z, []);
      m.get(z)!.push(t);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [diningTables]);

  const displayRows = useMemo(() => {
    if (listFilter === "all") return rows;
    if (listFilter === "today") return rows.filter((r) => isSameLocalCalendarDay(r.startsAt));
    return rows.filter((r) => ["PENDING", "CONFIRMED", "SEATED"].includes(r.status));
  }, [rows, listFilter]);

  /** Próximas llegadas confirmadas/pendientes (sin registrar llegada), ventana ~10 h. */
  const upcomingArrivals = useMemo(() => {
    const now = Date.now();
    const horizon = now + 1000 * 60 * 60 * 10;
    return rows
      .filter(
        (r) =>
          (r.status === "PENDING" || r.status === "CONFIRMED") &&
          !r.arrivedAt &&
          new Date(r.startsAt).getTime() > now &&
          new Date(r.startsAt).getTime() < horizon,
      )
      .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime())
      .slice(0, 20);
  }, [rows]);

  useEffect(() => {
    const es = new EventSource(streamUrl, { withCredentials: true });
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.addEventListener("message", (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as { type?: string };
        if (msg.type === "reservations_updated") void load();
      } catch {
        /* ignore */
      }
    });
    return () => es.close();
  }, [load, streamUrl]);

  async function patch(id: string, body: Record<string, unknown>) {
    const res = await fetch(patchUrl(id), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: creds,
      body: JSON.stringify(body),
    });
    if (res.status === 401) {
      onTabletSessionLost?.();
      return;
    }
    if (!res.ok) {
      setError("No se pudo guardar");
      return;
    }
    void load();
  }

  function quickStatusAction(r: ReservationRow): { label: string; body: Record<string, unknown> } | null {
    if (r.status === "PENDING") {
      return { label: "Confirmar", body: { status: "CONFIRMED" } };
    }
    if (r.status === "CONFIRMED") {
      return {
        label: "Sentar",
        body: { status: "SEATED", arrivedAt: r.arrivedAt ?? new Date().toISOString() },
      };
    }
    if (r.status === "SEATED") {
      return { label: "Cerrar", body: { status: "COMPLETED" } };
    }
    return null;
  }

  const cell = "px-4 py-4 text-base leading-snug";
  const th = "px-4 py-4 text-[0.7rem]";
  const inputCls =
    "w-full min-w-[5rem] rounded-xl border-2 border-[#2c1810]/[0.1] bg-white px-3 py-2.5 text-base font-medium text-[#1a1614] shadow-inner outline-none focus:border-[#8f1d1d]/45 focus:ring-2 focus:ring-[#8f1d1d]/15";

  const mapWrap = `${tabletPanel} overflow-hidden p-4 sm:p-5`;
  const tableWrap = `${tabletTableWrap} max-h-[min(70vh,900px)] overflow-auto`;
  const theadRow = tabletThead;
  const rowLine =
    "border-b border-[#2c1810]/[0.06] align-top transition hover:bg-[#faf8f5]/90 last:border-0";

  return (
    <div className="space-y-6">
      <div className={mapWrap}>
        <DiningFloorMap onTabletSessionLost={onTabletSessionLost} />
      </div>

      {upcomingArrivals.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-[#2c1810]/[0.08] bg-white shadow-sm">
          <div className="border-b border-[#2c1810]/[0.06] bg-[#fdfaf7]/60 px-3 py-2">
            <span className="text-xs font-semibold tracking-tight text-[#5c4f47]">Próximas llegadas</span>
          </div>
          <ul className="divide-y divide-[#2c1810]/[0.05]">
            {upcomingArrivals.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-1 px-3 py-2.5 text-sm leading-snug text-[#2d2420]"
              >
                <span className="font-semibold tabular-nums text-[#1a1614]">{fmtClockShort(r.startsAt)}</span>
                <span className="text-[#c9b8a8]">·</span>
                <span className="text-[#6b5d55]">{minutesUntilShort(r.startsAt)}</span>
                <span className="text-[#c9b8a8]">·</span>
                <span className="font-medium text-[#2d2420]">{r.customerName}</span>
                <span className="text-[#c9b8a8]">·</span>
                <span className="text-[#6b5d55]">{reservationTableLabel(r)}</span>
                <span className="text-[#c9b8a8]">·</span>
                <span className="tabular-nums text-[#8a7d72]">{r.partySize} pax</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-[#2c1810]/[0.08] bg-[#fdfaf7]/70 px-3 py-2.5 text-sm text-[#5c4f47]">
        <span className="inline-flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-amber-400"}`} />
          <span className="font-medium text-[#4a4038]">
            {connected ? "Lista sincronizada" : "Reconectando…"}
          </span>
        </span>
        <span className="text-[#c9b8a8]">|</span>
        <span className="text-[#6b5d55]">
          Origen: web, teléfono o mostrador. Cupo por franja según horarios.
        </span>
      </div>
      {error && (
        <p className={tabletAlertError} role="alert" aria-live="polite">
          {error}
        </p>
      )}

      <div className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[#2c1810]/[0.06] pb-3">
          <div>
            <h3 className="font-display text-xl font-semibold text-[#1a1614]">Listado de reservas</h3>
            <p className="mt-0.5 text-xs text-[#6b5d55]">
              Mostrando {displayRows.length} de {rows.length} · filtros para turno punta
            </p>
          </div>
          <div
            className="flex flex-wrap gap-1.5"
            role="group"
            aria-label="Filtrar listado"
          >
            {(
              [
                { id: "all" as const, label: "Todas" },
                { id: "today" as const, label: "Hoy" },
                { id: "active" as const, label: "Activas" },
              ] as const
            ).map(({ id, label }) => {
              const active = listFilter === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setListFilter(id)}
                  className={
                    active
                      ? "rounded-full bg-[#8f1d1d] px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm shadow-[#6b1518]/20"
                      : "rounded-full border border-[#2c1810]/10 bg-white px-3.5 py-1.5 text-xs font-medium text-[#5c4f47] transition hover:bg-[#faf6ed]"
                  }
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        <div className={tableWrap}>
          <table className="min-w-[1280px] w-full text-left">
            <thead className="sticky top-0 z-20 bg-[#faf6ed]">
              <tr className={`${theadRow} shadow-[0_1px_0_rgba(44,24,16,0.07)]`}>
              <th className={th}>Alta</th>
              <th className={th}>Hora prevista</th>
              <th className={th}>Llegada</th>
              <th className={th}>Mesa</th>
              <th className={th}>Origen</th>
              <th className={th}>Cliente</th>
              <th className={th}>Contacto</th>
              <th className={th}>Pax</th>
              <th className={th}>Notas cliente</th>
              <th className={th}>Equipo</th>
              <th className={th}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((r) => {
              const quick = quickStatusAction(r);
              return (
              <tr key={r.id} className={rowLine}>
                <td className={`${cell} whitespace-nowrap tabular-nums text-[#6b5d55]`}>{fmtShort(r.createdAt)}</td>
                <td className={`${cell} whitespace-nowrap tabular-nums font-medium text-[#1a1614]`}>
                  {fmtShort(r.startsAt)}
                </td>
                <td className={cell}>
                  <div className="flex flex-col gap-1">
                    {r.arrivedAt ? (
                      <>
                        <span className="whitespace-nowrap tabular-nums text-zinc-800">{fmtShort(r.arrivedAt)}</span>
                        <button
                          type="button"
                          className="text-left text-xs text-amber-800 underline"
                          onClick={() => void patch(r.id, { arrivedAt: null })}
                        >
                          Quitar llegada
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="rounded-xl border border-[#2c1810]/10 bg-[#faf8f5] px-3 py-2.5 text-sm font-semibold text-[#1a1614] shadow-sm transition hover:bg-[#f0ebe3] active:scale-[0.99]"
                        onClick={() => void patch(r.id, { arrivedAt: new Date().toISOString() })}
                      >
                        Registrar llegada
                      </button>
                    )}
                  </div>
                </td>
                <td className={cell}>
                  <div className="flex min-w-[7rem] flex-col gap-1">
                    <select
                      className={inputCls}
                      aria-label="Mesa del catálogo"
                      value={tableSelectValue(r, diningTables)}
                      onChange={(e) => {
                        const v = e.target.value;
                        void patch(r.id, { tableId: v.length ? v : null });
                      }}
                    >
                      <option value="">Sin mesa</option>
                      {tablesByZone.map(([zone, list]) => (
                        <optgroup key={zone} label={zone}>
                          {list.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.label} ({t.capacity} pax)
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    {r.tableId == null && r.assignedTable?.trim() && !diningTables.some((t) => t.label === r.assignedTable?.trim()) && (
                      <span className="text-[11px] text-amber-800" title="Texto antiguo sin enlace al catálogo">
                        Texto: {r.assignedTable}
                      </span>
                    )}
                  </div>
                </td>
                <td className={cell}>
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${sourceBadgeClass(r.source)}`}
                  >
                    {sourceLabels[r.source ?? "WEB"] ?? r.source ?? "Web"}
                  </span>
                </td>
                <td className={`${cell} font-medium text-[#1a1614]`}>{r.customerName}</td>
                <td className={cell}>
                  <div className="space-y-0.5">
                    <a
                      href={`tel:${r.phone}`}
                      className="block font-medium text-[#8f1d1d] underline decoration-[#8f1d1d]/30 underline-offset-2 tabular-nums hover:decoration-[#8f1d1d]"
                    >
                      {r.phone}
                    </a>
                    {r.customerEmail && (
                      <a
                        href={`mailto:${r.customerEmail}`}
                        className="block break-all text-xs text-zinc-600 underline"
                      >
                        {r.customerEmail}
                      </a>
                    )}
                  </div>
                </td>
                <td className={`${cell} tabular-nums`}>{r.partySize}</td>
                <td className={`${cell} max-w-[200px] text-zinc-700`}>
                  {r.notes ? (
                    <span className="line-clamp-4 whitespace-pre-wrap" title={r.notes}>
                      {r.notes}
                    </span>
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </td>
                <td className={cell}>
                  <textarea
                    key={`${r.id}-staff-${r.updatedAt}`}
                    className="min-h-[80px] w-full min-w-[120px] max-w-[240px] rounded-xl border-2 border-[#2c1810]/[0.1] bg-white px-3 py-2.5 text-sm text-[#1a1614] shadow-inner outline-none focus:border-[#8f1d1d]/45 focus:ring-2 focus:ring-[#8f1d1d]/12"
                    defaultValue={r.staffNotes ?? ""}
                    placeholder="Interno…"
                    aria-label="Notas de equipo"
                    onBlur={(e) => {
                      const v = e.target.value.trim();
                      const next = v.length ? v : null;
                      const prev = r.staffNotes ?? null;
                      if (next !== prev) void patch(r.id, { staffNotes: next });
                    }}
                  />
                </td>
                <td className={cell}>
                  <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap gap-1">
                      {r.status === "PENDING" && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-950 ring-1 ring-amber-200">
                          Por confirmar
                        </span>
                      )}
                      {r.status === "CONFIRMED" && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-950 ring-1 ring-emerald-200">
                          Confirmada
                        </span>
                      )}
                      {r.status !== "PENDING" && r.status !== "CONFIRMED" && (
                        <span className="text-[11px] font-medium text-zinc-600">{statusLabels[r.status] ?? r.status}</span>
                      )}
                      {quick && (
                        <button
                          type="button"
                          className="rounded-full border border-[#8f1d1d]/25 bg-[#fdf4f4] px-2.5 py-0.5 text-[11px] font-semibold text-[#6b1518] hover:bg-[#fbe9ea]"
                          onClick={() => {
                            void patch(r.id, quick.body);
                          }}
                        >
                          {quick.label}
                        </button>
                      )}
                    </div>
                    <select
                      className="min-h-[48px] w-full min-w-[10rem] rounded-xl border-2 border-[#2c1810]/[0.1] bg-white px-3 py-2 text-base font-semibold text-[#1a1614] shadow-inner outline-none focus:border-[#8f1d1d]/45 focus:ring-2 focus:ring-[#8f1d1d]/12"
                      value={r.status}
                      onChange={(e) =>
                        void patch(r.id, { status: e.target.value as keyof typeof ReservationStatus })
                      }
                    >
                      {Object.entries(ReservationStatus).map(([k]) => (
                        <option key={k} value={k}>
                          {statusLabels[k] ?? k}
                        </option>
                      ))}
                    </select>
                  </div>
                </td>
              </tr>
            );
            })}
          </tbody>
        </table>
        {displayRows.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-[#6b5d55]">
            {rows.length === 0
              ? "No hay reservas todavía."
              : "Ninguna reserva con este filtro. Prueba otra vista o limpia filtros."}
          </p>
        )}
        </div>
      </div>
    </div>
  );
}
