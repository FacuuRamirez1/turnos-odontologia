import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/errors";
import {
  descargarExportacion,
  ESTADOS_ASISTENCIA,
  ESTADOS_MAIL,
  getAsistencia,
  getCaja,
  getMailReporte,
  type CajaReporte,
} from "../../api/reportes";
import type { UserRole } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { ReportesPage } from "./ReportesPage";

vi.mock("../../api/reportes", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/reportes")>()),
  getAsistencia: vi.fn(),
  getCaja: vi.fn(),
  getMailReporte: vi.fn(),
  descargarExportacion: vi.fn(),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

const CAJA: CajaReporte = {
  desde: "2026-12-01T00:00:00Z",
  hasta: "2026-12-31T23:59:59Z",
  odontologo_id: null,
  marca: "(simulado)",
  total_aprobado: "10000.00",
  total_devuelto: "6000.00",
  neto: "4000.00",
  filas: [],
};

function conteos(claves: readonly string[], valor: number): Record<string, number> {
  return Object.fromEntries(claves.map((clave) => [clave, valor]));
}

function mockUser(rol: UserRole, odontologoId: string | null): void {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { sub: "u-1", email: `${rol}@clinica-ficticia.example.ar`, rol, odontologo_id: odontologoId },
    sessionExpired: false,
    login: vi.fn(),
    logout: vi.fn(),
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockUser("recepcionista", null);
  vi.mocked(getAsistencia).mockResolvedValue({
    desde: "2026-12-01",
    hasta: "2026-12-31",
    odontologo_id: null,
    conteos: { ...conteos(ESTADOS_ASISTENCIA, 0), atendido: 3, no_show: 1 },
  });
  vi.mocked(getCaja).mockResolvedValue(CAJA);
  vi.mocked(getMailReporte).mockResolvedValue({
    desde: "2026-12-01",
    hasta: "2026-12-31",
    conteos: conteos(ESTADOS_MAIL, 2),
  });
});

describe("ReportesPage", () => {
  it("muestra conteos, caja con marca simulada y mail", async () => {
    render(<ReportesPage />);

    expect(await screen.findByText("Neto: 4000.00")).toBeInTheDocument();
    expect(screen.getByText("(simulado)")).toBeInTheDocument();
    expect(screen.getByTestId("conteo-atendido")).toHaveTextContent("3");
    expect(screen.getByTestId("conteo-no_show")).toHaveTextContent("1");
    expect(screen.getByTestId("mail-fallido")).toHaveTextContent("2");
  });

  it("muestra error reintentable sin perder los filtros", async () => {
    vi.mocked(getAsistencia).mockRejectedValueOnce(new ApiError(500, "Fallo interno"));
    render(<ReportesPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Fallo interno");
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-11-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("Neto: 4000.00")).toBeInTheDocument();
    expect(screen.getByLabelText("Desde")).toHaveValue("2026-11-01");
  });

  it("descarga una exportación con los filtros actuales", async () => {
    const createUrl = vi.fn(() => "blob:fake");
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() });
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.mocked(descargarExportacion).mockResolvedValue(new Blob(["a"]));
    render(<ReportesPage />);
    await screen.findByText("Neto: 4000.00");

    fireEvent.click(screen.getByRole("button", { name: "Turnos CSV" }));

    await waitFor(() => expect(createUrl).toHaveBeenCalled());
    expect(vi.mocked(descargarExportacion).mock.calls[0]?.[0]).toBe("turnos.csv");
    expect(clic).toHaveBeenCalledTimes(1);
    clic.mockRestore();
  });

  it("el odontólogo no ve el filtro de profesional (alcance propio)", async () => {
    mockUser("odontologo", "19ceb23b-eacd-4ff6-95d6-94f1548d1b30");
    render(<ReportesPage />);
    await screen.findByText("Neto: 4000.00");

    expect(screen.queryByLabelText("Profesional (UUID)")).not.toBeInTheDocument();
    expect(vi.mocked(getAsistencia).mock.calls[0]?.[0].odontologoId).toBeUndefined();
  });

  it("rechaza un período invertido sin llamar a la API", async () => {
    render(<ReportesPage />);
    await screen.findByText("Neto: 4000.00");
    vi.mocked(getAsistencia).mockClear();

    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2027-01-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-01-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("posterior");
    expect(getAsistencia).not.toHaveBeenCalled();
  });
});
