import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { getApiKey } from "./api";
import Login from "./pages/Login";
import Suppliers from "./pages/Suppliers";
import Tasks from "./pages/Tasks";
import Today from "./pages/Today";

function RequireAuth({ children }: { children: ReactNode }) {
  if (!getApiKey()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <div className="layout">
      <div className="topbar">
        <h1>Gerente</h1>
      </div>
      <nav className="nav">
        <NavLink to="/" end>
          Hoy
        </NavLink>
        <NavLink to="/proveedores">Proveedores</NavLink>
        <NavLink to="/tareas">Tareas</NavLink>
        <NavLink to="/login">Clave</NavLink>
      </nav>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Today />
            </RequireAuth>
          }
        />
        <Route
          path="/proveedores"
          element={
            <RequireAuth>
              <Suppliers />
            </RequireAuth>
          }
        />
        <Route
          path="/tareas"
          element={
            <RequireAuth>
              <Tasks />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
