import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, getApiKey, setApiKey } from "../api";

export default function Login() {
  const nav = useNavigate();
  const [key, setKey] = useState(getApiKey());
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      setApiKey(key.trim());
      await apiFetch("/api/today");
      nav("/", { replace: true });
    } catch {
      setApiKey("");
      setErr("Clave incorrecta o servidor no disponible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Clave API</h2>
      <p className="muted">La misma que defines en el VPS como GERENTE_API_KEY. Solo se guarda en este dispositivo.</p>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="k">Clave</label>
          <input id="k" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" />
        </div>
        <button className="btn primary" type="submit" disabled={busy || !key.trim()}>
          Guardar y entrar
        </button>
      </form>
      {err ? <p style={{ color: "var(--danger)", marginTop: "0.75rem" }}>{err}</p> : null}
    </div>
  );
}
