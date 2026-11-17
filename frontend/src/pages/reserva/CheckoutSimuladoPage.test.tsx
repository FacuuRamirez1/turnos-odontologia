import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiError } from "../../api/errors";
import { simularPago } from "../../api/public";
import type { SimulacionPago } from "../../api/types";
import { CheckoutSimuladoPage } from "./CheckoutSimuladoPage";

vi.mock("../../api/public", () => ({
  getPrecios: vi.fn(),
  getDisponibilidad: vi.fn(),
  crearReserva: vi.fn(),
  simularPago: vi.fn(),
}));

const PAGO_ID = "0b6f9a2e-6d7a-4f3e-9a8e-2f1c4a5b6d7e";
const TOKEN = "chk_abc";

const PAGO_APROBADO: SimulacionPago = {
  pago_id: PAGO_ID,
  estado_pago: "aprobado",
  turno_id: "turno-1",
  estado_turno: "confirmado",
  transicionado: true,
  idempotente: false,
  proveedor: "simulado",
  marca: "(simulado)",
};

const PAGO_RECHAZADO: SimulacionPago = {
  ...PAGO_APROBADO,
  estado_pago: "rechazado",
  estado_turno: "cancelado",
};

function renderCheckout(entrada: string): void {
  render(
    <MemoryRouter initialEntries={[entrada]}>
      <Routes>
        <Route path="/checkout-simulado" element={<CheckoutSimuladoPage />} />
        <Route path="/reservar" element={<div data-testid="reserva-stub" />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function esperarBanner(): Promise<void> {
  expect(
    await screen.findByRole("heading", { name: /Checkout Simulado/ }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("(simulado)").length).toBeGreaterThan(0);
  expect(screen.getByText(/sin valor fiscal ni movimiento de dinero/)).toBeInTheDocument();
}

describe("CheckoutSimuladoPage", () => {
  beforeEach(() => {
    vi.mocked(simularPago).mockReset();
  });

  it("aprueba en el servidor y refleja pago aprobado, seña y turno confirmado", async () => {
    vi.mocked(simularPago).mockResolvedValue(PAGO_APROBADO);
    renderCheckout(`/checkout-simulado?pago_id=${PAGO_ID}&token=${TOKEN}&monto_senia=65000.50`);

    await esperarBanner();
    expect(screen.getByText(/65\.000/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Aprobar" }));

    expect(simularPago).toHaveBeenCalledWith(PAGO_ID, "aprobar", TOKEN);
    expect((await screen.findAllByText(/aprobado/i)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/confirmado/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Aprobar" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rechazar" })).toBeDisabled();
  });

  it("al rechazar informa la liberación del horario y ofrece volver a reservar", async () => {
    vi.mocked(simularPago).mockResolvedValue(PAGO_RECHAZADO);
    renderCheckout(`/checkout-simulado?pago_id=${PAGO_ID}&token=${TOKEN}`);

    await esperarBanner();
    fireEvent.click(screen.getByRole("button", { name: "Rechazar" }));

    expect(simularPago).toHaveBeenCalledWith(PAGO_ID, "rechazar", TOKEN);
    expect(await screen.findByText(/liberado/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a reservar/ })).toHaveAttribute(
      "href",
      "/reservar",
    );
    expect(screen.getByRole("button", { name: "Rechazar" })).toBeDisabled();
  });

  it("al expirar informa la liberación del horario sin marcar el turno como confirmado", async () => {
    vi.mocked(simularPago).mockResolvedValue({ ...PAGO_RECHAZADO, estado_pago: "expirado" });
    renderCheckout(`/checkout-simulado?pago_id=${PAGO_ID}&token=${TOKEN}`);

    await esperarBanner();
    fireEvent.click(screen.getByRole("button", { name: "Expirar" }));

    expect(simularPago).toHaveBeenCalledWith(PAGO_ID, "expirar", TOKEN);
    expect(await screen.findByText(/liberado/i)).toBeInTheDocument();
    expect(screen.queryByText(/aprobado/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a reservar/ })).toHaveAttribute(
      "href",
      "/reservar",
    );
  });

  it("bloquea la pantalla si falta pago_id o token sin llamar a la API", async () => {
    renderCheckout(`/checkout-simulado?pago_id=${PAGO_ID}`);

    expect(await screen.findByRole("alert")).toHaveTextContent(/token/i);
    expect(screen.queryByRole("button", { name: "Aprobar" })).not.toBeInTheDocument();
    expect(simularPago).not.toHaveBeenCalled();
  });

  it("ante checkout_token consumido avisa y bloquea sin confirmar en el cliente", async () => {
    vi.mocked(simularPago).mockRejectedValue(
      new PublicApiError("no_procesable", "Token inválido.", 422, "TOKEN_INVALIDO"),
    );
    renderCheckout(`/checkout-simulado?pago_id=${PAGO_ID}&token=${TOKEN}`);

    await esperarBanner();
    fireEvent.click(screen.getByRole("button", { name: "Aprobar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/ya fue utilizado|expiró/i);
    expect(screen.queryByText(/confirmado/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aprobar" })).toBeDisabled();
    expect(simularPago).toHaveBeenCalledTimes(1);
  });
});
