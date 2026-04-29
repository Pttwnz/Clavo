"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";

const DEDupe_MS = 4000;

function shouldRecordPathname(pathname: string): boolean {
  if (!pathname.startsWith("/")) return false;
  if (pathname.startsWith("/admin")) return false;
  if (pathname.startsWith("/ingreso")) return false;
  if (pathname.startsWith("/api")) return false;
  if (pathname.startsWith("/_next")) return false;
  return true;
}

/**
 * Registra una vista por navegación (deduplicación breve en `sessionStorage`).
 * Debe ir dentro de `<Suspense>` por `useSearchParams`.
 */
export function VisitRecorder() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  /** Primitivo estable: el objeto `searchParams` suele cambiar de referencia en cada render y re-dispararía el efecto. */
  const searchString = searchParams?.toString() ?? "";

  useEffect(() => {
    if (!shouldRecordPathname(pathname)) return;
    const path = `${pathname}${searchString ? `?${searchString}` : ""}`.slice(0, 1024);
    const dedupeKey = `clavo_pv:${path}`;
    const now = Date.now();
    try {
      const prev = sessionStorage.getItem(dedupeKey);
      if (prev) {
        const t = parseInt(prev, 10);
        if (Number.isFinite(t) && now - t < DEDupe_MS) return;
      }
      sessionStorage.setItem(dedupeKey, String(now));
    } catch {
      /* modo privado u otro bloqueo */
    }

    void fetch("/api/public/page-view", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
      keepalive: true,
    }).catch(() => {});
  }, [pathname, searchString]);

  return null;
}
