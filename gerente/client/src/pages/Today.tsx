import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

type Supplier = {
  id: number;
  name: string;
  template_json: string;
};

type OpenOrder = {
  id: number;
  supplier_id: number;
  supplier_name: string;
  status: string;
  whatsapp_draft: string | null;
  created_at: string;
};

type Task = {
  id: number;
  title: string;
  cadence: string;
  next_due_on: string | null;
};

type TodayPayload = {
  today: string;
  timeZone: string;
  dueSuppliers: Supplier[];
  openOrders: OpenOrder[];
  tasksDue: Task[];
};

export default function Today() {
  const [data, setData] = useState<TodayPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const j = (await apiFetch("/api/today")) as TodayPayload;
      setData(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function markOrder(id: number, status: "sent" | "received") {
    await apiFetch(`/api/orders/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
    await load();
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      window.prompt("Copia manualmente:", text);
    }
  }

  async function markTaskDone(id: number) {
    await apiFetch(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ mark_done: true }) });
    await load();
  }

  if (err) {
    return (
      <div className="card">
        <p style={{ color: "var(--danger)" }}>{err}</p>
        <button className="btn" type="button" onClick={() => void load()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!data) return <p className="muted">Cargando…</p>;

  return (
    <>
      <p className="muted">
        Día de trabajo: <strong>{data.today}</strong> ({data.timeZone})
      </p>

      <div className="card">
        <h2>Proveedores que tocan hoy</h2>
        {data.dueSuppliers.length === 0 ? (
          <p className="muted">Ninguno con plantilla y día fijo / intervalo que coincida.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {data.dueSuppliers.map((s) => (
              <li key={s.id}>{s.name}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="card">
        <h2>Pedidos abiertos</h2>
        {data.openOrders.length === 0 ? (
          <p className="muted">No hay borradores ni enviados pendientes de recibir.</p>
        ) : (
          data.openOrders.map((o) => (
            <div key={o.id} style={{ borderTop: "1px solid var(--border)", paddingTop: "0.65rem", marginTop: "0.65rem" }}>
              <div>
                <strong>{o.supplier_name}</strong>{" "}
                <span className="muted">
                  ({o.status}) · {new Date(o.created_at).toLocaleString("es-ES")}
                </span>
              </div>
              {o.whatsapp_draft ? <pre className="draft">{o.whatsapp_draft}</pre> : null}
              <div className="row-actions">
                {o.whatsapp_draft ? (
                  <button className="btn primary" type="button" onClick={() => void copyText(o.whatsapp_draft!)}>
                    Copiar WhatsApp
                  </button>
                ) : null}
                {o.status === "draft" ? (
                  <button className="btn" type="button" onClick={() => void markOrder(o.id, "sent")}>
                    Marcar enviado
                  </button>
                ) : null}
                {o.status === "sent" ? (
                  <button className="btn" type="button" onClick={() => void markOrder(o.id, "received")}>
                    Marcar recibido
                  </button>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <h2>Tareas vencidas o para hoy</h2>
        {data.tasksDue.length === 0 ? (
          <p className="muted">Nada pendiente por fecha.</p>
        ) : (
          data.tasksDue.map((t) => (
            <div
              key={t.id}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem", marginTop: "0.5rem" }}
            >
              <div>
                <strong>{t.title}</strong>
                <div className="muted">
                  {t.cadence} · límite {t.next_due_on}
                </div>
              </div>
              <button className="btn primary" type="button" onClick={() => void markTaskDone(t.id)}>
                Hecho
              </button>
            </div>
          ))
        )}
      </div>

      <button className="btn" type="button" onClick={() => void load()}>
        Actualizar
      </button>
    </>
  );
}
