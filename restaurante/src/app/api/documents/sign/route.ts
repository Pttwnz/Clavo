import { NextResponse } from "next/server";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import { createHash } from "node:crypto";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/db";
import { getTabletEmployeeId } from "@/lib/tablet-session";

export const dynamic = "force-dynamic";

type Body = {
  employeeId?: string;
  pin?: string;
  title?: string;
  documentKind?: string;
  signaturePngB64?: string;
};

function stripDataUrl(b64: string): string {
  const m = b64.match(/^data:image\/png;base64,(.+)$/);
  return m ? m[1]! : b64;
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as Body | null;
  if (!body?.employeeId || !body.signaturePngB64 || !body.title?.trim()) {
    return NextResponse.json({ error: "Faltan datos o título" }, { status: 400 });
  }

  const employee = await prisma.employee.findFirst({
    where: { id: body.employeeId, active: true },
  });
  if (!employee) {
    return NextResponse.json({ error: "Empleado no encontrado" }, { status: 404 });
  }

  const tabletId = await getTabletEmployeeId();
  const pinOk =
    tabletId === employee.id ||
    (typeof body.pin === "string" && (await bcrypt.compare(body.pin, employee.pinHash)));
  if (!pinOk) {
    return NextResponse.json({ error: "PIN incorrecto" }, { status: 401 });
  }

  let pngBuffer: Buffer;
  try {
    pngBuffer = Buffer.from(stripDataUrl(body.signaturePngB64), "base64");
  } catch {
    return NextResponse.json({ error: "Firma no válida" }, { status: 400 });
  }

  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([595.28, 841.89]);
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica);
  const title = body.title.trim();
  const kind = typeof body.documentKind === "string" ? body.documentKind.trim() || "ACK" : "ACK";
  const signedAt = new Date().toISOString();

  page.drawText(title, { x: 50, y: 780, size: 16, font, color: rgb(0.1, 0.1, 0.1) });
  page.drawText(`Empleado: ${employee.name}`, { x: 50, y: 750, size: 12, font });
  page.drawText(`Fecha (UTC): ${signedAt}`, { x: 50, y: 730, size: 11, font, color: rgb(0.3, 0.3, 0.3) });
  page.drawText("Firma manuscrita (captura digital):", { x: 50, y: 680, size: 11, font });

  const png = await pdfDoc.embedPng(pngBuffer);
  const w = 220;
  const h = (png.height / png.width) * w;
  page.drawImage(png, { x: 50, y: 520 - h, width: w, height: h });

  page.drawText("Este documento se generó en el sistema interno del restaurante.", {
    x: 50,
    y: 480 - h,
    size: 8,
    font,
    color: rgb(0.4, 0.4, 0.4),
    maxWidth: 495,
  });
  page.drawText("La firma gráfica tiene valor interno; eIDAS requiere proveedor cualificado.", {
    x: 50,
    y: 468 - h,
    size: 8,
    font,
    color: rgb(0.4, 0.4, 0.4),
    maxWidth: 495,
  });

  const pdfBytes = await pdfDoc.save();
  const buf = Buffer.from(pdfBytes);
  const sha256 = createHash("sha256").update(buf).digest("hex");

  const record = await prisma.signedDocument.create({
    data: {
      employeeId: employee.id,
      title,
      documentKind: kind,
      signaturePngB64: body.signaturePngB64,
      pdfBytes: buf,
      sha256,
    },
  });

  return NextResponse.json({
    id: record.id,
    sha256,
    signedAt: record.signedAt.toISOString(),
    pdfBase64: buf.toString("base64"),
    filename: `documento-${record.id}.pdf`,
  });
}
