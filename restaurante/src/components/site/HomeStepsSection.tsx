import Image from "next/image";
import Link from "next/link";
import { homeGalleryStrip } from "@/lib/site-images";

type Card =
  | { title: string; text: string }
  | { title: string; text: string; href: string; linkLabel: string };

const cards: Card[] = [
  { title: "Del mercado", text: "Lo que el día trae: temporada, sabor y criterio en cocina." },
  {
    title: "Carta con QR",
    text: "Español, inglés, francés o alemán — tú eliges.",
    href: "/menu?lang=es",
    linkLabel: "Ver carta",
  },
  {
    title: "Tu mesa",
    text: "Reserva aquí; te llamamos para cerrar detalles.",
    href: "#reserva",
    linkLabel: "Reservar",
  },
];

const THUMB_W = 280;
const THUMB_H = 180;

export function HomeStepsSection() {
  return (
    <section
      className="border-y border-[#8f1d1d]/10 bg-[#ebe4d9] bg-restaurant-grain py-12 md:py-16"
      aria-label="Galería y servicios"
    >
      <div className="mx-auto max-w-6xl px-5">
        <div className="flex min-h-0 gap-3 overflow-x-auto overflow-y-visible pb-2 pt-1 [scrollbar-width:thin] md:justify-center md:gap-4">
          {homeGalleryStrip.map((item) => (
            <div
              key={item.src}
              className="relative h-[5.25rem] w-[8.25rem] shrink-0 overflow-hidden rounded-xl shadow-md ring-1 ring-[#2d2420]/10 sm:h-24 sm:w-36 md:h-28 md:w-44"
            >
              <Image
                src={item.src}
                alt={item.alt}
                width={THUMB_W}
                height={THUMB_H}
                sizes="(max-width: 768px) 33vw, 180px"
                className="h-full w-full object-cover"
              />
            </div>
          ))}
        </div>

        <div className="mx-auto mt-10 grid max-w-6xl gap-6 md:grid-cols-3 md:gap-8">
          {cards.map((b) => (
            <div
              key={b.title}
              className="rounded-2xl border border-[#2d2420]/8 bg-[#f5f0e8]/95 p-6 shadow-sm md:p-8"
            >
              <h3 className="font-display text-xl font-semibold text-[#2d2420]">{b.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-[#5c4f47]">{b.text}</p>
              {"href" in b ? (
                <p className="mt-4">
                  {b.href.startsWith("#") ? (
                    <a
                      href={b.href}
                      className="text-sm font-semibold text-[#8f1d1d] underline-offset-2 hover:underline"
                    >
                      {b.linkLabel} →
                    </a>
                  ) : (
                    <Link
                      href={b.href}
                      className="text-sm font-semibold text-[#8f1d1d] underline-offset-2 hover:underline"
                    >
                      {b.linkLabel} →
                    </Link>
                  )}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
