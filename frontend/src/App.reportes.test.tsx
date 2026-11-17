import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { useAuth } from "./auth/AuthProvider";

vi.mock("./auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./pages/reportes/ReportesPage", () => ({
  ReportesPage: () => <h2>Reportes y exportaciones</h2>,
}));

vi.mock("./pages/login/LoginPage", () => ({
  LoginPage: () => <h2>Pantalla de login</h2>,
}));

function mockSesion(status: "authenticated" | "anonymous", rol: "recepcionista" | "odontologo"): void {
  vi.mocked(useAuth).mockReturnValue({
    status,
    user:
      status === "authenticated"
        ? { sub: "u-1", email: "staff@clinica-ficticia.example.ar", rol, odontologo_id: null }
        : null,
    sessionExpired: false,
    login: vi.fn(),
    logout: vi.fn(),
  });
}

function renderEn(ruta: string): void {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <App />
    </MemoryRouter>,
  );
}

describe("ruta /reportes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it.each(["recepcionista", "odontologo"] as const)("%s ve la página y el enlace", (rol) => {
    mockSesion("authenticated", rol);

    renderEn("/reportes");

    expect(screen.getByRole("heading", { name: "Reportes y exportaciones" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reportes" })).toBeInTheDocument();
  });

  it("sin sesión redirige al login y no muestra reportes", () => {
    mockSesion("anonymous", "recepcionista");

    renderEn("/reportes");

    expect(screen.getByRole("heading", { name: "Pantalla de login" })).toBeInTheDocument();
    expect(screen.queryByText("Reportes y exportaciones")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Reportes" })).not.toBeInTheDocument();
  });
});
