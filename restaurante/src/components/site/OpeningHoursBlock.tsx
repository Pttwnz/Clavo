import { VENUE } from "@/lib/venue";

type Props = { compact?: boolean; variant?: "light" | "dark" };

export function OpeningHoursBlock({ compact = false, variant = "light" }: Props) {
  const dark = variant === "dark";
  return (
    <div className={compact ? "text-sm" : ""}>
      <p
        className={
          dark
            ? "text-xs font-semibold uppercase tracking-wider text-[#a89888]"
            : compact
              ? "text-xs font-semibold uppercase tracking-wider text-[#6b5a4e]"
              : "font-display text-base font-semibold text-[#2d2420]"
        }
      >
        Horario del local
      </p>
      <ul
        className={`mt-2 space-y-1 ${dark ? "text-[#d4c8bc]" : compact ? "text-[#4a3f38]" : "text-[#4a3f38] md:text-base"}`}
      >
        {VENUE.openingHoursRows.map((row) => (
          <li
            key={row.days}
            className={`flex flex-wrap justify-between gap-x-4 gap-y-0.5 border-b pb-1 last:border-0 ${
              dark ? "border-white/10" : "border-[#2d2420]/5"
            }`}
          >
            <span className={dark ? "text-[#c4b5a8]" : "text-[#5c4f47]"}>{row.days}</span>
            <span className={`tabular-nums font-medium ${dark ? "text-[#f7f0e8]" : "text-[#2d2420]"}`}>{row.hours}</span>
          </li>
        ))}
      </ul>
      <p
        className={`mt-2 ${dark ? "text-[#9a8a7c]" : "text-[#6b5d55]"} ${compact ? "text-[11px] leading-snug" : "text-xs leading-relaxed"}`}
      >
        {VENUE.openingHoursNote}
      </p>
    </div>
  );
}
