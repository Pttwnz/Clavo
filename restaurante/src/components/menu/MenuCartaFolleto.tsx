import type { ReactNode } from "react";
import type { MenuItem, Locale } from "@/lib/menu-types";
import { MenuCartaImg } from "@/components/menu/MenuCartaImg";
import {
  allergenCodesFromSpanish,
  dishDesc,
  dishName,
  itemsByCategoryEs,
  LEGEND,
  legendLabel,
  priceLine,
  splitTapasColumns,
} from "@/components/menu/menu-carta-folleto-utils";
import styles from "./MenuCartaFolleto.module.css";

const ICON_CLASS: Record<number, string> = {
  1: styles.n1,
  2: styles.n2,
  3: styles.n3,
  4: styles.n4,
  5: styles.n5,
  6: styles.n6,
  7: styles.n7,
  8: styles.n8,
  9: styles.n9,
  10: styles.n10,
  11: styles.n11,
  12: styles.n12,
  13: styles.n13,
  14: styles.n14,
};

const UI: {
  scanIntro: Record<Locale, string>;
  legendTitle: Record<Locale, string>;
  footCarnes: Record<Locale, string>;
  disclaimer: Record<Locale, string>;
} = {
  scanIntro: {
    es: "Carta escaneada (mismo folleto del local). Debajo, texto por idiomas con alérgenos.",
    en: "Scanned menu (same as in the venue). Below: text by language with allergens.",
    fr: "Carte scannée (identique sur place). Ci-dessous : texte multilingue et allergènes.",
    de: "Gescannte Karte (wie vor Ort). Darunter: mehrsprachiger Text mit Allergenen.",
    ca: "Carta escanejada (mateix fulletó del local). A sota, text en diversos idiomes amb al·lèrgens.",
    it: "Menu scansionato (come in locale). Sotto: testo multilingue con allergeni.",
    pt: "Menu digitalizado (igual ao do local). Abaixo: texto em várias línguas com alérgenos.",
  },
  legendTitle: {
    es: "Leyenda de alérgenos",
    en: "Allergen key",
    fr: "Légende des allergènes",
    de: "Allergen-Legende",
    ca: "Llegenda d'al·lèrgens",
    it: "Legenda allergeni",
    pt: "Legenda de alérgenos",
  },
  footCarnes: {
    es: "* En carnes, presencia habitual de sulfitos (13). Consulta en sala.",
    en: "* Meat dishes often contain sulphites (13). Ask staff in the dining room.",
    fr: "* Les viandes contiennent souvent des sulfites (13). Renseignez-vous sur place.",
    de: "* Fleischgerichte enthalten oft Sulfite (13). Bitte vor Ort erfragen.",
    ca: "* En carns, sovint hi ha sulfits (13). Consulteu al personal.",
    it: "* Nei piatti di carne spesso sono presenti solfiti (13). Chiedere al personale.",
    pt: "* Nos pratos de carne costumam existir sulfitos (13). Pergunte na sala.",
  },
  disclaimer: {
    es: "Precios orientativos según carta abril 2026; pueden variar en el local.",
    en: "Indicative prices from the April 2026 menu; may vary at the restaurant.",
    fr: "Prix indicatifs (carte avril 2026) ; peuvent varier sur place.",
    de: "Richtpreise laut Speisekarte April 2026; vor Ort abweichend möglich.",
    ca: "Preus orientatius segons carta abril 2026; poden variar al local.",
    it: "Prezzi indicativi da menu aprile 2026; possono variare in loco.",
    pt: "Preços indicativos conforme ementa abril 2026; podem variar no local.",
  },
};

function allergenTitle(locale: Locale, code: number): string {
  const row = LEGEND.find((l) => l.id === code);
  if (!row) return "";
  return legendLabel(locale, row);
}

function AllergenDots({ codes, locale }: { codes: number[]; locale: Locale }) {
  if (!codes.length) return null;
  return (
    <span className={styles.icons}>
      {codes.map((id) => (
        <span
          key={id}
          className={`${styles.icon} ${ICON_CLASS[id] ?? styles.n1}`}
          title={allergenTitle(locale, id)}
        >
          {id}
        </span>
      ))}
    </span>
  );
}

function DishRow({ m, locale }: { m: MenuItem; locale: Locale }) {
  const codes = allergenCodesFromSpanish(m.allergens?.es);
  const price = priceLine(m, locale);
  const desc = dishDesc(m, locale);
  return (
    <div className={styles.dishBlock}>
      <div className={styles.row}>
        <div className={styles.rowMain}>
          <span className={styles.rowName}>{dishName(m, locale)}</span>
          <AllergenDots codes={codes} locale={locale} />
        </div>
        {price ? (
          <>
            <span className={styles.dots} aria-hidden />
            <span className={styles.price}>{price}</span>
          </>
        ) : null}
      </div>
      {desc ? <p className={styles.rowDesc}>{desc}</p> : null}
    </div>
  );
}

function SectionBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.sectionBlock}>
      <h3 className={styles.secTitle}>{title}</h3>
      {children}
    </div>
  );
}

function LogoMark() {
  return (
    <div className={styles.logoMark} aria-hidden>
      <svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="28" cy="28" r="26" stroke="#1a1a1a" strokeWidth="3" fill="#fff" />
        <path
          d="M28 8 L33.5 22.5 L49 24 L37.5 34 L40.5 49 L28 41 L15.5 49 L18.5 34 L7 24 L22.5 22.5 Z"
          fill="#c40000"
          stroke="#1a1a1a"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
        <path
          d="M28 14 L28 38 M24 18 L32 22 M24 26 L32 22"
          stroke="#1a1a1a"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <ellipse cx="28" cy="40" rx="5" ry="2.2" fill="#1a1a1a" opacity="0.35" />
      </svg>
    </div>
  );
}

export type MenuCartaFolletoProps = {
  locale: Locale;
  menuItems: MenuItem[];
  /** URLs de páginas escaneadas (p. ej. desde `/api/menu-carta/...`). Vacío = solo texto. */
  scanImages?: { src: string; page: number }[];
};

export function MenuCartaFolleto({ locale, menuItems, scanImages = [] }: MenuCartaFolletoProps) {
  const promos = itemsByCategoryEs(menuItems, "Promociones");
  const promoBoxes = promos.filter((p) => p.id !== "promo-reservas");
  const promoReservas = promos.find((p) => p.id === "promo-reservas");
  const { left: tapasL, right: tapasR } = splitTapasColumns(menuItems);

  const firstOf = (catEs: string): MenuItem | undefined => itemsByCategoryEs(menuItems, catEs)[0];
  const title = (catEs: string) => firstOf(catEs)?.category[locale] ?? catEs;

  const tostas = itemsByCategoryEs(menuItems, "Tostas");
  const carnes = itemsByCategoryEs(menuItems, "Carnes");
  const pan = itemsByCategoryEs(menuItems, "Pan y extras");
  const postres = itemsByCategoryEs(menuItems, "Postres");
  const cervezas = itemsByCategoryEs(menuItems, "Cervezas");
  const refrescos = itemsByCategoryEs(menuItems, "Refrescos");
  const copas = itemsByCategoryEs(menuItems, "Copas");
  const cafes = itemsByCategoryEs(menuItems, "Cafés");
  const blancos = itemsByCategoryEs(menuItems, "Blancos");
  const tintos = itemsByCategoryEs(menuItems, "Tintos");
  const rosados = itemsByCategoryEs(menuItems, "Rosados");
  const vermu = itemsByCategoryEs(menuItems, "Vermú");
  const cavas = itemsByCategoryEs(menuItems, "Cavas");

  return (
    <article className={styles.root} lang={locale}>
      <div className={styles.inner}>
        {scanImages.length > 0 ? (
          <div className={styles.scans}>
            <p className={styles.toolbar} style={{ border: "none", padding: 0, marginBottom: 8 }}>
              <span style={{ fontFamily: "system-ui,sans-serif", fontSize: "0.8rem", color: "#4a4a4a" }}>
                {UI.scanIntro[locale]}
              </span>
            </p>
            {scanImages.map(({ src, page }) => (
              <figure key={src} className={styles.scan}>
                <MenuCartaImg src={src} alt={`El Clavo — carta página ${page}`} priority={page === 1} />
              </figure>
            ))}
          </div>
        ) : null}

        <header className={styles.brand}>
          <LogoMark />
          <h1>EL CLAVO</h1>
          <p className={styles.reservas}>
            {promoReservas ? dishName(promoReservas, locale).toUpperCase() : "RESERVAS"}{" "}
            <span className="tabular-nums">
              {promoReservas ? priceLine(promoReservas, locale) || "963 287 041" : "963 287 041"}
            </span>
          </p>
        </header>

        <div className={styles.promos}>
          {promoBoxes.map((p) => (
            <div key={p.id} className={styles.promo}>
              <h3>{dishName(p, locale)}</h3>
              <p>{dishDesc(p, locale)}</p>
              {priceLine(p, locale) ? (
                <div className={styles.promoPrice}>
                  <span>{priceLine(p, locale)}</span>
                </div>
              ) : null}
            </div>
          ))}
        </div>

        <div className={styles.tapasGrid}>
          <section aria-labelledby="tapas-a">
            <h2 id="tapas-a" className={styles.secTitle}>
              {title("Tapas")}
            </h2>
            {tapasL.map((m) => (
              <DishRow key={m.id} m={m} locale={locale} />
            ))}
          </section>
          <section aria-labelledby="tapas-b">
            <h2 id="tapas-b" className={styles.srOnly}>
              {title("Tapas")} (2)
            </h2>
            {tapasR.map((m) => (
              <DishRow key={m.id} m={m} locale={locale} />
            ))}
          </section>
        </div>

        <SectionBlock title={title("Tostas")}>
          {tostas.map((m) => (
            <DishRow key={m.id} m={m} locale={locale} />
          ))}
        </SectionBlock>

        <SectionBlock title={title("Carnes")}>
          {carnes.map((m) => (
            <DishRow key={m.id} m={m} locale={locale} />
          ))}
          <p className={styles.footnote}>{UI.footCarnes[locale]}</p>
        </SectionBlock>

        <SectionBlock title={title("Pan y extras")}>
          {pan.map((m) => (
            <DishRow key={m.id} m={m} locale={locale} />
          ))}
        </SectionBlock>

        <div className={styles.midGrid}>
          <section aria-labelledby="postres-h">
            <h2 id="postres-h" className={styles.secTitle}>
              {title("Postres")}
            </h2>
            {postres.map((m) => (
              <DishRow key={m.id} m={m} locale={locale} />
            ))}
          </section>
          <div className={styles.midStack}>
            <section aria-labelledby="copas-h">
              <h2 id="copas-h" className={styles.secTitle}>
                {title("Copas")}
              </h2>
              {copas.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
            <section aria-labelledby="cafes-h">
              <h2 id="cafes-h" className={styles.secTitle}>
                {title("Cafés")}
              </h2>
              {cafes.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
          </div>
          <div className={styles.midStack}>
            <section aria-labelledby="blancos-h">
              <h2 id="blancos-h" className={styles.secTitle}>
                {title("Blancos")}
              </h2>
              {blancos.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
            <section aria-labelledby="tintos-h">
              <h2 id="tintos-h" className={styles.secTitle}>
                {title("Tintos")}
              </h2>
              {tintos.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
            <section aria-labelledby="rosados-h">
              <h2 id="rosados-h" className={styles.secTitle}>
                {title("Rosados")}
              </h2>
              {rosados.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
            <section aria-labelledby="vermu-h">
              <h2 id="vermu-h" className={styles.secTitle}>
                {title("Vermú")}
              </h2>
              {vermu.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
            <section aria-labelledby="cavas-h">
              <h2 id="cavas-h" className={styles.secTitle}>
                {title("Cavas")}
              </h2>
              {cavas.map((m) => (
                <DishRow key={m.id} m={m} locale={locale} />
              ))}
            </section>
          </div>
        </div>

        <div className={styles.bottomGrid}>
          <section aria-labelledby="cervezas-h">
            <h2 id="cervezas-h" className={styles.secTitle}>
              {title("Cervezas")}
            </h2>
            {cervezas.map((m) => (
              <DishRow key={m.id} m={m} locale={locale} />
            ))}
          </section>
          <section aria-labelledby="refrescos-h">
            <h2 id="refrescos-h" className={styles.secTitle}>
              {title("Refrescos")}
            </h2>
            {refrescos.map((m) => (
              <DishRow key={m.id} m={m} locale={locale} />
            ))}
          </section>
        </div>

        <div className={styles.legend}>
          <h2>{UI.legendTitle[locale]}</h2>
          <div className={styles.legendGrid}>
            {LEGEND.map((row) => (
              <div key={row.id} className={styles.legendItem}>
                <span className={`${styles.icon} ${ICON_CLASS[row.id] ?? styles.n1}`}>{row.id}</span>
                <span>{legendLabel(locale, row)}</span>
              </div>
            ))}
          </div>
        </div>

        <p className={styles.disclaimer}>{UI.disclaimer[locale]}</p>
      </div>
    </article>
  );
}
