/**
 * Datos del local alineados con la ficha pública en mapas (dirección y enlaces Google).
 * Horario: tabla difundida en agregadores (p. ej. Google / Restaurant Guru, abr. 2026); puede variar.
 */
export const VENUE = {
  name: "Taberna El Clavo",
  streetLine: "C/ del Crist del Grau, 16",
  postalCity: "46011 València",
  area: "Poblats Marítims · barri del Grau",
  phoneDisplay: "+34 963 28 70 41",
  phoneTel: "+34963287041",
  footerLine: "Taberna El Clavo · València",
  googleMapsPlaceUrl:
    "https://www.google.com/maps/search/?api=1&query=Taberna+El+Clavo+C%2F+del+Crist+del+Grau+16+46011+Val%C3%A8ncia",
  googleDirectionsUrl:
    "https://www.google.com/maps/dir/?api=1&destination=Carrer+del+Crist+del+Grau%2C+16%2C+46011+Val%C3%A8ncia%2C+Spain",
  googleEmbedMapUrl:
    "https://maps.google.com/maps?q=Carrer+del+Crist+del+Grau%2C+16%2C+46011+Val%C3%A8ncia%2C+Spain&z=17&ie=UTF8&output=embed",
  /** Filas para mostrar en web (lun–dom). */
  openingHoursRows: [
    { days: "Lunes a viernes", hours: "09:30 – 00:00" },
    { days: "Sábado y domingo", hours: "10:00 – 00:00" },
  ] as const,
  openingHoursNote:
    "Horario según datos públicos recientes; en festivos o reformas puede cambiar. Confirma en Google Maps o por teléfono.",
} as const;
