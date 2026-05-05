import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

type Task = {
  id: number;
  title: string;
  cadence: "once" | "daily" | "weekly" | "monthly";
  next_due_on: string | null;
  last_done_on: string | null;
};

export default function Tasks() {
  const [list, setList] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [cadence, setCadence] = useState<Task["cadence"]>("weekly");
  const [next, setNext] = useState("");

  const load = useCallback(async () => {
    const rows = (await apiFetch("/api/tasks")) as Task[];
    setList(rows);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    await apiFetch("/api/tasks", {
      method: "POST",
      body: JSON.stringify({ title, cadence, next_due_on: next || null }),
    });
    setTitle("");
    setNext("");
    await load();
  }

  async function done(id: number) {
    await apiFetch(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ mark_done: true }) });
    await load();
  }

  async function remove(id: number) {
    if (!confirm("¿Borrar tarea?")) return;
    await apiFetch(`/api/tasks/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <>
      <div className="card">
        <h2>Nueva tarea gerencia</h2>
        <form onSubmit={(e) => void onCreate(e)}>
          <div className="field">
            <label>Título</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="field">
            <label>Cadencia</label>
            <select value={cadence} onChange={(e) => setCadence(e.target.value as Task["cadence"])}>
              <option value="once">Una vez</option>
              <option value="daily">Diaria</option>
              <option value="weekly">Semanal</option>
              <option value="monthly">Mensual (aprox. 30 días)</option>
            </select>
          </div>
          <div className="field">
            <label>Próximo vencimiento (YYYY-MM-DD)</label>
            <input placeholder="2026-05-10" value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <button className="btn primary" type="submit">
            Guardar
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Lista</h2>
        {list.map((t) => (
          <div key={t.id} style={{ borderTop: "1px solid var(--border)", paddingTop: "0.65rem", marginTop: "0.65rem" }}>
            <strong>{t.title}</strong>
            <div className="muted">
              {t.cadence} · próximo {t.next_due_on || "—"} · hecho {t.last_done_on || "—"}
            </div>
            <div className="row-actions">
              <button className="btn primary" type="button" onClick={() => void done(t.id)}>
                Marcar hecho
              </button>
              <button className="btn danger" type="button" onClick={() => void remove(t.id)}>
                Borrar
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
