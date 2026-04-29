"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MenuCartaFolleto } from "@/components/menu/MenuCartaFolleto";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { localeLabels, locales, type Locale } from "@/lib/menu-i18n";
import type { MenuItem } from "@/lib/menu-types";
import { siteImages } from "@/lib/site-images";

function isLocale(s: string | null): s is Locale {
  return s !== null && (locales as readonly string[]).includes(s);
}

const ui: {
  qrHint: Record<Locale, string>;
  cartaFolletoHeading: Record<Locale, string>;
  heroNote: Record<Locale, string>;
  qrFullUrl: Record<Locale, string>;
  fullEnHtml: Record<Locale, string>;
} = {
  qrHint: {
    es: "Enlace corto para QR (misma carta):",
    en: "Short link for QR (same menu):",
    fr: "Lien court pour QR (même carte) :",
    de: "Kurzlink für QR (gleiche Karte):",
    ca: "Enllaç curt per a QR (mateixa carta):",
    it: "Link breve per QR (stesso menu):",
    pt: "Link curto para QR (mesmo menu):",
  },
  cartaFolletoHeading: {
    es: "Carta completa",
    en: "Full menu",
    fr: "Carte complète",
    de: "Vollständige Speisekarte",
    ca: "Carta completa",
    it: "Menu completo",
    pt: "Menu completo",
  },
  heroNote: {
    es: "Elige el idioma con los botones: la carta de abajo cambia al instante.",
    en: "Pick a language below — the menu updates immediately.",
    fr: "Choisissez la langue : la carte ci-dessous s’actualise tout de suite.",
    de: "Sprache wählen — die Karte darunter wechselt sofort.",
    ca: "Trieu l’idioma amb els botons: la carta de sota canvia a l’instant.",
    it: "Scegli la lingua con i pulsanti: il menu sotto si aggiorna subito.",
    pt: "Escolha o idioma nos botões: o menu abaixo muda na hora.",
  },
  qrFullUrl: {
    es: "En el QR usa la URL completa de tu dominio + esta ruta.",
    en: "For the QR code, use your full site URL + this path.",
    fr: "Pour le QR, utilisez l’URL complète de votre site + ce chemin.",
    de: "Im QR die vollständige Domain + diesen Pfad verwenden.",
    ca: "Al QR, useu l’URL completa del domini + aquest camí.",
    it: "Per il QR usate l’URL completo del dominio + questo percorso.",
    pt: "No QR use o URL completo do domínio + este caminho.",
  },
  fullEnHtml: {
    es: "Carta completa en inglés (HTML imprimible)",
    en: "Full English menu (printable HTML)",
    fr: "Menu complet en anglais (HTML imprimable)",
    de: "Vollständige Speisekarte auf Englisch (druckbares HTML)",
    ca: "Carta completa en anglès (HTML per imprimir)",
    it: "Menu completo in inglese (HTML stampabile)",
    pt: "Menu completo em inglês (HTML para imprimir)",
  },
};

export function MenuBody({ initialMenuItems }: { initialMenuItems: MenuItem[] }) {
  const searchParams = useSearchParams();
  const raw = searchParams.get("lang");
  const lang: Locale = isLocale(raw) ? raw : "es";

  const menuQuery = (l: Locale) => `/menu?lang=${l}`;

  return (
    <div className="flex min-h-full flex-col">
      <section className="relative min-h-[min(48vh,420px)]">
        <Image
          src={siteImages.barra}
          alt="Interior de Taberna El Clavo"
          fill
          priority
          className="object-cover object-[center_45%]"
          sizes="100vw"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#1a0f0f] via-[#2d1818]/65 to-[#3d2020]/35" />
        <SiteHeader theme="transparent" cartaHref={`/menu?lang=${lang}`} />
        <div className="relative z-10 mx-auto flex min-h-[min(48vh,420px)] max-w-6xl flex-col justify-end px-4 pb-10 pt-28 sm:px-5 sm:pb-12 sm:pt-32">
          <p className="text-xs font-medium uppercase tracking-[0.35em] text-[#e8c87a]">Taberna El Clavo</p>
          <h1 className="font-display mt-2 text-4xl font-semibold text-[#faf6ed] md:text-5xl">Carta</h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-white/80">{ui.heroNote[lang]}</p>
          <p className="mt-2 max-w-xl text-xs leading-relaxed text-white/70">
            {ui.qrHint[lang]}{" "}
            <Link href={`/carta/${lang}`} className="font-mono text-[#e8c87a] underline underline-offset-2">
              /carta/{lang}
            </Link>
            <span className="block text-[10px] text-white/55">{ui.qrFullUrl[lang]}</span>
          </p>
          <p className="mt-3 max-w-xl text-xs">
            <a
              href="/carta/el-clavo-menu-en.html"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-[#e8c87a] underline decoration-[#e8c87a]/40 underline-offset-2 hover:text-white"
            >
              {ui.fullEnHtml[lang]}
            </a>
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {locales.map((l) => (
              <Link
                key={l}
                href={menuQuery(l)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  l === lang
                    ? "bg-[#8f1d1d] text-[#faf6ed]"
                    : "border border-white/35 text-[#faf6ed] hover:bg-white/10"
                }`}
              >
                {localeLabels[l]}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <div className="flex flex-1 flex-col bg-[#ebe4d9]">
        <main className="mx-auto w-full max-w-[1200px] px-3 py-8 sm:px-5 sm:py-10 md:py-12">
          <section aria-labelledby="carta-folleto-h" className="mb-8 sm:mb-10 md:mb-12">
            <h2
              id="carta-folleto-h"
              className="mb-3 font-display border-b border-[#8f1d1d]/25 pb-2 text-xl font-semibold tracking-tight text-[#2d2420] sm:mb-4 sm:text-2xl md:text-3xl"
            >
              {ui.cartaFolletoHeading[lang]}
            </h2>
            <MenuCartaFolleto key={lang} locale={lang} menuItems={initialMenuItems} scanImages={[]} />
          </section>
        </main>
      </div>
      <SiteFooter />
    </div>
  );
}
