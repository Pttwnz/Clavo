import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type Search = { token?: string | string[] };

export default async function ConfirmarReservaPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const raw = sp?.token;
  const token = (Array.isArray(raw) ? raw[0] : raw || "").trim();
  if (!token) {
    redirect("/#reserva");
  }

  const base = (process.env.NEXT_PUBLIC_GASTRO_BASE_URL || "").trim().replace(/\/$/, "");
  if (!base) {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center text-sm text-neutral-700">
        <h1 className="mb-3 text-lg font-semibold text-neutral-900">No se puede confirmar desde aquí</h1>
        <p className="leading-relaxed">
          Falta configurar en el servidor la URL pública del panel. Llama al restaurante para confirmar tu reserva.
        </p>
      </main>
    );
  }

  redirect(`${base}/confirmar-reserva?token=${encodeURIComponent(token)}`);
}
