/** Unsplash (licencia propia del servicio). Solo para la franja de miniaturas si no tenéis más fotos propias. */
export function unsplashPhoto(id: string, w: number) {
  return `https://images.unsplash.com/${id}?ixlib=rb-4.1.0&auto=format&fit=crop&w=${w}&q=78`;
}

/** Fotos del local en `public/taberna/` (hero y carta / bloque “Oficio”). */
export const siteImages = {
  hero: "/taberna/barra-el-clavo.png",
  barra: "/taberna/interior-sala.png",
} as const;

/**
 * Franja horizontal inicio: cinco fotos genéricas de hostelería, distintas de hero/barra.
 */
export const homeGalleryStrip: { src: string; alt: string }[] = [
  { src: unsplashPhoto("photo-1414235077428-338989a2e8c0", 800), alt: "Mesa en restaurante (imagen de referencia)" },
  { src: unsplashPhoto("photo-1470337458703-46ad1756a187", 800), alt: "Copas y bar (imagen de referencia)" },
  { src: unsplashPhoto("photo-1504674900247-0877df9cc836", 800), alt: "Plato servido (imagen de referencia)" },
  { src: unsplashPhoto("photo-1555396273-367ea4eb4db5", 800), alt: "Mesa con platos (imagen de referencia)" },
  { src: unsplashPhoto("photo-1466978913421-dad2ebd01d17", 800), alt: "Ambiente de terraza o comedor (imagen de referencia)" },
];

/** @deprecated Usa VENUE.footerLine; se mantiene por si algún import antiguo. */
export const photoCredit = "Taberna El Clavo · València";
