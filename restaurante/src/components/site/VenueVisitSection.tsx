import Link from "next/link";
import { OpeningHoursBlock } from "@/components/site/OpeningHoursBlock";
import { VENUE } from "@/lib/venue";

export function VenueVisitSection() {
  return (
    <section
      id="como-llegar"
      className="scroll-mt-24 border-y border-[#8f1d1d]/10 bg-[#f5f0e8] px-5 py-16 md:py-24"
      aria-labelledby="como-llegar-title"
    >
      <div className="mx-auto max-w-6xl">
        <h2
          id="como-llegar-title"
          className="font-display text-center text-3xl font-semibold text-[#2d2420] md:text-4xl"
        >
          Cómo llegar
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-sm leading-relaxed text-[#5c4f47] md:text-base">
          Estamos en el <strong>Grau</strong>, junto a la Marina y el paseo marítimo. En transporte público, líneas
          hacia la <strong>zona marítima</strong> (Marina / Neptú según procedas); en coche, zona ORA y parkings de la
          Marina cercanos. Reseñas y avisos puntuales: ficha del local en Google Maps.
        </p>
        <div className="mt-10 grid gap-10 lg:grid-cols-2 lg:items-start">
          <div className="space-y-4 rounded-2xl border border-[#2d2420]/10 bg-white/90 p-6 shadow-sm md:p-8">
            <p className="font-display text-lg font-semibold text-[#2d2420]">{VENUE.name}</p>
            <address className="not-italic text-sm leading-relaxed text-[#4a3f38] md:text-base">
              {VENUE.streetLine}
              <br />
              {VENUE.postalCity}
              <br />
              <span className="text-[#6b5d55]">{VENUE.area}</span>
            </address>
            <p>
              <a href={`tel:${VENUE.phoneTel}`} className="text-[#8f1d1d] font-medium hover:underline">
                {VENUE.phoneDisplay}
              </a>
            </p>
            <div className="rounded-xl border border-[#8f1d1d]/15 bg-[#faf7f2] px-4 py-3">
              <OpeningHoursBlock />
            </div>
            <div className="flex flex-wrap gap-3 pt-2">
              <a
                href={VENUE.googleMapsPlaceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center rounded-full bg-[#8f1d1d] px-5 py-2.5 text-sm font-semibold text-[#faf6ed] shadow-sm transition hover:bg-[#7a1919]"
              >
                Abrir en Google Maps
              </a>
              <a
                href={VENUE.googleDirectionsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center rounded-full border border-[#2d2420]/20 bg-white px-5 py-2.5 text-sm font-semibold text-[#2d2420] transition hover:bg-[#f5f0e8]"
              >
                Indicaciones desde aquí
              </a>
              <Link
                href="/menu?lang=es"
                className="inline-flex items-center justify-center rounded-full border border-[#8f1d1d]/35 px-5 py-2.5 text-sm font-semibold text-[#8f1d1d] transition hover:bg-[#8f1d1d]/10"
              >
                Carta en línea
              </Link>
            </div>
          </div>
          <div className="overflow-hidden rounded-2xl border border-[#2d2420]/10 shadow-lg ring-1 ring-black/5">
            <iframe
              title="Mapa: Taberna El Clavo, València"
              src={VENUE.googleEmbedMapUrl}
              className="aspect-[4/3] min-h-[280px] w-full border-0 lg:aspect-auto lg:min-h-[360px]"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              allowFullScreen
            />
          </div>
        </div>
      </div>
    </section>
  );
}
