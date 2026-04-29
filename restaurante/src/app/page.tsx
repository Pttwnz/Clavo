"use client";

import Image from "next/image";
import Link from "next/link";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { HomeReservationSection } from "@/components/site/HomeReservationSection";
import { HomeStepsSection } from "@/components/site/HomeStepsSection";
import { VenueVisitSection } from "@/components/site/VenueVisitSection";
import { siteImages } from "@/lib/site-images";

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <section className="relative min-h-[min(92vh,900px)]">
        <Image
          src={siteImages.hero}
          alt="Barra de Taberna El Clavo: madera, lámparas y detalle del local"
          fill
          priority
          className="object-cover object-[center_38%]"
          sizes="100vw"
        />
        <div
          className="absolute inset-0 bg-gradient-to-t from-[#1a0f0f] via-[#2d1818]/72 to-[#3d2020]/40"
          aria-hidden
        />
        <div
          className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(143,29,29,0.18),transparent_55%)]"
          aria-hidden
        />
        <SiteHeader theme="transparent" />
        <div className="relative z-10 mx-auto flex min-h-[min(92vh,900px)] max-w-6xl flex-col justify-end px-5 pb-16 pt-36 md:pb-24 md:pt-40">
          <p className="text-xs font-medium uppercase tracking-[0.4em] text-[#e8c87a] md:text-sm">
            València · Poblats Marítims
          </p>
          <h1 className="font-display mt-4 max-w-3xl text-4xl font-semibold leading-[1.08] tracking-tight text-[#faf6ed] md:text-6xl lg:text-7xl">
            El clavo que sujeta el buen comer
          </h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#efe8df]/95 md:text-lg">
            Antigua ferretería convertida en taberna: madera, azulejo, pizarra y el rojo de siempre. Tapas de mercado y
            mesa para quedarse.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link
              href="/menu?lang=es"
              className="inline-flex items-center justify-center rounded-full bg-[#8f1d1d] px-8 py-3.5 text-sm font-semibold text-[#faf6ed] shadow-lg shadow-[#4a0f0f]/35 transition hover:bg-[#7a1919]"
            >
              Ver la carta
            </Link>
            <a
              href="#reserva"
              className="inline-flex items-center justify-center rounded-full border border-[#faf6ed]/50 px-8 py-3.5 text-sm font-semibold text-[#faf6ed] transition hover:bg-white/10"
            >
              Reservar mesa
            </a>
            <a
              href="#como-llegar"
              className="inline-flex items-center justify-center rounded-full border border-[#e8c87a]/50 px-8 py-3.5 text-sm font-semibold text-[#e8c87a] transition hover:bg-[#e8c87a]/10"
            >
              Cómo llegar
            </a>
          </div>
        </div>
      </section>

      <main className="flex-1">
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 md:grid-cols-2 md:gap-16 md:py-24">
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl shadow-xl shadow-[#2d2420]/20 ring-1 ring-[#8f1d1d]/15">
            <Image
              src={siteImages.barra}
              alt="Interior de Taberna El Clavo: sala, madera y cartel"
              fill
              className="object-cover object-center"
              sizes="(max-width: 768px) 100vw, 50vw"
            />
          </div>
          <div>
            <h2 className="font-display text-3xl font-semibold text-[#2d2420] md:text-4xl">Oficio y convite</h2>
            <p className="mt-4 text-sm leading-relaxed text-[#4a3f38] md:text-base">
              El local conserva el alma de la ferretería — letras de herramientas en la estantería, madera noble y esa
              luz roja que abriga la barra. Aquí el tapeo es de verdad, sin prisas.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-[#3d3532]">
              <li className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#8f1d1d]" />
                Raciones generosas y producto de temporada.
              </li>
              <li className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#8f1d1d]" />
                Carta multilingüe por QR.
              </li>
              <li className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#8f1d1d]" />
                Reserva online; confirmamos por teléfono.
              </li>
            </ul>
          </div>
        </section>

        <VenueVisitSection />

        <HomeStepsSection />

        <HomeReservationSection />
      </main>
      <SiteFooter />
    </div>
  );
}
