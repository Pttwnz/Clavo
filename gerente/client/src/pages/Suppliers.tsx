import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

type TemplateLine = { label: string; qty: number };

type Supplier = {
  id: number;
  name: string;
  whatsapp_phone: string | null;
  notes: string | null;
  order_weekday: number | null;
  order_interval_days: number | null;
  last_sent_on: string | null;
  template_json: string;
};

const WD: { v: string; n: number }[] = [
  { v: "Domingo", n: 0 },
  { v: "Lunes", n: 1 },
  { v: "Martes", n: 2 },
  { v: "Miércoles", n: 3 },
  { v: "Jueves", n: 4 },
  { v: "Viernes", n: 5 },
  { v: "Sábado", n: 6 },
];

function parseLines(raw: string): TemplateLine[] {
  try {
    const v = JSON.parse(raw) as unknown;
    if (!Array.isArray(v)) return [];
    return v
      .map((x) => {
        if (!x || typeof x !== "object") return null;
        const label = (x as { label?: unknown }).label;
        const qty = (x as { qty?: unknown }).qty;
        if (typeof label !== "string" || typeof qty !== "number") return null;
        return { label, qty: Math.max(0, Math.floor(qty)) };
      })
      .filter(Boolean) as TemplateLine[];
  } catch {
    return [];
  }
}

export default function Suppliers() {
  const [list, setList] = useState<Supplier[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [lines, setLines] = useState<TemplateLine[]>([{ label: "", qty: 1 }]);
  const [weekday, setWeekday] = useState<string>("");
  const [interval, setInterval] = useState<string>("");

  const load = useCallback(async () => {
    setErr(null);
    try {
      const rows = (await apiFetch("/api/suppliers")) as Supplier[];
      setList(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const template_json = JSON.stringify(lines.filter((l) => l.label.trim()).map((l) => ({ label: l.label.trim(), qty: l.qty })));
    await apiFetch("/api/suppliers", {
      method: "POST",
      body: JSON.stringify({
        name,
        template_json,
        order_weekday: weekday === "" ? null : Number(weekday),
        order_interval_days: interval === "" ? null : Number(interval),
      }),
    });
    setName("");
    setLines([{ label: "", qty: 1 }]);
    setWeekday("");
    setInterval("");
    await load();
  }

  async function createOrder(supplierId: number) {
    await apiFetch(`/api/suppliers/${supplierId}/orders`, { method: "POST", body: JSON.stringify({}) });
    alert("Pedido borrador creado. Míralo en Hoy.");
  }

  async function removeSupplier(id: number) {
    if (!confirm("¿Borrar proveedor y sus pedidos?")) return;
    await apiFetch(`/api/suppliers/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <>
      <div className="card">
        <h2>Nuevo proveedor</h2>
        <form onSubmit={(e) => void onCreate(e)}>
          <div className="field">
            <label>Nombre</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Día fijo de pedido (opcional)</label>
            <select value={weekday} onChange={(e) => setWeekday(e.target.value)}>
              <option value="">— Sin día fijo —</option>
              {WD.map((d) => (
                <option key={d.n} value={d.n}>
                  {d.v}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Intervalo en días (opcional)</label>
            <input
              inputMode="numeric"
              placeholder="ej. 7"
              value={interval}
              onChange={(e) => setInterval(e.target.value.replace(/[^\d]/g, ""))}
            />
            <span className="muted">Si rellenas día fijo e intervalo, el día fijo manda.</span>
          </div>
          <div className="field">
            <label>Plantilla (líneas)</label>
            {lines.map((l, i) => (
              <div key={i} style={{ display: "flex", gap: "0.5rem", marginBottom: "0.35rem" }}>
                <input
                  placeholder="Producto"
                  value={l.label}
                  onChange={(e) => {
                    const n = [...lines];
                    n[i] = { ...l, label: e.target.value };
                    setLines(n);
                  }}
                  style={{ flex: 1 }}
                />
                <input
                  style={{ width: "4.5rem" }}
                  inputMode="numeric"
                  value={l.qty}
                  onChange={(e) => {
                    const n = [...lines];
                    n[i] = { ...l, qty: Math.max(0, Number(e.target.value) || 0) };
                    setLines(n);
                  }}
                />
              </div>
            ))}
            <button
              className="btn"
              type="button"
              onClick={() => setLines([...lines, { label: "", qty: 1 }])}
            >
              + línea
            </button>
          </div>
          <button className="btn primary" type="submit" disabled={!name.trim()}>
            Guardar proveedor
          </button>
        </form>
      </div>

      {err ? <p style={{ color: "var(--danger)" }}>{err}</p> : null}

      <div className="card">
        <h2>Lista</h2>
        {list.length === 0 ? <p className="muted">Aún no hay proveedores.</p> : null}
        {list.map((s) => {
          const tmpl = parseLines(s.template_json);
          const wdLabel = s.order_weekday != null ? WD.find((w) => w.n === s.order_weekday)?.v : null;
          return (
            <div key={s.id} style={{ borderTop: "1px solid var(--border)", paddingTop: "0.65rem", marginTop: "0.65rem" }}>
              <strong>{s.name}</strong>
              <div className="muted">
                {wdLabel ? `Día: ${wdLabel}` : "Sin día fijo"}
                {s.order_interval_days ? ` · cada ${s.order_interval_days} días` : ""}
                {s.last_sent_on ? ` · último envío ${s.last_sent_on}` : ""}
              </div>
              <ul style={{ margin: "0.35rem 0", paddingLeft: "1.1rem", fontSize: "0.9rem" }}>
                {tmpl.map((t, i) => (
                  <li key={i}>
                    {t.label} × {t.qty}
                  </li>
                ))}
              </ul>
              <div className="row-actions">
                <button className="btn primary" type="button" onClick={() => void createOrder(s.id)}>
                  Nuevo pedido (borrador)
                </button>
                <button className="btn danger" type="button" onClick={() => void removeSupplier(s.id)}>
                  Borrar
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
