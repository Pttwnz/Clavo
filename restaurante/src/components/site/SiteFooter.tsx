import Link from "next/link";
import { OpeningHoursBlock } from "@/components/site/OpeningHoursBlock";
import { gastroAccessHubUrl } from "@/lib/gastro-site";
import { VENUE } from "@/lib/venue";

export function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-[#8f1d1d]/25 bg-[#14100e] text-[#e8ddd4]">
      <div className="mx-auto max-w-6xl px-5 py-12 md:py-16">
        <div className="grid gap-12 md:grid-cols-2 md:gap-x-10 md:gap-y-12 lg:grid-cols-12 lg:gap-10">
          <div className="lg:col-span-4">
            <p className="font-display text-2xl font-semibold tracking-tight text-[#f7f0e8] md:text-[1.65rem]">
              {VENUE.name}
            </p>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-[#b8a99c]">
              Antigua ferretería, taberna de hoy. Mercado, barra y mesa en el barrio marítimo.
            </p>
          </div>

          <div className="lg:col-span-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#8f7364]">Dónde y contacto</p>
            <address className="mt-4 space-y-1.5 text-sm not-italic leading-relaxed text-[#d4c8bc]">
              <p className="text-[#f0e8e0]">{VENUE.streetLine}</p>
              <p>
                {VENUE.postalCity}
                <br />
                <span className="text-[#a89888]">{VENUE.area}</span>
              </p>
              <p className="pt-2">
                <a href={`tel:${VENUE.phoneTel}`} className="font-medium text-[#e8c87a] hover:underline">
                  {VENUE.phoneDisplay}
                </a>
              </p>
            </address>
            <div className="mt-5 flex flex-wrap gap-x-4 gap-y-2 text-sm">
              <a
                href={VENUE.googleMapsPlaceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[#e8ddd4] transition hover:border-[#e8c87a]/40 hover:bg-white/10 hover:text-[#f7f0e8]"
              >
                Ver en mapa
              </a>
              <a
                href={VENUE.googleDirectionsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[#e8ddd4] transition hover:border-[#e8c87a]/40 hover:bg-white/10 hover:text-[#f7f0e8]"
              >
                Cómo llegar
              </a>
            </div>
          </div>

          <div className="lg:col-span-3">
            <OpeningHoursBlock compact variant="dark" />
          </div>

          <nav className="lg:col-span-2" aria-label="Enlaces del pie">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#8f7364]">Enlaces</p>
            <ul className="mt-4 space-y-2.5 text-sm">
              <li>
                <Link href="/menu?lang=es" className="text-[#d4c8bc] transition hover:text-[#e8c87a]">
                  Carta
                </Link>
              </li>
              <li>
                <Link href="/#reserva" className="text-[#d4c8bc] transition hover:text-[#e8c87a]">
                  Reservar
                </Link>
              </li>
              <li>
                <Link href="/#como-llegar" className="text-[#d4c8bc] transition hover:text-[#e8c87a]">
                  Visítanos
                </Link>
              </li>
              <li>
                <a
                  href={gastroAccessHubUrl("/panel")}
                  className="text-[#9a8a7c] transition hover:text-[#c4b5a8]"
                >
                  Acceso personal
                </a>
              </li>
            </ul>
          </nav>
        </div>

        <div className="mt-12 border-t border-white/10 pt-8">
          <div className="flex flex-col items-center justify-between gap-4 text-center sm:flex-row sm:text-left">
            <p className="max-w-2xl text-[11px] leading-relaxed text-[#6e6058]">
              {VENUE.footerLine}
              <span className="mx-2 text-[#4a4038]">·</span>
              Franja de miniaturas en la home: fotos genéricas (Unsplash); hero y carta usan imágenes del local.
            </p>
            <p className="shrink-0 text-[11px] text-[#5c5048]">© {year} Taberna El Clavo</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
