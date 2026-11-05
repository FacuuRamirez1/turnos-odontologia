import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AgendaPage } from "./pages/agenda/AgendaPage";
import { LoginPage } from "./pages/login/LoginPage";

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/agenda" element={<AgendaPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/agenda" replace />} />
      <Route path="*" element={<Navigate to="/agenda" replace />} />
    </Routes>
  );
}
