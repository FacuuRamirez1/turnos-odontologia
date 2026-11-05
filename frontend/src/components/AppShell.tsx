import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

const ROLE_LABELS: Record<string, string> = {
  odontologo: "Odontología",
  recepcionista: "Recepción",
  admin: "Administración",
  paciente: "Paciente",
};

function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? "Equipo";
}

export function AppShell(): JSX.Element {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [closing, setClosing] = useState(false);

  async function handleLogout(): Promise<void> {
    setClosing(true);
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="site-header__inner">
          <div className="brand">
            <span className="brand__mark" aria-hidden="true" />
            <div>
              <p className="brand__title">Bitácora clínica</p>
              <p className="brand__subtitle">Agenda de turnos</p>
            </div>
          </div>
          <div className="session">
            {user !== null && (
              <p className="session__user">
                <span>{user.email}</span>
                <span className="session__role">{roleLabel(user.rol)}</span>
              </p>
            )}
            <button
              type="button"
              className="button button--quiet"
              onClick={() => {
                void handleLogout();
              }}
              disabled={closing}
            >
              {closing ? "Cerrando…" : "Cerrar sesión"}
            </button>
          </div>
        </div>
      </header>
      <main className="site-main">
        <Outlet />
      </main>
    </div>
  );
}
