"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { tabletCard, tabletBtnPrimary, tabletInput } from "@/components/tablet/tablet-tokens";

type ItemRow = {
  id: string;
  nameEs: string;
  categoryEs: string;
  hiddenFromPublic: boolean;
};

export function TabletKitchenStops({ onSessionLost }: { onSessionLost?: () => void }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [stopped, setStopped] = useState<Set<string>>(() => new Set());
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setError(null);
    const res = await fetch("/api/tablet/kitchen-stops", { credentials: "include", cache: "no-store" });
    if (res.status === 401 || res.status === 403) {
      onSessionLost?.();
      return;
    }
    if (!res.ok) {
      setError("No se pudo cargar la carta.");
      setLoading(false);
      return;
    }
    const data = (await res.json()) as { items: ItemRow[]; stoppedItemIds: string[] };
    setItems(data.items ?? []);
    setStopped(new Set(data.stoppedItemIds ?? []));
    setLoading(false);
  }, [onSessionLost]);

  useEffect(() => {
    void load();
  }, [load]);

  async function persist(next: Set<string>) {
    setSaving(true);
    setError(null);
    const res = await fetch("/api/tablet/kitchen-stops", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stoppedItemIds: [...next] }),
    });
    setSaving(false);
    if (res.status === 401 || res.status === 403) {
      onSessionLost?.();
      return;
    }
    if (!res.ok) {
      const j = (await res.json().catch(() => ({}))) as { error?: string };
      setError(typeof j.error === "string" ? j.error : "No se pudo guardar");
      void load();
      return;
    }
    setStopped(next);
  }

  function toggle(id: string) {
    const next = new Set(stopped);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    void persist(next);
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (it) =>
        it.nameEs.toLowerCase().includes(q) ||
        it.categoryEs.toLowerCase().includes(q) ||
        it.id.toLowerCase().includes(q),
    );
  }, [items, query]);

  const byCat = useMemo(() => {
    const m = new Map<string, ItemRow[]>();
    for (const it of filtered) {
      const k = it.categoryEs.trim() || "Sin categoría";
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(it);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b, "es"));
  }, [filtered]);

  if (loading) {
    return (
      <section className={tabletCard}>
        <p className="text-lg text-[#5c4f47]">Cargando carta…</p>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <section className={tabletCard}>
        <h2 className="font-display text-2xl font-semibold text-[#1a1614]">Paros de cocina</h2>
        <p className="mt-2 text-lg leading-relaxed text-[#5c4f47]">
          Un plato parado deja de mostrarse en la <strong className="font-semibold">carta web y QR</strong> al
          instante. Queda el resto de la carta visible. Desmarca para volver a ofrecerlo.
        </p>
        <label className="mt-6 flex flex-col gap-2">
          <span className="text-base font-semibold text-[#3d3532]">Buscar</span>
          <input
            className={tabletInput}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nombre o categoría…"
            autoComplete="off"
          />
        </label>
        {saving && (
          <p className="mt-4 text-base font-medium text-[#8a7d72]" role="status">
            Guardando…
          </p>
        )}
        {error && (
          <p className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-base text-red-900" role="alert">
            {error}
          </p>
        )}
      </section>

      <div className="flex flex-wrap gap-3">
        <button type="button" className={tabletBtnPrimary} disabled={saving} onClick={() => void load()}>
          Refrescar lista
        </button>
      </div>

      {byCat.map(([cat, list]) => (
        <section key={cat} className={tabletCard}>
          <h3 className="font-display text-xl font-semibold uppercase tracking-wide text-[#8a7d72]">{cat}</h3>
          <ul className="mt-4 divide-y divide-[#2c1810]/[0.06]">
            {list.map((it) => {
              const isStopped = stopped.has(it.id);
              return (
                <li key={it.id} className="flex flex-wrap items-center justify-between gap-4 py-4 first:pt-0">
                  <div className="min-w-0 flex-1">
                    <p className="text-lg font-semibold text-[#1a1614]">{it.nameEs}</p>
                    <p className="mt-1 text-sm text-[#8a7d72]">
                      <code className="rounded bg-[#faf8f5] px-1.5 py-0.5 text-xs">{it.id}</code>
                      {it.hiddenFromPublic ? (
                        <span className="ml-2 text-amber-800">· ya oculto en panel</span>
                      ) : null}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggle(it.id)}
                    disabled={saving}
                    className={`min-h-[52px] min-w-[160px] rounded-2xl border-2 px-5 text-base font-bold transition active:scale-[0.99] ${
                      isStopped
                        ? "border-red-300 bg-red-50 text-red-900 hover:bg-red-100"
                        : "border-emerald-300 bg-emerald-50 text-emerald-950 hover:bg-emerald-100"
                    }`}
                  >
                    {isStopped ? "Parado · tocar para ofrecer" : "En carta · parar"}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {filtered.length === 0 && (
        <p className="rounded-2xl border border-[#c9a54a]/30 bg-[#fdf8ee] px-5 py-4 text-lg text-[#5c4f47]">
          Nada coincide con la búsqueda.
        </p>
      )}
    </div>
  );
}
