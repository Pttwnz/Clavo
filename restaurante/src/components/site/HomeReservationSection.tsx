"use client";

import { useEffect, useState } from "react";
import { parseDatetimeLocalAsMadrid } from "@/lib/madrid-time";

const inputClass =
  "w-full rounded-xl border border-[#2d2420]/10 bg-[#faf8f5] px-4 py-3 text-[#2d2420] shadow-inner shadow-[#2d1818]/[0.03] outline-none ring-[#8f1d1d]/20 transition placeholder:text-[#9a8a80] focus:border-[#8f1d1d]/35 focus:bg-white focus:ring-2";

const labelClass = "text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b5a4e]";

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-5 w-5 shrink-0 text-[#8f1d1d] transition-transform duration-300 ${open ? "rotate-180" : ""}`}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function HomeReservationSection() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [partySize, setPartySize] = useState(2);
  const [datetime, setDatetime] = useState("");
  const [notes, setNotes] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  /** Enlace de confirmación si el correo no se envió (p. ej. sin SMTP); el API lo devuelve en `confirm_url`. */
  const [confirmLinkUrl, setConfirmLinkUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [quotaHint, setQuotaHint] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    const openFromHash = () => {
      if (typeof window !== "undefined" && window.location.hash === "#reserva") {
        setPanelOpen(true);
      }
    };
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
    return () => window.removeEventListener("hashchange", openFromHash);
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    let clearTimer: number | undefined;

    if (!datetime.trim() || Number.isNaN(parseDatetimeLocalAsMadrid(datetime).getTime())) {
      clearTimer = window.setTimeout(() => setQuotaHint(null), 0);
      return () => {
        window.clearTimeout(clearTimer);
        ac.abort();
      };
    }

    const startsAt = parseDatetimeLocalAsMadrid(datetime);
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        startsAt: startsAt.toISOString(),
        partySize: String(partySize),
      });
      void fetch(`/api/reservations/availability?${params}`, { signal: ac.signal })
        .then((res) => res.json())
        .then(
          (j: {
            ok?: boolean;
            message?: string;
            remaining?: number;
            quota?: number;
            webPercent?: number;
          }) => {
            if (!j.ok) {
              setQuotaHint(typeof j.message === "string" ? j.message : "Sin cupo web para esa hora o grupo.");
              return;
            }
            setQuotaHint(
              `Cupo web: quedan ${j.remaining} plazas (${j.quota} reservables online, ${j.webPercent}% del aforo total).`,
            );
          },
        )
        .catch(() => {
          if (!ac.signal.aborted) setQuotaHint(null);
        });
    }, 450);
    return () => {
      ac.abort();
      window.clearTimeout(timer);
    };
  }, [datetime, partySize]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setFeedback(null);
    setConfirmLinkUrl(null);
    const startsAt = parseDatetimeLocalAsMadrid(datetime);
    if (Number.isNaN(startsAt.getTime())) {
      setFeedback("Elige fecha y hora válidas.");
      setLoading(false);
      return;
    }
    const res = await fetch("/api/reservations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customerName: name,
        phone,
        customerEmail: email.trim() || undefined,
        partySize,
        startsAt: startsAt.toISOString(),
        notes: notes || undefined,
      }),
    });
    const raw = await res.json().catch(() => null);
    setLoading(false);
    if (!res.ok) {
      const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
      const serverMsg =
        typeof o.error === "string" ? o.error : typeof o.message === "string" ? o.message : null;
      setFeedback(
        serverMsg ??
          (res.status === 409
            ? "No hay cupo web para esa hora o el horario no está abierto online. Revisa la fecha y la hora, o llama al restaurante."
            : `No se pudo completar la reserva (${res.status}).`),
      );
      return;
    }
    const okBody = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
    const confirmUrl =
      typeof okBody.confirm_url === "string" && okBody.confirm_url.trim() ? okBody.confirm_url.trim() : null;

    if (okBody.email_sent === true) {
      setConfirmLinkUrl(null);
      setFeedback("Reserva registrada. Te hemos enviado un correo: abre el enlace para confirmarla.");
    } else if (confirmUrl) {
      setConfirmLinkUrl(confirmUrl);
      const extra =
        typeof okBody.email_error === "string" && okBody.email_error.trim()
          ? ` (${okBody.email_error.trim()})`
          : "";
      setFeedback(
        `Reserva registrada como pendiente.${extra} Usa el enlace de abajo para confirmarla ahora (útil si aún no hay SMTP).`,
      );
    } else if (typeof okBody.email_error === "string" && okBody.email_error) {
      setConfirmLinkUrl(null);
      setFeedback(`Reserva registrada. ${okBody.email_error}`);
    } else {
      setConfirmLinkUrl(null);
      setFeedback("Reserva enviada. Te contactaremos para confirmar.");
    }
    setName("");
    setPhone("");
    setEmail("");
    setNotes("");
  }

  const partyOptions = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

  const success =
    feedback &&
    (feedback.includes("registrada") ||
      feedback.includes("enviada") ||
      feedback.includes("contactaremos") ||
      feedback.includes("confirmar"));

  return (
    <section
      id="reserva"
      className="scroll-mt-24 border-t border-[#8f1d1d]/10 bg-[#ebe4d9] bg-restaurant-grain px-5 py-10 md:py-14"
    >
      <div className="mx-auto max-w-2xl">
        <div className="text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#8f1d1d]">Reservas</p>
          <h2
            id="reserva-heading"
            className="font-display mt-2 text-3xl font-semibold tracking-tight text-[#2d2420] md:text-4xl"
          >
            Te guardamos sitio
          </h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-[#5c4f47]">
            Elige día, hora y cuántos sois. Revisamos disponibilidad y te respondemos cuanto antes.
          </p>
        </div>

        <button
          type="button"
          id="reserva-toggle"
          aria-expanded={panelOpen}
          aria-controls="reserva-panel"
          onClick={() => setPanelOpen((o) => !o)}
          className="mt-8 flex w-full items-center justify-between gap-4 rounded-2xl border border-[#2d2420]/12 bg-[#f7f3ee] px-4 py-4 text-left shadow-sm ring-[#8f1d1d]/0 transition hover:border-[#8f1d1d]/25 hover:ring-2 hover:ring-[#8f1d1d]/10 sm:px-5 sm:py-4"
        >
          <span className="min-w-0">
            <span className="font-display text-lg font-semibold text-[#2d2420] sm:text-xl">
              {panelOpen ? "Ocultar formulario" : "Mostrar formulario de reserva"}
            </span>
            <span className="mt-0.5 block text-xs leading-snug text-[#5c4f47] sm:text-sm">
              {panelOpen
                ? "Puedes cerrar cuando hayas terminado; los datos no se borran."
                : "Despliega para rellenar nombre, contacto, fecha y comensales."}
            </span>
          </span>
          <Chevron open={panelOpen} />
        </button>

        <div
          id="reserva-panel"
          role="region"
          aria-labelledby="reserva-heading"
          hidden={!panelOpen}
          className="mt-4"
        >
          <div className="relative overflow-hidden rounded-3xl border border-[#2d2420]/10 bg-[#f7f3ee] shadow-[0_24px_48px_-24px_rgba(45,36,32,0.35)]">
          <div
            className="pointer-events-none absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-[#8f1d1d] via-[#b83232] to-[#6b1515]"
            aria-hidden
          />
          <form className="relative flex flex-col gap-0 px-5 py-8 sm:px-8 sm:py-10" onSubmit={submit}>
            <fieldset className="space-y-4 border-b border-[#2d2420]/8 pb-8">
              <legend className="font-display text-lg font-semibold text-[#2d2420]">1. Quiénes sois</legend>
              <p className="text-xs text-[#6b5a4e]">Así sabemos cómo dirigirnos a vosotros.</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-2 sm:col-span-2">
                  <span className={labelClass}>Nombre o reserva a nombre de</span>
                  <input
                    required
                    className={inputClass}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ej. María García"
                    autoComplete="name"
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <span className={labelClass}>Teléfono</span>
                  <input
                    required
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    className={`${inputClass} tabular-nums`}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+34 …"
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <span className={labelClass}>Correo (opcional)</span>
                  <input
                    type="email"
                    autoComplete="email"
                    className={inputClass}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Para confirmación por email"
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="space-y-4 border-b border-[#2d2420]/8 py-8">
              <legend className="font-display text-lg font-semibold text-[#2d2420]">2. Cuándo y mesa</legend>
              <div>
                <span className={labelClass}>Comensales</span>
                <p className="mt-2 text-xs text-[#6b5a4e]">
                  Toca el número; para 13–20 personas usa el desplegable inferior.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {partyOptions.map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setPartySize(n)}
                      className={`min-w-[2.75rem] rounded-xl border px-3 py-2.5 text-sm font-semibold tabular-nums transition ${
                        partySize === n
                          ? "border-[#8f1d1d] bg-[#8f1d1d] text-[#faf6ed] shadow-md shadow-[#4a0f0f]/25"
                          : "border-[#2d2420]/12 bg-white text-[#3d3532] hover:border-[#8f1d1d]/40 hover:bg-[#faf8f5]"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
                <label className="mt-4 flex max-w-full flex-col gap-2 sm:max-w-xs">
                  <span className={labelClass}>Grupo grande (13–20)</span>
                  <select
                    className={inputClass}
                    value={partySize > 12 ? String(partySize) : ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (!v) {
                        setPartySize((p) => (p > 12 ? 8 : p));
                        return;
                      }
                      setPartySize(Number(v));
                    }}
                  >
                    <option value="">—</option>
                    {Array.from({ length: 8 }, (_, i) => i + 13).map((n) => (
                      <option key={n} value={n}>
                        {n} comensales
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="flex flex-col gap-2">
                <span className={labelClass}>Fecha y hora</span>
                <input
                  required
                  type="datetime-local"
                  className={inputClass}
                  value={datetime}
                  onChange={(e) => setDatetime(e.target.value)}
                />
                <span className="text-xs text-[#6b5a4e]">Hora local (España / Valencia).</span>
              </label>
              {quotaHint && (
                <p className="rounded-xl border border-[#8f1d1d]/15 bg-[#fff9f5] px-4 py-3 text-sm leading-relaxed text-[#4a3f38]">
                  <span className="font-medium text-[#8f1d1d]">Disponibilidad · </span>
                  {quotaHint}
                </p>
              )}
            </fieldset>

            <fieldset className="space-y-4 pt-8">
              <legend className="font-display text-lg font-semibold text-[#2d2420]">3. Detalles</legend>
              <label className="flex flex-col gap-2">
                <span className={labelClass}>Notas (opcional)</span>
                <textarea
                  className={`${inputClass} min-h-[108px] resize-y`}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Cumpleaños, alergias, sillita infantil, preferencia de mesa…"
                />
              </label>
            </fieldset>

            <div className="mt-8 flex flex-col items-stretch gap-4 sm:items-center">
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[#8f1d1d] px-10 py-4 text-sm font-semibold text-[#faf6ed] shadow-lg shadow-[#4a0f0f]/30 transition hover:bg-[#7a1919] disabled:opacity-55"
              >
                {loading ? (
                  "Enviando…"
                ) : (
                  <>
                    Enviar solicitud
                    <span aria-hidden className="text-base leading-none">
                      →
                    </span>
                  </>
                )}
              </button>
              {feedback && (
                <p
                  className={`text-center text-sm leading-relaxed ${success ? "text-emerald-800" : "text-red-700"}`}
                  role="status"
                >
                  {feedback}
                </p>
              )}
              {confirmLinkUrl && (
                <div className="rounded-2xl border border-emerald-800/20 bg-emerald-50/90 px-4 py-4 text-center text-sm text-[#14532d] shadow-inner">
                  <p className="mb-2 font-medium">Enlace de confirmación (ábrelo en esta ventana o en privado)</p>
                  <a
                    href={confirmLinkUrl}
                    className="inline-block max-w-full break-all rounded-lg bg-white px-3 py-2 text-xs font-semibold text-[#8f1d1d] underline decoration-[#8f1d1d]/40 underline-offset-2 hover:bg-[#faf8f5]"
                  >
                    Confirmar reserva
                  </a>
                </div>
              )}
            </div>
          </form>
        </div>
        </div>
      </div>
    </section>
  );
}
