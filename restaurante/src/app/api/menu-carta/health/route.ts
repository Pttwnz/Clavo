import fs from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { menuCartaPublicDirs } from "@/lib/menu-carta-fs";

export const runtime = "nodejs";

export async function GET() {
  const cwd = process.cwd();
  const dirs = menuCartaPublicDirs();
  const esDir = path.join(dirs[0] ?? path.join(cwd, "public"), "taberna", "menu", "es");
  let cartaFilesInEs: string[] = [];
  try {
    if (fs.existsSync(esDir)) {
      cartaFilesInEs = fs.readdirSync(esDir).filter((f) => /^carta-\d+\./i.test(f));
    }
  } catch {
    cartaFilesInEs = [];
  }

  return NextResponse.json(
    {
      cwd,
      publicDirsFound: dirs,
      esMenuDir: esDir,
      esMenuDirExists: fs.existsSync(esDir),
      cartaFilesInEs,
      hint: "Si cartaFilesInEs está vacío, el contenedor no tiene fotos en public/taberna/menu/es/. Añade archivos y rebuild, o monta esa carpeta con Docker.",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
