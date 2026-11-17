import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AgendaPage } from "./pages/agenda/AgendaPage";
import { BandejaPage } from "./pages/bandeja/BandejaPage";
import { LoginPage } from "./pages/login/LoginPage";
import { MailAccionPage } from "./pages/mail/MailAccionPage";
import { MisTurnosPage } from "./pages/mis-turnos/MisTurnosPage";
import { PreciosPage } from "./pages/precios/PreciosPage";
import { CheckoutSimuladoPage } from "./pages/reserva/CheckoutSimuladoPage";
import { ReservaPage } from "./pages/reserva/ReservaPage";

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/reservar" element={<ReservaPage />} />
      <Route path="/reserva" element={<ReservaPage />} />
      <Route path="/checkout-simulado" element={<CheckoutSimuladoPage />} />
      <Route path="/mail/confirmar" element={<MailAccionPage accion="confirmar" />} />
      <Route path="/mail/cancelar" element={<MailAccionPage accion="cancelar" />} />
      <Route path="/mis-turnos" element={<MisTurnosPage />} />
      <Route path="/precios" element={<PreciosPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/agenda" element={<AgendaPage />} />
          <Route path="/bandeja" element={<BandejaPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/agenda" replace />} />
      <Route path="*" element={<Navigate to="/agenda" replace />} />
    </Routes>
  );
}
