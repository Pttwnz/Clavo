"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { TabletKitchenStops } from "@/components/tablet/TabletKitchenStops";
import {
  tabletAmbient,
  tabletBtnGhost,
  tabletBtnPrimary,
  tabletCard,
  tabletHeader,
  tabletInput,
  tabletSessionPill,
  tabletShell,
} from "@/components/tablet/tablet-tokens";
import { gastroAccessHubUrl } from "@/lib/gastro-site";

type Employee = { id: string; name: string; role: string };
type SessionEmp = { id: string; name: string; role: string };

function roleLabel(role: string): string {
  if (role === "MANAGER") return "Encargado";
  if (role === "KITCHEN") return "Cocina";
  return "Personal";
}

export default function CocinaPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [pin, setPin] = useState("");
  const [session, setSession] = useState<SessionEmp | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);

  const kitchenStaff = employees.filter((e) => e.role === "KITCHEN" || e.role === "MANAGER");

  const refreshSession = useCallback(async () => {
    setSessionLoading(true);
    try {
      const res = await fetch("/api/tablet/session", { credentials: "include" });
      if (!res.ok) {
        setSession(null);
        return;
      }
      const data = (await res.json()) as { employee: SessionEmp };
      const emp = data.employee;
      if (emp.role !== "KITCHEN" && emp.role !== "MANAGER") {
        await fetch("/api/tablet/logout", { method: "POST", credentials: "include" });
        setSession(null);
        setLoginError("Esta sesión no tiene permiso de cocina. Cierra sesión en recepción e identifícate aquí.");
        return;
      }
      setSession(emp);
      setEmployeeId(emp.id);
    } catch {
      setSession(null);
    } finally {
      setSessionLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const res = await fetch("/api/employees");
      if (!res.ok || cancelled) return;
      const data = (await res.json()) as Employee[];
      setEmployees(data);
      setEmployeeId((prev) => {
        if (prev) return prev;
        const k = data.find((e) => e.role === "KITCHEN") ?? data.find((e) => e.role === "MANAGER");
        return k?.id ?? "";
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loginKitchen(e: React.FormEvent) {
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
    const emp = (data as { employee: SessionEmp }).employee;
    if (emp.role !== "KITCHEN" && emp.role !== "MANAGER") {
      await fetch("/api/tablet/logout", { method: "POST", credentials: "include" });
      setLoginError("Solo personal de cocina o encargado pueden entrar en este modo.");
      return;
    }
    setSession(emp);
    setPin("");
  }

  async function logoutKitchen() {
    await fetch("/api/tablet/logout", { method: "POST", credentials: "include" });
    setSession(null);
    setLoginError(null);
  }

  const handleSessionLost = useCallback(() => {
    setSession(null);
    setLoginError("Sesión caducada. Vuelve a identificarte.");
  }, []);

  if (sessionLoading) {
    return (
      <div className={`${tabletShell} flex items-center justify-center`}>
        <div className={tabletAmbient} aria-hidden />
        <div className="flex flex-col items-center gap-4 rounded-3xl border border-white/60 bg-white/90 px-12 py-14 shadow-xl">
          <span
            className="h-12 w-12 animate-spin rounded-full border-4 border-[#8f1d1d]/20 border-t-[#8f1d1d]"
            aria-hidden
          />
          <p className="text-lg font-medium text-[#5c4f47]">Cargando…</p>
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
              Cocina · paros
            </h1>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-white/55">
              Control de platos fuera de carta (QR y web). La recepción y el mapa de sala siguen en{" "}
              <strong className="font-semibold text-white/75">Recepción</strong>.
            </p>
          </div>
          <nav className="flex flex-shrink-0 flex-wrap items-center gap-2">
            <Link href="/recepcion" className={`${tabletBtnGhost} text-sm`}>
              Recepción / sala
            </Link>
            <Link href="/menu" className={`${tabletBtnGhost} text-sm`}>
              Ver carta web
            </Link>
            <a href={gastroAccessHubUrl("/panel")} className={`${tabletBtnGhost} text-sm`}>
              Panel Gastro
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-10">
        {!session ? (
          <section className={tabletCard}>
            <h2 className="font-display text-2xl font-semibold text-[#1a1614] md:text-3xl">Identificación cocina</h2>
            <p className="mt-2 text-lg leading-relaxed text-[#5c4f47]">
              Introduce el mismo PIN que en recepción. Solo aparecen empleados con rol{" "}
              <strong className="font-semibold">Cocina</strong> o <strong className="font-semibold">Encargado</strong>
              (el encargado puede cubrir paros si hace falta).
            </p>
            <form className="mt-8 space-y-6" onSubmit={(e) => void loginKitchen(e)}>
              <label className="flex flex-col gap-2">
                <span className="text-base font-semibold text-[#3d3532]">Empleado</span>
                <select
                  required
                  className={tabletInput}
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  disabled={kitchenStaff.length === 0}
                >
                  {kitchenStaff.length === 0 ? (
                    <option value="">No hay cocina en el listado</option>
                  ) : (
                    kitchenStaff.map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name} ({roleLabel(e.role)})
                      </option>
                    ))
                  )}
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
              {kitchenStaff.length === 0 && (
                <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-base text-amber-950">
                  En administración · Empleados, asigna el rol <strong>Cocina</strong> (o usa un encargado) para
                  habilitar este modo.
                </p>
              )}
              <button type="submit" disabled={loginBusy || kitchenStaff.length === 0} className={tabletBtnPrimary}>
                {loginBusy ? "Entrando…" : "Entrar"}
              </button>
            </form>
          </section>
        ) : (
          <>
            <div className={tabletSessionPill}>
              <p className="text-lg text-emerald-950">
                <span className="font-semibold">{session.name}</span>
                <span className="ml-2 text-base font-normal text-emerald-800/90">· {roleLabel(session.role)}</span>
              </p>
              <button
                type="button"
                className="min-h-[48px] rounded-2xl border border-emerald-300/60 bg-white px-5 text-base font-semibold text-emerald-900 shadow-sm transition hover:bg-emerald-50 active:scale-[0.99]"
                onClick={() => void logoutKitchen()}
              >
                Cerrar sesión
              </button>
            </div>

            <TabletKitchenStops onSessionLost={handleSessionLost} />
          </>
        )}
      </main>
    </div>
  );
}
