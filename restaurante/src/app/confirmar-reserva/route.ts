import { NextResponse } from "next/server";

/**
 * Si alguien abre /confirmar-reserva en el dominio de la web Next, redirige al panel Gastro público
 * (mismo query ?token=…). Útil cuando el correo apuntaba al host equivocado.
 */
export async function GET(request: Request) {
  const base = (process.env.NEXT_PUBLIC_GASTRO_BASE_URL || "").replace(/\/$/, "");
  if (!base) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_GASTRO_BASE_URL no está definida en el servidor." },
      { status: 503 },
    );
  }
  const { searchParams } = new URL(request.url);
  const token = searchParams.get("token") || "";
  if (!token) {
    return NextResponse.redirect(new URL("/#reserva", request.url), 302);
  }
  const target = `${base}/confirmar-reserva?token=${encodeURIComponent(token)}`;
  return NextResponse.redirect(target, 302);
}
