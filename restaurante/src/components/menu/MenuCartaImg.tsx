"use client";

import { useState } from "react";

function CartaMissing({ alt }: { alt: string }) {
  return (
    <div
      role="img"
      aria-label={alt}
      className="flex min-h-[280px] flex-col items-center justify-center gap-3 bg-[#ebe4d9] px-6 py-10 text-center text-sm text-[#5c4f47]"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 24 24" fill="none" className="text-[#8f7364]">
        <path
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.5"
          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14M6 20h12a2 2 0 002-2V8a2 2 0 00-2-2h-3.34a2 2 0 01-1.664-.89l-.812-1.22A2 2 0 0010.07 4H6a2 2 0 00-2 2v12a2 2 0 002 2z"
        />
      </svg>
      <p className="max-w-md font-medium text-[#2d2420]">No se ha podido cargar esta página de la carta.</p>
      <p className="max-w-md text-xs leading-relaxed text-[#6b5348]">
        En el servidor, coloca los archivos en{" "}
        <code className="rounded bg-[#f5f0e8] px-1 font-mono text-[11px]">public/taberna/menu/es/</code> como{" "}
        <code className="rounded bg-[#f5f0e8] px-1 font-mono text-[11px]">carta-1.webp</code> y{" "}
        <code className="rounded bg-[#f5f0e8] px-1 font-mono text-[11px]">carta-2.webp</code> (o .png / .jpg), haz{" "}
        <code className="rounded bg-[#f5f0e8] px-1 font-mono text-[11px]">docker compose build web</code> y vuelve a
        subir. Diagnóstico:{" "}
        <a href="/api/menu-carta/health" className="font-medium text-[#8f1d1d] underline underline-offset-2">
          /api/menu-carta/health
        </a>
      </p>
    </div>
  );
}

/**
 * Carta escaneada vía URL (p. ej. `/api/menu-carta/file?...`). Si falla la carga, muestra ayuda en pantalla.
 */
export function MenuCartaImg({ src, alt, priority }: { src: string; alt: string; priority?: boolean }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return <CartaMissing alt={alt} />;
  }

  return (
    <img
      src={src}
      alt={alt}
      className="h-auto w-full max-w-full object-contain align-top"
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      {...(priority ? { fetchPriority: "high" as const } : {})}
      onError={() => setFailed(true)}
    />
  );
}
