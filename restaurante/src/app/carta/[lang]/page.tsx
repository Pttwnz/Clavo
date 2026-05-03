import Link from "next/link";
import { redirect } from "next/navigation";
import type { Metadata } from "next";
import { MenuCartaFolleto } from "@/components/menu/MenuCartaFolleto";
import { getMenuItemsForPublicDisplay } from "@/lib/menu-items-resolved";
import { localeLabels, locales, type Locale } from "@/lib/menu-types";

function isLocale(s: string): s is Locale {
  return (locales as readonly string[]).includes(s);
}

const titles: Record<Locale, string> = {
  es: "Carta · Taberna El Clavo",
  en: "Menu · Taberna El Clavo",
  fr: "Carte · Taberna El Clavo",
  de: "Speisekarte · Taberna El Clavo",
  ca: "Carta · Taberna El Clavo",
  it: "Menù · Taberna El Clavo",
  pt: "Menu · Taberna El Clavo",
};

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang: raw } = await params;
  const lang = isLocale(raw) ? raw : "es";
  return {
    title: titles[lang],
    description: "Carta en texto. Reservas 963 287 041.",
  };
}

export default async function CartaLangPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: raw } = await params;
  if (!isLocale(raw)) redirect("/carta/es");

  const lang = raw;
  const menuItems = await getMenuItemsForPublicDisplay();

  return (
    <div className="min-h-full bg-[#ebe4d9] pb-10">
      <header className="sticky top-0 z-20 border-b border-[#2d2420]/10 bg-[#f5f0e8]/95 px-4 py-3 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.25em] text-[#8f1d1d]">El Clavo</p>
            <h1 className="font-display text-lg font-semibold text-[#2d2420]">{titles[lang].split("·")[0].trim()}</h1>
          </div>
          <nav className="flex max-w-full flex-wrap justify-end gap-1 sm:gap-1.5">
            {locales.map((l) => (
              <Link
                key={l}
                href={`/carta/${l}`}
                className={`rounded-full px-2 py-1 text-[10px] font-medium transition sm:px-3 sm:py-1.5 sm:text-xs ${
                  l === lang ? "bg-[#8f1d1d] text-[#faf6ed]" : "border border-[#2d2420]/15 text-[#2d2420] hover:bg-[#2d2420]/5"
                }`}
              >
                {localeLabels[l]}
              </Link>
            ))}
          </nav>
        </div>
        <p className="mx-auto mt-2 max-w-3xl px-1 text-center text-xs text-[#5c4f47]">
          <Link href="/" className="underline decoration-[#8f1d1d]/40 underline-offset-2 hover:text-[#8f1d1d]">
            Web
          </Link>
          {" · "}
          <Link href={`/menu?lang=${lang}`} className="underline decoration-[#8f1d1d]/40 underline-offset-2 hover:text-[#8f1d1d]">
            Carta web
          </Link>
          {" · "}
          <span className="tabular-nums">963 287 041</span>
        </p>
      </header>

      <main className="mx-auto mt-4 max-w-[1200px] px-3 pb-4 sm:mt-6 sm:px-4">
        <MenuCartaFolleto key={lang} locale={lang} menuItems={menuItems} scanImages={[]} />
      </main>
    </div>
  );
}
