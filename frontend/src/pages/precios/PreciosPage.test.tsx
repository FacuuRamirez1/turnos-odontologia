import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiError } from "../../api/errors";
import { getPrecios } from "../../api/public";
import type { PreciosPublicos } from "../../api/types";
import { PreciosPage } from "./PreciosPage";

vi.mock("../../api/public", () => ({
  getPrecios: vi.fn(),
}));

const PRECIOS_OK: PreciosPublicos = {
  odontologos: [
    {
      odontologo_id: "19ceb23b-eacd-4ff6-95d6-94f1548d1b30",
      monto_turno: "70000.00",
      monto_senia: "65000.50",
    },
  ],
  trial: { disponible: true, requiere_tarjeta: false, dias: null },
  marca: "(simulado)",
};

function renderPrecios(): void {
  render(
    <MemoryRouter initialEntries={["/precios"]}>
      <Routes>
        <Route path="/precios" element={<PreciosPage />} />
        <Route path="/reservar" element={<div data-testid="reservar-stub" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PreciosPage", () => {
  beforeEach(() => {
    vi.mocked(getPrecios).mockReset();
  });

  it("muestra aranceles activos, condiciones de trial y marca (simulado) sin exigir login", async () => {
    vi.mocked(getPrecios).mockResolvedValue(PRECIOS_OK);
    renderPrecios();

    expect(await screen.findByText(/70\.000/)).toBeInTheDocument();
    expect(screen.getByText(/65\.000/)).toBeInTheDocument();
    expect(screen.getByText(/sin tarjeta/i)).toBeInTheDocument();
    expect(screen.getAllByText("(simulado)").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Reservar turno/ })).toHaveAttribute(
      "href",
      "/reservar",
    );
  });

  it("informa estado vacío o error de red sin exponer datos clínicos", async () => {
    vi.mocked(getPrecios).mockRejectedValue(
      new PublicApiError("red", "No pudimos conectarnos con el consultorio."),
    );
    renderPrecios();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/No pudimos conectarnos/i);
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("ante ráfaga 429 permite reintentar y recupera los aranceles", async () => {
    vi.mocked(getPrecios)
      .mockRejectedValueOnce(
        new PublicApiError(
          "rate_limit",
          "Demasiadas solicitudes. Esperá un momento y volvé a intentar.",
          429,
        ),
      )
      .mockResolvedValueOnce(PRECIOS_OK);

    renderPrecios();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Demasiadas solicitudes/i);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText(/70\.000/)).toBeInTheDocument();
    expect(getPrecios).toHaveBeenCalledTimes(2);
  });
});
