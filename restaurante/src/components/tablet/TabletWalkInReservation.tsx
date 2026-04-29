"use client";

import { useCallback, useEffect, useState } from "react";
import {
  tabletAlertError,
  tabletBtnPrimary,
  tabletCard,
  tabletInput,
  tabletTextarea,
} from "@/components/tablet/tablet-tokens";

type DiningOpt = { id: string; label: string; zone: string | null; capacity: number };

function toDatetimeLocalValue(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

type Props = {
  onSessionLost: () => void;
  onCreated: (summary: string) => void;
};

export function TabletWalkInReservation({ onSessionLost, onCreated }: Props) {
  const [tables, setTables] = useState<DiningOpt[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [partySize, setPartySize] = useState(2);
  const [datetime, setDatetime] = useState(() => toDatetimeLocalValue(new Date()));
  const [endsAt, setEndsAt] = useState("");
  const [notes, setNotes] = useState("");
  const [staffNotes, setStaffNotes] = useState("");
  const [tableId, setTableId] = useState("");
  const [status, setStatus] = useState<"CONFIRMED" | "PENDING">("CONFIRMED");
  /** PHONE = llamada; WALKIN = viene al local */
  const [tabletSource, setTabletSource] = useState<"PHONE" | "WALKIN">("PHONE");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTables = useCallback(async () => {
    const res = await fetch("/api/dining-tables", { credentials: "include" });
    if (res.status === 401 || res.status === 403) {
      onSessionLost();
      return;
    }
    if (!res.ok) return;
    const data = (await res.json()) as { tables: DiningOpt[] };
    setTables(data.tables);
  }, [onSessionLost]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadTables();
    });
  }, [loadTables]);

  const byZone = useCallback(() => {
    const m = new Map<string, DiningOpt[]>();
    for (const t of tables) {
      const z = t.zone?.trim() || "Mesas";
      if (!m.has(z)) m.set(z, []);
      m.get(z)!.push(t);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [tables]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const startsAt = new Date(datetime);
    if (Number.isNaN(startsAt.getTime())) {
      setError("Revisa fecha y hora.");
      return;
    }
    setBusy(true);
    const payload: Record<string, unknown> = {
      customerName: name.trim(),
      phone: phone.trim(),
      customerEmail: email.trim() || null,
      partySize,
      startsAt: startsAt.toISOString(),
      notes: notes.trim() || null,
      staffNotes: staffNotes.trim() || null,
      tableId: tableId || null,
      status,
      tabletSource,
    };
    if (endsAt.trim()) {
      const end = new Date(endsAt);
      if (!Number.isNaN(end.getTime())) payload.endsAt = end.toISOString();
    }
    const res = await fetch("/api/tablet/reservations", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (res.status === 401 || res.status === 403) {
      onSessionLost();
      return;
    }
    if (!res.ok) {
      setError(typeof data.error === "string" ? data.error : "No se pudo guardar");
      return;
    }
    const created = data as { customerName?: string; startsAt?: string };
    onCreated(
      `Reserva creada: ${created.customerName ?? name} · ${new Date(created.startsAt ?? startsAt).toLocaleString()}`,
    );
    setName("");
    setPhone("");
    setEmail("");
    setPartySize(2);
    setDatetime(toDatetimeLocalValue(new Date()));
    setEndsAt("");
    setNotes("");
    setStaffNotes("");
    setTableId("");
    setStatus("CONFIRMED");
    setTabletSource("PHONE");
  }

  return (
    <section className={tabletCard}>
      <h2 className="font-display text-2xl font-semibold text-[#1a1614] md:text-3xl">Reserva por teléfono o recepción</h2>
      <p className="mt-2 text-lg leading-relaxed text-[#5c4f47]">
        Cliente que llama o acude al local sin reserva web. El tipo de alta queda en el listado (Teléfono / Mostrador).
      </p>

      <div className="mt-6 rounded-2xl border border-[#8f1d1d]/15 bg-gradient-to-br from-[#fdf8f3] to-[#f5ebe3] p-5">
        <p className="text-sm font-bold uppercase tracking-wider text-[#6b1518]/80">Tipo de alta</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label
            className={`flex min-h-[72px] cursor-pointer items-center gap-4 rounded-2xl border-2 px-5 py-4 transition has-[:checked]:border-[#8f1d1d] has-[:checked]:bg-white has-[:checked]:shadow-md ${
              tabletSource === "PHONE"
                ? "border-[#8f1d1d] bg-white shadow-md"
                : "border-[#2c1810]/[0.08] bg-white/70"
            }`}
          >
            <input
              type="radio"
              name="tabletSource"
              className="h-5 w-5 accent-[#8f1d1d]"
              checked={tabletSource === "PHONE"}
              onChange={() => setTabletSource("PHONE")}
            />
            <span className="text-lg font-semibold text-[#1a1614]">Llamada telefónica</span>
          </label>
          <label
            className={`flex min-h-[72px] cursor-pointer items-center gap-4 rounded-2xl border-2 px-5 py-4 transition has-[:checked]:border-[#8f1d1d] has-[:checked]:bg-white has-[:checked]:shadow-md ${
              tabletSource === "WALKIN"
                ? "border-[#8f1d1d] bg-white shadow-md"
                : "border-[#2c1810]/[0.08] bg-white/70"
            }`}
          >
            <input
              type="radio"
              name="tabletSource"
              className="h-5 w-5 accent-[#8f1d1d]"
              checked={tabletSource === "WALKIN"}
              onChange={() => setTabletSource("WALKIN")}
            />
            <span className="text-lg font-semibold text-[#1a1614]">Mostrador / walk-in</span>
          </label>
        </div>
      </div>

      {error && (
        <p className={`${tabletAlertError} mt-6`} role="alert">
          {error}
        </p>
      )}

      <form className="mt-8 flex flex-col gap-6" onSubmit={submit}>
        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Nombre</span>
          <input
            required
            className={tabletInput}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Teléfono</span>
          <input
            required
            type="tel"
            inputMode="tel"
            className={`${tabletInput} tabular-nums`}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Email (opcional)</span>
          <input
            type="email"
            className={tabletInput}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <div className="grid gap-6 sm:grid-cols-2">
          <label className="flex flex-col gap-2">
            <span className="text-base font-semibold text-[#3d3532]">Comensales</span>
            <input
              required
              type="number"
              min={1}
              max={40}
              className={tabletInput}
              value={partySize}
              onChange={(e) => setPartySize(Number(e.target.value))}
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="text-base font-semibold text-[#3d3532]">Estado</span>
            <select
              className={tabletInput}
              value={status}
              onChange={(e) => setStatus(e.target.value as "CONFIRMED" | "PENDING")}
            >
              <option value="CONFIRMED">Confirmada (habitual por teléfono)</option>
              <option value="PENDING">Pendiente</option>
            </select>
          </label>
        </div>

        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Día y hora</span>
          <input
            required
            type="datetime-local"
            className={tabletInput}
            value={datetime}
            onChange={(e) => setDatetime(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Fin de franja (opcional)</span>
          <input
            type="datetime-local"
            className={tabletInput}
            value={endsAt}
            onChange={(e) => setEndsAt(e.target.value)}
          />
          <span className="text-base text-[#6b5d55]">Si no indicas, se usan 2 h para comprobar solapes de mesa.</span>
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Mesa (opcional)</span>
          <select
            className={tabletInput}
            value={tableId}
            onChange={(e) => setTableId(e.target.value)}
          >
            <option value="">Sin asignar aún</option>
            {byZone().map(([zone, list]) => (
              <optgroup key={zone} label={zone}>
                {list.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label} · {t.capacity} pax
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Notas para el cliente / cocina</span>
          <textarea
            className={tabletTextarea}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Alergias, celebración, hora aproximada…"
          />
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Notas internas (opcional)</span>
          <textarea
            className={`${tabletTextarea} min-h-[88px]`}
            value={staffNotes}
            onChange={(e) => setStaffNotes(e.target.value)}
            placeholder="Solo equipo"
          />
        </label>

        <button type="submit" disabled={busy} className={tabletBtnPrimary}>
          {busy ? "Guardando…" : "Registrar reserva"}
        </button>
      </form>
    </section>
  );
}
