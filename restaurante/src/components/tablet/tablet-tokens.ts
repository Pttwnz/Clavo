/** UI modo tablet: táctil, espaciado generoso, aspecto “kiosk” moderno. */

export const tabletShell =
  "min-h-[100dvh] bg-gradient-to-b from-[#f5f0ea] via-[#efe8e0] to-[#e5dcd4] text-[#1a1614] font-body " +
  "pb-[max(1rem,env(safe-area-inset-bottom))] pt-[env(safe-area-inset-top)]";

export const tabletAmbient =
  "pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(ellipse_100%_60%_at_50%_-10%,rgba(143,29,29,0.09),transparent_55%)]";

export const tabletHeader =
  "sticky top-0 z-40 border-b border-white/10 bg-[#141210]/[0.88] shadow-lg shadow-black/20 backdrop-blur-2xl";

export const tabletCard =
  "rounded-[1.75rem] border border-white/70 bg-white/90 p-6 shadow-[0_24px_48px_-20px_rgba(20,16,14,0.22),inset_0_1px_0_rgba(255,255,255,0.95)] backdrop-blur-sm md:p-8";

export const tabletCardMuted =
  "rounded-[1.75rem] border border-[#2c1810]/[0.06] bg-white/75 p-6 shadow-inner shadow-black/[0.03] backdrop-blur-sm";

export const tabletInput =
  "min-h-[56px] w-full rounded-2xl border-2 border-[#2c1810]/[0.1] bg-white px-4 py-3.5 text-lg leading-snug text-[#1a1614] shadow-[inset_0_2px_4px_rgba(0,0,0,0.04)] outline-none transition " +
  "focus:border-[#8f1d1d]/55 focus:ring-4 focus:ring-[#8f1d1d]/12";

export const tabletTextarea = tabletInput + " min-h-[100px] resize-y py-3";

export const tabletBtnPrimary =
  "inline-flex min-h-[56px] w-full items-center justify-center rounded-2xl bg-gradient-to-b from-[#a32222] to-[#8f1d1d] px-6 py-4 text-lg font-semibold text-white shadow-lg shadow-[#6b1518]/35 transition active:scale-[0.99] hover:from-[#b52828] hover:to-[#9e2020] disabled:opacity-50";

export const tabletBtnGhost =
  "inline-flex min-h-[48px] items-center justify-center rounded-2xl border border-white/15 bg-white/10 px-5 text-base font-medium text-white transition hover:bg-white/15";

export const tabletSessionPill =
  "flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-emerald-400/25 bg-gradient-to-r from-emerald-50/95 to-teal-50/90 px-5 py-4 shadow-md shadow-emerald-900/5";

export const tabletTabGrid =
  "grid grid-cols-2 gap-3 lg:grid-cols-4";

export function tabletTabTile(active: boolean) {
  return active
    ? "flex min-h-[88px] flex-col items-start justify-center gap-1 rounded-2xl border-2 border-[#8f1d1d]/40 bg-gradient-to-br from-[#8f1d1d] to-[#6b1518] px-4 py-3 text-left text-white shadow-lg shadow-[#6b1518]/30"
    : "flex min-h-[88px] flex-col items-start justify-center gap-1 rounded-2xl border border-[#2c1810]/[0.08] bg-white/90 px-4 py-3 text-left text-[#2d2420] shadow-md shadow-black/[0.04] transition active:scale-[0.99] hover:border-[#8f1d1d]/25 hover:bg-[#fffefb]";
}

export const tabletTabHint = "text-[0.7rem] font-semibold uppercase tracking-wider opacity-75";
export const tabletTabTitle = "text-lg font-bold leading-tight text-[#1a1614]";

/** Listado / mapa envueltos en modo tablet */
export const tabletPanel =
  "rounded-[1.75rem] border border-[#2c1810]/[0.07] bg-white/95 p-5 shadow-[0_16px_40px_-18px_rgba(26,18,16,0.15)] backdrop-blur-sm md:p-6";

export const tabletTableWrap =
  "overflow-x-auto rounded-2xl border border-[#2c1810]/[0.08] bg-white shadow-inner shadow-black/[0.04]";

export const tabletThead =
  "border-b border-[#2c1810]/[0.08] bg-gradient-to-b from-[#faf8f5] to-[#f0ebe4] text-[0.65rem] font-bold uppercase tracking-wider text-[#5c4f47]";

export const tabletStatusBar =
  "flex flex-wrap items-center gap-3 rounded-2xl border border-[#c9a54a]/20 bg-[#fdf8ee]/95 px-4 py-3.5 text-base text-[#4a4038] shadow-sm";

export const tabletAlertError =
  "rounded-2xl border border-red-200/90 bg-red-50 px-4 py-3 text-base text-red-900";

export const tabletChip =
  "inline-flex items-center rounded-full bg-white/15 px-3 py-1 text-sm font-medium backdrop-blur-sm";
