import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function ProtectedRoute(): JSX.Element {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <main className="screen-status" role="status">
        Verificando sesión…
      </main>
    );
  }

  if (status === "anonymous") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
