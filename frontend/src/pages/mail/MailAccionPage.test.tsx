import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiError } from "../../api/errors";
import { cancelarDesdeMail, confirmarDesdeMail } from "../../api/public";
import type { MailAccionResult } from "../../api/types";
import { MailAccionPage } from "./MailAccionPage";

vi.mock("../../api/public", () => ({
  confirmarDesdeMail: vi.fn(),
  cancelarDesdeMail: vi.fn(),
}));

const CONFIRMADO: MailAccionResult = {
  ok: true,
  accion: "confirmar",
  estado: "confirmado_desde_mail",
  turno_id: "turno-1",
  inicio: "2030-05-20T13:00:00+00:00",
  mensaje: "Tu turno quedó confirmado. Gracias.",
};

const CANCELADO_CON_DEVOLUCION: MailAccionResult = {
  ok: true,
  accion: "cancelar",
  estado: "cancelado",
  turno_id: "turno-1",
  inicio: "2030-05-20T13:00:00+00:00",
  porcentaje: 100,
  devolucion: {
    id: "dev-1",
    porcentaje: 100,
    monto: 65000.5,
    estado: "pendiente",
  },
  marca: "(simulado)",
  mensaje: "Turno cancelado.",
};

function renderMail(accion: "confirmar" | "cancelar", url: string): void {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/mail/confirmar" element={<MailAccionPage accion={accion} />} />
        <Route path="/mail/cancelar" element={<MailAccionPage accion={accion} />} />
        <Route path="/reservar" element={<div data-testid="reservar-stub" />} />
        <Route path="/mis-turnos" element={<div data-testid="mis-turnos-stub" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MailAccionPage", () => {
  beforeEach(() => {
    vi.mocked(confirmarDesdeMail).mockReset();
    vi.mocked(cancelarDesdeMail).mockReset();
  });

  it("confirma el turno desde el mail con token válido", async () => {
    vi.mocked(confirmarDesdeMail).mockResolvedValue(CONFIRMADO);
    renderMail("confirmar", "/mail/confirmar?token=tok_mail_1");

    expect(await screen.findByText(/Tu turno quedó confirmado/i)).toBeInTheDocument();
    expect(confirmarDesdeMail).toHaveBeenCalledWith("tok_mail_1", expect.any(AbortSignal));
    expect(screen.getByText("confirmado_desde_mail")).toBeInTheDocument();
  });

  it("cancela el turno desde el mail mostrando porcentaje, devolución y marca (simulado)", async () => {
    vi.mocked(cancelarDesdeMail).mockResolvedValue(CANCELADO_CON_DEVOLUCION);
    renderMail("cancelar", "/mail/cancelar?token=tok_cancel_1");

    expect(
      await screen.findByRole("heading", { name: /Turno cancelado/i }),
    ).toBeInTheDocument();
    expect(cancelarDesdeMail).toHaveBeenCalledWith("tok_cancel_1", expect.any(AbortSignal));
    expect(screen.getByText(/100\s*%/)).toBeInTheDocument();
    expect(screen.getByText(/65\.000/)).toBeInTheDocument();
    expect(screen.getByText("pendiente")).toBeInTheDocument();
    expect(screen.getAllByText("(simulado)").length).toBeGreaterThan(0);
  });

  it("muestra error claro y enlace a reservar ante token expirado o estado incompatible", async () => {
    vi.mocked(cancelarDesdeMail).mockRejectedValue(
      new PublicApiError(
        "validacion",
        "Revisá los datos ingresados e intentá de nuevo.",
        400,
        "TOKEN_INVALIDO",
        "El link ya no es válido.",
      ),
    );
    renderMail("cancelar", "/mail/cancelar?token=tok_vencido");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/no es válido|expirado/i);
    expect(screen.getByRole("link", { name: /Volver a reservar/ })).toHaveAttribute(
      "href",
      "/reservar",
    );
  });

  it("maneja respuesta ok: false sin romper ni exponer datos de terceros", async () => {
    vi.mocked(confirmarDesdeMail).mockResolvedValue({
      ok: false,
      accion: "confirmar",
      code: "ESTADO_INCOMPATIBLE",
      detail: "El turno ya no está confirmado.",
    });
    renderMail("confirmar", "/mail/confirmar?token=tok_err");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/ya no está confirmado/i);
    expect(screen.getByRole("link", { name: /Volver a reservar/ })).toHaveAttribute(
      "href",
      "/reservar",
    );
  });

  it("ante falta de token en querystring no llama a la API y guía al paciente", async () => {
    renderMail("confirmar", "/mail/confirmar");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/falta el token|enlace incompleto/i);
    expect(confirmarDesdeMail).not.toHaveBeenCalled();
    expect(cancelarDesdeMail).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /Volver a reservar/ })).toHaveAttribute(
      "href",
      "/reservar",
    );
  });

  it("ante ráfaga 429 muestra aviso de espera y permite reintentar", async () => {
    vi.mocked(confirmarDesdeMail)
      .mockRejectedValueOnce(
        new PublicApiError(
          "rate_limit",
          "Demasiadas solicitudes. Esperá un momento y volvé a intentar.",
          429,
          "RATE_LIMIT",
        ),
      )
      .mockResolvedValueOnce(CONFIRMADO);

    renderMail("confirmar", "/mail/confirmar?token=tok_429");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Demasiadas solicitudes/i);

    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText(/Tu turno quedó confirmado/i)).toBeInTheDocument();
    expect(confirmarDesdeMail).toHaveBeenCalledTimes(2);
  });
});
