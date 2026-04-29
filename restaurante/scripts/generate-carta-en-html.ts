/**
 * Genera public/carta/el-clavo-menu-en.html desde menu-carta.ts (inglés + iconos de alérgenos).
 * Ejecutar: npx tsx scripts/generate-carta-en-html.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { MenuItem } from "../src/lib/menu-types";
import { menuItems } from "../src/lib/menu-carta";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");

const ALLERGEN_MAP: [string, number][] = [
  ["soja", 1],
  ["moluscos", 2],
  ["pescado", 3],
  ["crustáceos", 4],
  ["lácteos", 5],
  ["huevo", 6],
  ["gluten", 7],
  ["altramuces", 8],
  ["apio", 9],
  ["sésamo", 10],
  ["mostaza", 11],
  ["cacahuetes", 12],
  ["sulfitos", 13],
  ["frutos secos", 14],
];

function allergenCodesFromText(s: string | undefined): number[] {
  if (!s) return [];
  const low = s.toLowerCase();
  const out: number[] = [];
  for (const [key, code] of ALLERGEN_MAP) {
    if (low.includes(key)) out.push(code);
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

function iconsHtml(codes: number[]): string {
  if (!codes.length) return "";
  return `<span class="alf-icons" aria-label="Allergens">${codes.map((c) => `<span class="alf" data-n="${c}">${c}</span>`).join("")}</span>`;
}

function priceCell(m: MenuItem): string {
  const pt = m.priceText?.en;
  if (pt) return pt.replace(/€/g, "€");
  if (m.price > 0) return `${Number.isInteger(m.price) ? m.price : m.price.toFixed(2)} €`;
  return "";
}

function esc(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function rowHtml(m: MenuItem): string {
  const codes = allergenCodesFromText(m.allergens?.es);
  const desc = m.description.en ? `<span class="dish-desc">${esc(m.description.en)}</span>` : "";
  const pr = priceCell(m);
  return `<div class="dish">
  <div class="dish-main">
    <span class="dish-name">${esc(m.name.en)}</span>
    ${iconsHtml(codes)}
  </div>
  ${desc ? `<div class="dish-sub">${desc}</div>` : ""}
  <span class="dish-price">${esc(pr)}</span>
</div>`;
}

const byCat = (es: string) => menuItems.filter((m) => m.category.es === es);

function sectionHtml(titleEn: string, catEs: string): string {
  const items = byCat(catEs);
  if (!items.length) return "";
  return `<section class="sec"><h2>${esc(titleEn)}</h2>${items.map(rowHtml).join("\n")}</section>`;
}

const specials = byCat("Promociones");
const specialsHtml = specials
  .map((m) => {
    const price = priceCell(m);
    return `<article class="promo"><h3>${esc(m.name.en)}</h3><p>${esc(m.description.en)}</p>${price ? `<p class="promo-price">${esc(price)}</p>` : ""}</article>`;
  })
  .join("");

const tapas = byCat("Tapas");
const mid = Math.ceil(tapas.length / 2);
const tapasL = tapas.slice(0, mid);
const tapasR = tapas.slice(mid);

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>El Clavo — Full menu (English)</title>
<style>
:root {
  --red: #b91c1c;
  --ink: #1c1917;
  --muted: #57534e;
  --paper: #fafaf9;
  --line: #e7e5e4;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif;
  background: #e7e5e4;
  color: var(--ink);
  line-height: 1.35;
}
.wrap {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px 16px 48px;
}
.sheet {
  background: var(--paper);
  box-shadow: 0 4px 24px rgba(0,0,0,.08);
  border-radius: 4px;
  padding: 28px 22px 36px;
}
.brand {
  text-align: center;
  margin-bottom: 8px;
}
.brand svg { width: 56px; height: 56px; }
.brand h1 {
  margin: 8px 0 4px;
  font-size: 2rem;
  letter-spacing: .12em;
  font-weight: 800;
  color: var(--red);
}
.brand p { margin: 0; font-size: .85rem; color: var(--muted); }
.promos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.promo {
  background: #f5f5f4;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 14px 12px;
  text-align: center;
}
.promo h3 { margin: 0 0 8px; font-size: .95rem; color: var(--red); text-transform: uppercase; letter-spacing: .04em; }
.promo p { margin: 0; font-size: .82rem; color: var(--muted); }
.promo-price { margin-top: 10px !important; font-weight: 800; font-size: 1.1rem !important; color: var(--ink) !important; }
.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px 36px;
  margin-bottom: 28px;
}
@media (max-width: 780px) {
  .grid2 { grid-template-columns: 1fr; }
}
.sec h2 {
  margin: 0 0 12px;
  font-size: 1.05rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--red);
  border-bottom: 2px solid var(--red);
  padding-bottom: 6px;
}
.dish {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 10px;
  padding: 8px 0;
  border-bottom: 1px dotted var(--line);
  font-size: .88rem;
  align-items: start;
}
.dish-main { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; }
.dish-name { font-weight: 600; }
.dish-sub { grid-column: 1 / -1; font-size: .78rem; color: var(--muted); margin-top: 2px; }
.dish-price { font-weight: 700; white-space: nowrap; text-align: right; }
.alf-icons { display: inline-flex; gap: 3px; flex-wrap: wrap; }
.alf {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 9px;
  font-weight: 800;
  color: #fff;
  background: #78716c;
}
.alf[data-n="1"] { background: #65a30d; }
.alf[data-n="2"] { background: #0ea5e9; }
.alf[data-n="3"] { background: #0284c7; }
.alf[data-n="4"] { background: #0369a1; }
.alf[data-n="5"] { background: #ca8a04; }
.alf[data-n="6"] { background: #ea580c; }
.alf[data-n="7"] { background: #dc2626; }
.alf[data-n="8"] { background: #84cc16; }
.alf[data-n="9"] { background: #16a34a; }
.alf[data-n="10"] { background: #db2777; }
.alf[data-n="11"] { background: #ca8a04; }
.alf[data-n="12"] { background: #a16207; }
.alf[data-n="13"] { background: #9333ea; }
.alf[data-n="14"] { background: #854d0e; }
.row3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  margin-bottom: 28px;
}
@media (max-width: 900px) {
  .row3 { grid-template-columns: 1fr; }
}
.wines {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
  margin-bottom: 24px;
}
@media (max-width: 700px) {
  .wines { grid-template-columns: 1fr; }
}
.legend {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 2px solid var(--line);
}
.legend h2 { font-size: .95rem; margin: 0 0 14px; color: var(--red); }
.legend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px 14px;
  font-size: .72rem;
}
.legend-item { display: flex; align-items: center; gap: 8px; color: var(--muted); }
.legend-item .alf { flex-shrink: 0; }
.note { font-size: .75rem; color: var(--muted); margin-top: 20px; text-align: center; }
.meats-note { font-size: .78rem; color: var(--muted); margin-top: -12px; margin-bottom: 20px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="sheet">
    <header class="brand">
      <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="28" fill="none" stroke="#1c1917" stroke-width="2"/><path fill="#b91c1c" d="M32 8l6 18h18l-14 10 5 18-15-11-15 11 5-18L8 26h18z"/><line x1="32" y1="8" x2="32" y2="4" stroke="#1c1917" stroke-width="3" stroke-linecap="round"/></svg>
      <h1>EL CLAVO</h1>
      <p>Taberna · València · Reservations 963 287 041</p>
    </header>
    <div class="promos">${specialsHtml}</div>
    <div class="grid2">
      <div>
        <section class="sec"><h2>Tapas</h2>
          ${tapasL.map(rowHtml).join("\n")}
        </section>
      </div>
      <div>
        <section class="sec"><h2>Tapas (continued)</h2>
          ${tapasR.map(rowHtml).join("\n")}
        </section>
      </div>
    </div>
    <div class="row3">
      ${sectionHtml("Toasts", "Tostas")}
      ${sectionHtml("Meats", "Carnes")}
      ${sectionHtml("Bread & extras", "Pan y extras")}
    </div>
    <p class="meats-note">* Meats may contain sulphites and gluten (traces).</p>
    <div class="row3">
      ${sectionHtml("Desserts", "Postres")}
      <div>
        ${sectionHtml("Beers", "Cervezas")}
        ${sectionHtml("Soft drinks", "Refrescos")}
      </div>
      <div>
        ${sectionHtml("Spirits", "Copas")}
        ${sectionHtml("Coffee", "Cafés")}
      </div>
    </div>
    <div class="wines">
      ${sectionHtml("White wines", "Blancos")}
      ${sectionHtml("Red wines", "Tintos")}
    </div>
    <div class="row3">
      ${sectionHtml("Rosé wines", "Rosados")}
      ${sectionHtml("Vermouth", "Vermú")}
      ${sectionHtml("Cava", "Cavas")}
    </div>
    <div class="legend">
      <h2>Allergen legend (numbers on dishes)</h2>
      <div class="legend-grid">
        ${[
          [1, "Soy"],
          [2, "Molluscs"],
          [3, "Fish"],
          [4, "Crustaceans"],
          [5, "Dairy"],
          [6, "Egg"],
          [7, "Gluten"],
          [8, "Lupins"],
          [9, "Celery"],
          [10, "Sesame"],
          [11, "Mustard"],
          [12, "Peanuts"],
          [13, "Sulphites"],
          [14, "Tree nuts"],
        ]
          .map(
            ([n, label]) =>
              `<div class="legend-item"><span class="alf" data-n="${n}">${n}</span><span>${label}</span></div>`,
          )
          .join("")}
      </div>
    </div>
    <p class="note">Prices from the digital menu; may differ in the restaurant. Always confirm allergens with staff.</p>
  </div>
</div>
</body>
</html>`;

const outDir = path.join(root, "public", "carta");
fs.mkdirSync(outDir, { recursive: true });
const outPath = path.join(outDir, "el-clavo-menu-en.html");
fs.writeFileSync(outPath, html, "utf8");
console.log("Wrote", outPath);
