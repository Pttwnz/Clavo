/** Clases compartidas del panel de gestión (identidad Taberna El Clavo). */

export const adminShell =
  "relative min-h-screen overflow-x-hidden bg-gradient-to-br from-[#faf6ed] via-[#f3ece2] to-[#e4dcd2] text-[#2d2420] font-body " +
  "before:pointer-events-none before:fixed before:inset-0 before:-z-10 before:bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,rgba(143,29,29,0.06),transparent_50%)]";

export const adminHeaderBar =
  "border-b border-[#8f1d1d]/20 bg-[#1a1210] text-[#faf6ed] shadow-lg shadow-black/20";

export const adminMainCard =
  "rounded-2xl border border-white/60 bg-white/90 shadow-[0_24px_60px_-18px_rgba(26,18,16,0.18),inset_0_1px_0_rgba(255,255,255,0.85)] ring-1 ring-[#2c1810]/[0.04] backdrop-blur-sm";

export const adminSectionCard =
  "rounded-xl border border-[#2c1810]/[0.08] bg-[#fdfaf7] shadow-sm";

export const adminTableShell =
  "overflow-x-auto rounded-xl border border-[#2c1810]/[0.08] bg-white shadow-sm";

export const adminTableHead =
  "border-b border-[#2c1810]/[0.08] bg-gradient-to-b from-[#faf6ed] to-[#f3ebe4] text-[0.65rem] font-semibold uppercase tracking-wider text-[#6b5d55]";

export const adminInput =
  "rounded-xl border border-[#2c1810]/12 bg-white px-3 py-2 text-[#2d2420] outline-none transition placeholder:text-[#9a8b82] focus:border-[#8f1d1d]/50 focus:ring-2 focus:ring-[#8f1d1d]/15";

export const adminBtnPrimary =
  "inline-flex items-center justify-center rounded-xl bg-[#8f1d1d] px-5 py-2.5 text-sm font-semibold text-[#faf6ed] shadow-md shadow-[#6b1518]/25 transition hover:bg-[#7a1919] disabled:opacity-50";

export const adminBtnSecondary =
  "inline-flex items-center justify-center rounded-xl border border-[#2c1810]/12 bg-white px-4 py-2 text-sm font-medium text-[#3d3532] transition hover:bg-[#faf6ed]";

export const adminBtnOutline =
  "inline-flex items-center justify-center rounded-lg border border-[#2c1810]/12 bg-white px-2.5 py-1.5 text-xs font-medium text-[#3d3532] transition hover:bg-[#faf6ed]";

export const adminBtnDanger =
  "inline-flex items-center justify-center rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-800 hover:bg-red-50";

export const adminBtnLink =
  "text-sm font-medium text-[#8f1d1d] underline decoration-[#8f1d1d]/30 underline-offset-2 hover:decoration-[#8f1d1d]";

export const adminAlertError =
  "rounded-xl border border-red-200/80 bg-red-50/95 px-4 py-3 text-sm text-red-900 shadow-sm";

export const adminAlertInfo =
  "rounded-xl border border-[#c9a54a]/25 bg-[#fdf8ee] px-4 py-3 text-sm text-[#5c4f47]";

export const adminNavTrack =
  "flex flex-wrap gap-1.5 rounded-2xl border border-white/70 bg-white/70 p-1.5 shadow-[inset_0_1px_2px_rgba(0,0,0,0.04)] ring-1 ring-[#2c1810]/[0.05] backdrop-blur-xl";

export function adminNavPill(active: boolean) {
  return active
    ? "flex items-center gap-2 rounded-xl bg-[#8f1d1d] px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-[#6b1518]/30"
    : "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-[#5c4f47] transition hover:bg-[#faf6ed]/90";
}
