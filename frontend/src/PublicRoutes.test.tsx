import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  cancelarDesdeMail,
  confirmarDesdeMail,
  crearReserva,
  getDisponibilidad,
  getMisTurnos,
  getPrecios,
  simularPago,
} from "./api/public";
import type { PreciosPublicos, ReservaPublica, SimulacionPago } from "./api/types";
import { App } from "./App";

vi.mock("./api/public", () => ({
  getPrecios: vi.fn(),
  getDisponibilidad: vi.fn(),
  crearReserva: vi.fn(),
  simularPago: vi.fn(),
  getMisTurnos: vi.fn(),
  confirmarDesdeMail: vi.fn(),
  cancelarDesdeMail: vi.fn(),
  cotizarCancelacionPublica: vi.fn(),
  cancelarTurnoPublico: vi.fn(),
  reprogramarTurnoPublico: vi.fn(),
}));

const ODONTOLOGO_ID = "19ceb23b-eacd-4ff6-95d6-94f1548d1b30";
const PAGO_ID = "0b6f9a2e-6d7a-4f3e-9a8e-2f1c4a5b6d7e";

function fechaFutura(dias: number): string {
  const destino = new Date();
  destino.setDate(destino.getDate() + dias);
  const mes = String(destino.getMonth() + 1).padStart(2, "0");
  const dia = String(destino.getDate()).padStart(2, "0");
  return `${destino.getFullYear()}-${mes}-${dia}`;
}

const FECHA = fechaFutura(4);
const SLOT_INICIO = `${FECHA}T13:00:00.000Z`;

const PRECIOS: PreciosPublicos = {
  odontologos: [
    { odontologo_id: ODONTOLOGO_ID, monto_turno: "70000.00", monto_senia: "65000.50" },
  ],
  trial: { disponible: true, requiere_tarjeta: false, dias: null },
  marca: "(simulado)",
};

const RESERVA: ReservaPublica = {
  id: "turno-1",
  paciente_id: "pac-1",
  odontologo_id: ODONTOLOGO_ID,
  inicio: SLOT_INICIO,
  fin: `${FECHA}T13:30:00.000Z`,
  estado: "creado",
  canal: "web",
  pago_id: PAGO_ID,
  checkout_url: `http://localhost:5173/checkout-simulado?pago_id=${PAGO_ID}&token=chk_e2e`,
  checkout_token: "chk_e2e",
};

const PAGO_OK: SimulacionPago = {
  pago_id: PAGO_ID,
  estado_pago: "aprobado",
  turno_id: "turno-1",
  estado_turno: "confirmado",
  transicionado: true,
  idempotente: false,
  proveedor: "simulado",
  marca: "(simulado)",
};

function renderRuta(ruta: string): void {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <App />
    </MemoryRouter>,
  );
}

describe("PublicRoutes", () => {
  beforeEach(() => {
    vi.mocked(getPrecios).mockReset();
    vi.mocked(getDisponibilidad).mockReset();
    vi.mocked(crearReserva).mockReset();
    vi.mocked(simularPago).mockReset();
    vi.mocked(getMisTurnos).mockReset();
    vi.mocked(confirmarDesdeMail).mockReset();
    vi.mocked(cancelarDesdeMail).mockReset();

    vi.mocked(getPrecios).mockResolvedValue(PRECIOS);
    vi.mocked(getDisponibilidad).mockResolvedValue({
      slots: [{ inicio: SLOT_INICIO, fin: `${FECHA}T13:30:00.000Z` }],
    });
    vi.mocked(crearReserva).mockResolvedValue(RESERVA);
    vi.mocked(simularPago).mockResolvedValue(PAGO_OK);
  });

  it("ejecuta flujo completo /reservar -> /checkout-simulado -> aprobación simulada sin login", async () => {
    renderRuta("/reservar");

    fireEvent.change(screen.getByLabelText("DNI"), { target: { value: "30111222" } });
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText("Apellido"), { target: { value: "Ficticia" } });
    fireEvent.click(screen.getByLabelText(/Acepto el tratamiento/));
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));

    await screen.findByRole("heading", { name: "Elegí profesional" });
    const radiosProf = await screen.findAllByRole("radio");
    fireEvent.click(radiosProf[0] as HTMLElement);
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));

    await screen.findByRole("heading", { name: "Elegí fecha y horario" });
    fireEvent.change(screen.getByLabelText("Fecha"), { target: { value: FECHA } });
    await waitFor(() => {
      expect(getDisponibilidad).toHaveBeenCalled();
    });
    const radiosSlot = await screen.findAllByRole("radio");
    fireEvent.click(radiosSlot[0] as HTMLElement);
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));

    await screen.findByRole("heading", { name: "Revisá y confirmá" });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));

    expect(
      await screen.findByRole("heading", { name: /Checkout Simulado/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/65\.000/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Aprobar" }));

    expect(simularPago).toHaveBeenCalledWith(PAGO_ID, "aprobar", "chk_e2e");
    expect((await screen.findAllByText(/aprobado/i)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/confirmado/i).length).toBeGreaterThan(0);
  });

  it("expone /reserva, /precios, /mail/confirmar, /mail/cancelar y /mis-turnos sin requerir login", async () => {
    vi.mocked(confirmarDesdeMail).mockResolvedValue({
      ok: true,
      accion: "confirmar",
      estado: "confirmado_desde_mail",
      mensaje: "Turno confirmado.",
    });
    vi.mocked(cancelarDesdeMail).mockResolvedValue({
      ok: true,
      accion: "cancelar",
      estado: "cancelado",
      porcentaje: 100,
      devolucion: null,
      marca: "(simulado)",
      mensaje: "Turno cancelado.",
    });
    vi.mocked(getMisTurnos).mockResolvedValue([]);

    renderRuta("/precios");
    expect(await screen.findByRole("heading", { name: /Precios y condiciones/ })).toBeInTheDocument();
    cleanup();

    renderRuta("/mail/confirmar?token=tok_c");
    expect(await screen.findByText(/confirmado_desde_mail/)).toBeInTheDocument();
    cleanup();

    renderRuta("/mail/cancelar?token=tok_x");
    expect(
      await screen.findByRole("heading", { name: /Turno cancelado/i }),
    ).toBeInTheDocument();
    cleanup();

    renderRuta("/mis-turnos?dni=30111222&token=tok_m");
    expect(await screen.findByText(/No tenés turnos activos registrados/)).toBeInTheDocument();
    cleanup();

    renderRuta("/reserva");
    expect(screen.getByRole("heading", { name: /Reservá tu turno/i })).toBeInTheDocument();
  });
});
