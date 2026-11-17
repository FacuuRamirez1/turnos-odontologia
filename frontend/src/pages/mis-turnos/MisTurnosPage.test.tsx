import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiError } from "../../api/errors";
import {
  cancelarTurnoPublico,
  cotizarCancelacionPublica,
  getDisponibilidad,
  getMisTurnos,
  reprogramarTurnoPublico,
} from "../../api/public";
import type { MisTurnoPublico } from "../../api/types";
import { MisTurnosPage } from "./MisTurnosPage";

vi.mock("../../api/public", () => ({
  getMisTurnos: vi.fn(),
  cotizarCancelacionPublica: vi.fn(),
  cancelarTurnoPublico: vi.fn(),
  reprogramarTurnoPublico: vi.fn(),
  getDisponibilidad: vi.fn(),
}));

const ODONTOLOGO_ID = "19ceb23b-eacd-4ff6-95d6-94f1548d1b30";

function fechaFutura(dias: number): string {
  const destino = new Date();
  destino.setDate(destino.getDate() + dias);
  const mes = String(destino.getMonth() + 1).padStart(2, "0");
  const dia = String(destino.getDate()).padStart(2, "0");
  return `${destino.getFullYear()}-${mes}-${dia}`;
}

const FECHA_REPROG = fechaFutura(5);
const TURNOS_OK: MisTurnoPublico[] = [
  {
    id: "turno-1",
    odontologo_id: ODONTOLOGO_ID,
    inicio: `${fechaFutura(3)}T13:00:00+00:00`,
    fin: `${fechaFutura(3)}T13:30:00+00:00`,
    estado: "confirmado",
  },
];

function renderMisTurnos(url = "/mis-turnos"): void {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/mis-turnos" element={<MisTurnosPage />} />
        <Route path="/reservar" element={<div data-testid="reservar-stub" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MisTurnosPage", () => {
  beforeEach(() => {
    vi.mocked(getMisTurnos).mockReset();
    vi.mocked(cotizarCancelacionPublica).mockReset();
    vi.mocked(cancelarTurnoPublico).mockReset();
    vi.mocked(reprogramarTurnoPublico).mockReset();
    vi.mocked(getDisponibilidad).mockReset();
  });

  it("consulta con dni + token, cotiza cancelación antes de confirmar y muestra devolución", async () => {
    vi.mocked(getMisTurnos).mockResolvedValue(TURNOS_OK);
    vi.mocked(cotizarCancelacionPublica).mockResolvedValue({ porcentaje: 100 });
    vi.mocked(cancelarTurnoPublico).mockResolvedValue({
      id: "turno-1",
      estado: "cancelado",
      devolucion: {
        id: "dev-1",
        porcentaje: 100,
        monto: 65000.5,
        estado: "pendiente",
      },
    });

    renderMisTurnos();

    fireEvent.change(screen.getByLabelText("DNI"), { target: { value: "30.111.222" } });
    fireEvent.change(screen.getByLabelText("Token de acceso"), { target: { value: "tok_valido" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar mis turnos" }));

    expect(await screen.findByText("confirmado")).toBeInTheDocument();
    expect(getMisTurnos).toHaveBeenCalledWith("30111222", "tok_valido");

    fireEvent.click(screen.getByRole("button", { name: "Cancelar turno" }));
    expect(await screen.findByText(/100\s*%/)).toBeInTheDocument();
    expect(cancelarTurnoPublico).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Motivo/i), { target: { value: "Viaje" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelación" }));

    expect(await screen.findByRole("heading", { name: "Turno cancelado" })).toBeInTheDocument();
    expect(screen.getAllByText("cancelado").length).toBeGreaterThan(0);
    expect(cancelarTurnoPublico).toHaveBeenCalledWith(
      "turno-1",
      "30111222",
      "tok_valido",
      "Viaje",
    );
    expect(screen.getByText(/65\.000/)).toBeInTheDocument();
    expect(screen.getByText(/pendiente/i)).toBeInTheDocument();
  });

  it("reprograma un turno confirmado mostrando aviso Q3 sin calcular seña en cliente", async () => {
    vi.mocked(getMisTurnos).mockResolvedValue(TURNOS_OK);
    vi.mocked(getDisponibilidad).mockResolvedValue({
      slots: [
        {
          inicio: `${FECHA_REPROG}T15:00:00+00:00`,
          fin: `${FECHA_REPROG}T15:30:00+00:00`,
        },
      ],
    });
    vi.mocked(reprogramarTurnoPublico).mockResolvedValue({
      origen: { id: "turno-1", estado: "reprogramado" },
      nuevo: {
        id: "turno-2",
        estado: "confirmado",
        pago_id: "pago-1",
        reprogramado_de_id: "turno-1",
      },
    });

    renderMisTurnos("/mis-turnos?dni=30111222&token=tok_q3");

    expect(await screen.findByText("confirmado")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reprogramar" }));

    expect(screen.getByText(/conserva la seña original/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Nueva fecha"), { target: { value: FECHA_REPROG } });

    await waitFor(() => {
      expect(getDisponibilidad).toHaveBeenCalledWith(ODONTOLOGO_ID, FECHA_REPROG);
    });
    const radio = await screen.findByRole("radio");
    fireEvent.click(radio);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar reprogramación" }));

    expect(await screen.findByText(/Turno reprogramado correctamente/i)).toBeInTheDocument();
    expect(reprogramarTurnoPublico).toHaveBeenCalledWith(
      "turno-1",
      "30111222",
      "tok_q3",
      `${FECHA_REPROG}T15:00:00+00:00`,
      expect.any(String),
    );
  });

  it("bloquea consulta solo con DNI sin token en UI y refleja rechazo 401/403 (P12)", async () => {
    renderMisTurnos();

    fireEvent.change(screen.getByLabelText("DNI"), { target: { value: "30111222" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar mis turnos" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/token/i);
    expect(getMisTurnos).not.toHaveBeenCalled();

    vi.mocked(getMisTurnos).mockRejectedValue(
      new PublicApiError("inesperado", "Error", 403, null, "token no autoriza esta consulta"),
    );
    fireEvent.change(screen.getByLabelText("Token de acceso"), { target: { value: "tok_ajeno" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar mis turnos" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/enlace válido enviado por correo|validar tu token/i);
  });

  it("maneja HTTP 429 o turno no cancelable manteniendo entradas y sin filtrar PII", async () => {
    vi.mocked(getMisTurnos).mockRejectedValueOnce(
      new PublicApiError(
        "rate_limit",
        "Demasiadas solicitudes. Esperá un momento y volvé a intentar.",
        429,
      ),
    );
    renderMisTurnos();

    fireEvent.change(screen.getByLabelText("DNI"), { target: { value: "30111222" } });
    fireEvent.change(screen.getByLabelText("Token de acceso"), { target: { value: "tok_429" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar mis turnos" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Demasiadas solicitudes/i);
    expect(screen.getByLabelText("DNI")).toHaveValue("30111222");
    expect(screen.getByLabelText("Token de acceso")).toHaveValue("tok_429");
  });

  it("muestra error claro si un turno no admite cancelación sin filtrar datos ajenos", async () => {
    vi.mocked(getMisTurnos).mockResolvedValue(TURNOS_OK);
    vi.mocked(cotizarCancelacionPublica).mockRejectedValue(
      new PublicApiError(
        "no_procesable",
        "No pudimos procesar la solicitud con esos datos.",
        422,
        "TRANSICION_INVALIDA",
        "El turno ya no admite cancelación.",
      ),
    );
    renderMisTurnos("/mis-turnos?dni=30111222&token=tok_no_cancel");

    fireEvent.click(await screen.findByRole("button", { name: "Cancelar turno" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /no admite cancelación|No pudimos procesar/i,
    );
  });
});
