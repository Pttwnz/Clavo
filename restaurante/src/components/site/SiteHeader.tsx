"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Theme = "cream" | "transparent";

export function SiteHeader({ theme = "cream", cartaHref }: { theme?: Theme; cartaHref?: string }) {
  const pathname = usePathname();
  const onImage = theme === "transparent";
  const menuHref = cartaHref ?? "/menu?lang=es";

  const nav = [
    { href: "/", label: "Inicio" },
    { href: menuHref, label: "Carta" },
    { href: "/#como-llegar", label: "Cómo llegar" },
    { href: "/#reserva", label: "Reservar" },
  ] as const;

  return (
    <header
      className={
        onImage
          ? "absolute inset-x-0 top-0 z-50 border-b border-white/10 bg-gradient-to-b from-black/55 via-black/30 to-transparent backdrop-blur-[2px]"
          : "sticky top-0 z-50 border-b border-[#8f1d1d]/10 bg-[#f5f0e8]/93 backdrop-blur-md"
      }
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-5 py-4 md:py-5">
        <Link
          href="/"
          className={`font-display text-xl font-semibold tracking-tight md:text-2xl ${
            onImage ? "text-[#faf6ed] drop-shadow-md" : "text-[#2d2420]"
          }`}
        >
          <span className="block text-[0.65rem] font-normal uppercase tracking-[0.35em] opacity-90 md:text-xs">
            Taberna
          </span>
          El Clavo
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2">
          {nav.map(({ href, label }) => {
            const active =
              href === "/"
                ? pathname === "/"
                : href.startsWith("/menu")
                  ? pathname === "/menu"
                  : false;
            return (
              <Link
                key={href}
                href={href}
                className={`rounded-full px-3 py-2 text-sm font-medium transition sm:px-4 ${
                  onImage
                    ? active
                      ? "bg-[#8f1d1d] text-[#faf6ed] shadow-md shadow-black/20"
                      : "text-white/95 hover:bg-white/15"
                    : active
                      ? "bg-[#8f1d1d] text-[#faf6ed]"
                      : "text-[#4a3f38] hover:bg-[#8f1d1d]/10 hover:text-[#8f1d1d]"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
