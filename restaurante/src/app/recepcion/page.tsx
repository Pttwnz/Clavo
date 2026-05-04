"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { SignaturePad, type SignaturePadHandle } from "@/components/SignaturePad";
import { LiveReservationTable } from "@/components/reservations/LiveReservationTable";
import { TabletWalkInReservation } from "@/components/tablet/TabletWalkInReservation";
import {
  tabletAmbient,
  tabletBtnGhost,
  tabletBtnPrimary,
  tabletCard,
  tabletHeader,
  tabletInput,
  tabletSessionPill,
  tabletShell,
  tabletTabGrid,
  tabletTabTile,
  tabletTabHint,
  tabletTabTitle,
} from "@/components/tablet/tablet-tokens";
import { gastroAccessHubUrl } from "@/lib/gastro-site";

type Employee = { id: string; name: string; role: string };
type SessionEmp = { id: string; name: string; role: string };
type Tab = "reservas" | "telefono" | "fichaje" | "documentos";

const TABS: { id: Tab; title: string; hint: string }[] = [
  { id: "reservas", title: "Reservas", hint: "Mapa y lista en vivo" },
  { id: "telefono", title: "Alta manual", hint: "Teléfono o mostrador" },
  { id: "fichaje", title: "Fichaje", hint: "Entrada y salida" },
  { id: "documentos", title: "Documentos", hint: "Firma y PDF" },
];

export default function RecepcionPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [pin, setPin] = useState("");
  const [session, setSession] = useState<SessionEmp | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("reservas");
  const [msg, setMsg] = useState<string | null>(null);
  const [docTitle, setDocTitle] = useState("Recepción del reglamento interno");
  const sigRef = useRef<SignaturePadHandle>(null);

  const refreshSession = useCallback(async () => {
    setSessionLoading(true);
    try {
      const res = await fetch("/api/tablet/session", { credentials: "include" });
      if (!res.ok) {
        setSession(null);
        return;
      }
      const data = (await res.json()) as { employee: SessionEmp };
      setSession(data.employee);
      setEmployeeId(data.employee.id);
    } catch {
      setSession(null);
    } finally {
      setSessionLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void refreshSession();
    });
  }, [refreshSession]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const res = await fetch("/api/employees");
      if (!res.ok || cancelled) return;
      const data = (await res.json()) as Employee[];
      setEmployees(data);
      setEmployeeId((prev) => prev || data[0]?.id || "");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loginTablet(e: React.FormEvent) {
    e.preventDefault();
    setLoginError(null);
    setLoginBusy(true);
    const res = await fetch("/api/tablet/auth", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employeeId, pin }),
    });
    const data = await res.json().catch(() => ({}));
    setLoginBusy(false);
    if (!res.ok) {
      setLoginError(typeof data.error === "string" ? data.error : "No se pudo iniciar sesión");
      return;
    }
    setSession((data as { employee: SessionEmp }).employee);
    setPin("");
    setTab("reservas");
    setMsg(null);
  }

  async function logoutTablet() {
    await fetch("/api/tablet/logout", { method: "POST", credentials: "include" });
    setSession(null);
    setMsg(null);
    setTab("reservas");
  }

  const handleSessionLost = useCallback(() => {
    setSession(null);
    setMsg("Sesión tablet caducada o inválida. Vuelve a identificarte.");
  }, []);

  async function clock(action: "in" | "out") {
    if (!session) return;
    setMsg(null);
    const res = await fetch("/api/clock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ employeeId: session.id, pin: "", action }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setMsg(typeof data.error === "string" ? data.error : "Error");
      return;
    }
    setMsg(action === "in" ? "Entrada registrada." : "Salida registrada.");
  }

  async function signAndDownload() {
    if (!session) return;
    setMsg(null);
    const signaturePngB64 = sigRef.current?.getPngDataUrl();
    if (!signaturePngB64) {
      setMsg("Dibuja la firma primero.");
      return;
    }
    const res = await fetch("/api/documents/sign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        employeeId: session.id,
        pin: "",
        title: docTitle,
        documentKind: "ACK",
        signaturePngB64,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setMsg(typeof data.error === "string" ? data.error : "Error al firmar");
      return;
    }
    const b64 = data.pdfBase64 as string | undefined;
    const filename = (data.filename as string) ?? "documento.pdf";
    if (!b64) {
      setMsg("Respuesta sin PDF.");
      return;
    }
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    setMsg(`PDF descargado. Huella SHA-256: ${(data.sha256 as string)?.slice(0, 12)}…`);
  }

  if (sessionLoading) {
    return (
      <div className={`${tabletShell} flex items-center justify-center`}>
        <div className={tabletAmbient} aria-hidden />
        <div className="flex flex-col items-center gap-4 rounded-3xl border border-white/60 bg-white/90 px-12 py-14 shadow-xl">
          <span
            className="h-12 w-12 animate-spin rounded-full border-4 border-[#8f1d1d]/20 border-t-[#8f1d1d]"
            aria-hidden
          />
          <p className="text-lg font-medium text-[#5c4f47]">Preparando recepción…</p>
        </div>
      </div>
    );
  }

  return (
    <div className={tabletShell}>
      <div className={tabletAmbient} aria-hidden />

      <header className={tabletHeader}>
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4 md:px-8 md:py-5">
          <div className="min-w-0">
            <p className="text-[0.65rem] font-semibold uppercase tracking-[0.42em] text-[#c9a54a]/90">
              Taberna El Clavo
            </p>
            <h1 className="font-display mt-1 text-2xl font-semibold tracking-tight text-white md:text-3xl">
              Recepción
            </h1>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-white/55">
              Reservas, altas y fichaje con gestos táctiles amplios.
            </p>
          </div>
          <nav className="flex flex-shrink-0 flex-wrap items-center gap-2">
            <Link href="/" className={`${tabletBtnGhost} text-sm`}>
              Web
            </Link>
            <a href={gastroAccessHubUrl("/panel")} className={`${tabletBtnGhost} text-sm`}>
              Acceso panel
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-10">
        {!session ? (
          <section className={tabletCard}>
            <h2 className="font-display text-2xl font-semibold text-[#1a1614] md:text-3xl">Identificación</h2>
            <p className="mt-2 text-lg leading-relaxed text-[#5c4f47]">
              Elige empleado e introduce el PIN. La sesión queda activa en este dispositivo para fichar y gestionar
              reservas sin repetir el PIN en cada paso.
            </p>
            <form className="mt-8 space-y-6" onSubmit={loginTablet}>
              <label className="flex flex-col gap-2">
                <span className="text-base font-semibold text-[#3d3532]">Empleado</span>
                <select
                  required
                  className={tabletInput}
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                >
                  {employees.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name} ({e.role === "MANAGER" ? "Encargado" : "Personal"})
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-2">
                <span className="text-base font-semibold text-[#3d3532]">PIN</span>
                <input
                  required
                  type="password"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  className={`${tabletInput} tracking-[0.35em]`}
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="••••"
                />
              </label>
              {loginError && (
                <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-base text-red-900" role="alert">
                  {loginError}
                </p>
              )}
              <button type="submit" disabled={loginBusy} className={tabletBtnPrimary}>
                {loginBusy ? "Entrando…" : "Entrar"}
              </button>
            </form>
          </section>
        ) : (
          <>
            <div className={tabletSessionPill}>
              <p className="text-lg text-emerald-950">
                <span className="font-semibold">{session.name}</span>
                <span className="ml-2 text-base font-normal text-emerald-800/90">
                  · {session.role === "MANAGER" ? "Encargado" : "Personal"}
                </span>
              </p>
              <button
                type="button"
                className="min-h-[48px] rounded-2xl border border-emerald-300/60 bg-white px-5 text-base font-semibold text-emerald-900 shadow-sm transition hover:bg-emerald-50 active:scale-[0.99]"
                onClick={() => void logoutTablet()}
              >
                Cerrar sesión
              </button>
            </div>

            <nav className={`${tabletTabGrid} mb-8 mt-8`} aria-label="Secciones recepción">
              {TABS.map((t) => {
                const active = tab === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={tabletTabTile(active)}
                  >
                    <span className={active ? "text-white/80" : tabletTabHint}>{t.hint}</span>
                    <span className={active ? "text-xl font-bold text-white" : tabletTabTitle}>{t.title}</span>
                  </button>
                );
              })}
            </nav>

            {tab === "reservas" && (
              <LiveReservationTable onTabletSessionLost={handleSessionLost} />
            )}
            {tab === "telefono" && (
              <TabletWalkInReservation
                onSessionLost={handleSessionLost}
                onCreated={(summary) => setMsg(summary)}
              />
            )}
            {tab === "fichaje" && (
              <section className={tabletCard}>
                <h2 className="font-display text-2xl font-semibold text-[#1a1614]">Fichaje</h2>
                <p className="mt-2 text-lg text-[#5c4f47]">Registra entrada o salida con un toque.</p>
                <div className="mt-8 grid gap-4 sm:grid-cols-2">
                  <button
                    type="button"
                    className="flex min-h-[100px] flex-col items-center justify-center rounded-3xl bg-gradient-to-b from-emerald-600 to-emerald-700 px-6 py-8 text-2xl font-bold text-white shadow-xl shadow-emerald-900/25 transition active:scale-[0.99] hover:from-emerald-500 hover:to-emerald-600"
                    onClick={() => void clock("in")}
                  >
                    Entrada
                  </button>
                  <button
                    type="button"
                    className="flex min-h-[100px] flex-col items-center justify-center rounded-3xl bg-gradient-to-b from-zinc-700 to-zinc-900 px-6 py-8 text-2xl font-bold text-white shadow-xl shadow-black/20 transition active:scale-[0.99] hover:from-zinc-600 hover:to-zinc-800"
                    onClick={() => void clock("out")}
                  >
                    Salida
                  </button>
                </div>
              </section>
            )}
            {tab === "documentos" && (
              <section className={tabletCard}>
                <h2 className="font-display text-2xl font-semibold text-[#1a1614]">Documento con firma</h2>
                <label className="mt-6 flex flex-col gap-2">
                  <span className="text-base font-semibold text-[#3d3532]">Título del documento</span>
                  <input className={tabletInput} value={docTitle} onChange={(e) => setDocTitle(e.target.value)} />
                </label>
                <div className="mt-6">
                  <p className="mb-3 text-base font-semibold text-[#3d3532]">Firma en pantalla</p>
                  <div className="overflow-hidden rounded-2xl border-2 border-[#2c1810]/[0.08] bg-white shadow-inner">
                    <SignaturePad ref={sigRef} height={220} />
                  </div>
                </div>
                <button
                  type="button"
                  className={`${tabletBtnPrimary} mt-8`}
                  onClick={() => void signAndDownload()}
                >
                  Generar y descargar PDF
                </button>
              </section>
            )}

            {msg && (
              <p
                className="mt-8 rounded-2xl border border-[#c9a54a]/25 bg-[#fdf8ee] px-5 py-4 text-center text-lg font-medium text-[#3d3532] shadow-md"
                role="status"
              >
                {msg}
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
